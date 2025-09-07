"""
Yandex serverless function for handling user queries with semantic caching and
database-backed retrieval.  This module implements two HTTP endpoints:

1. **/retrive** – Given a natural‑language queue and a hashed Telegram ID
   (``tg_id_md5``), this endpoint tries to answer the query from cache.  If a
   semantically similar entry exists in the cache and is still valid, the
   cached answer is returned along with metadata describing whether the hit
   occurred and how much time remains until expiration.  Otherwise the
   pipeline falls back to LLM‑powered classification and SQL generation to
   execute the query against a PostgreSQL database, formats the results, and
   caches the new answer.

2. **/check** – Performs the same semantic cache lookup as ``/retrive`` but
   never executes the full pipeline.  It simply reports whether a cache
   record exists and its remaining TTL.

The cache uses a PostgreSQL table with pgvector support to store
embeddings, answers and metadata.  RedisSemanticCache from the LangChain
integration does not allow per‑record TTLs – TTL is a single argument
applied to the entire cache during initialisation【948225200163348†L148-L154】.
Because this application requires per‑record expiration times, a custom
SQLAlchemy schema is used instead.  Embeddings are computed using
``langchain_openai.OpenAIEmbeddings`` which produces 1536‑dimensional vectors
for the ``text‑embedding‑ada‑002`` model【283258372823551†L118-L139】.  When
searching the cache the cosine distance is computed in SQL using pgvector’s
functions; a threshold of 0.7 is adopted as recommended for filtering
semantically relevant results【283258372823551†L298-L303】.

Environment variables expected by this module:

``POSTGRES_URI``      – SQLAlchemy connection string, e.g. ``postgresql+psycopg2://user:password@host/db``
``OPENROUTER_API_KEY`` – API key for the OpenRouter LLM service
``OPENROUTER_BASE_URL`` – Base URL for the OpenRouter endpoint (default ``https://openrouter.ai/api/v1``)
``CACHE_TTL_HOURS``   – Default TTL in hours for new cache entries (default ``48``)

If ``OPENROUTER_API_KEY`` is not set the LLM calls will raise an error.  All
network calls are synchronous for simplicity; for production a fully
asynchronous implementation with ``aiohttp`` is recommended.

This file is designed to run in a Yandex Cloud serverless environment where
incoming requests are passed as JSON to the ``handler`` function.  The
``handler`` dispatches to the appropriate endpoint based on the request
``path``.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from sqlalchemy import (
    Column,
    DateTime,
    JSON as SQLJSON,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from pgvector.sqlalchemy import Vector
from langchain_openai import OpenAIEmbeddings


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

# Embedding dimension.  OpenAI's ``text‑embedding‑ada‑002`` model returns
# 1536‑element vectors【283258372823551†L118-L139】.  Adjust N_DIM if you use
# another embedding model.
N_DIM: int = 1536

# Similarity threshold: vectors whose cosine distance is below this value are
# considered close enough to count as a cache hit.  A threshold of 0.7 has
# been suggested for balancing recall and precision【283258372823551†L298-L303】.
SIMILARITY_THRESHOLD: float = 0.7

# Default cache TTL in hours for new entries.  If ``CACHE_TTL_HOURS`` is set
# this constant is overridden when computing expiration dates.
DEFAULT_TTL_HOURS: float = float(os.environ.get("CACHE_TTL_HOURS", 48))


# ----------------------------------------------------------------------------
# Database Models
# ----------------------------------------------------------------------------

Base = declarative_base()


class CacheEntry(Base):
    """SQLAlchemy model representing a cached answer.

    Each record stores the hashed Telegram ID, the original query and its
    embedding, the generated response and its embedding, the expiry time and
    optional metadata.  The ``queue_embd`` and ``response_embd`` columns use
    pgvector’s ``Vector`` type.
    """

    __tablename__ = "semantic_cache"

    id: str = Column(String, primary_key=True)
    tg_id_md5: str = Column(String, nullable=False, index=True)
    queue: str = Column(Text, nullable=False)
    queue_embd: np.ndarray = Column(Vector(N_DIM), nullable=False)
    response: str = Column(Text, nullable=False)
    response_embd: np.ndarray = Column(Vector(N_DIM), nullable=False)
    cache_ttl: datetime = Column(DateTime(timezone=True), nullable=False)
    metadata: Dict[str, Any] = Column(SQLJSON, nullable=True)


# Create engine and session factory at module import time.  If the database
# connection fails at import you will see an exception in the logs.  In a
# serverless environment you may prefer to lazily initialise the engine
# during the first invocation, but keeping it global improves connection
# pooling for repeated calls.
POSTGRES_URI: str = os.environ.get("POSTGRES_URI", "postgresql+psycopg2://user:pass@localhost/db")
engine = create_engine(POSTGRES_URI, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# Ensure the table exists.  If the extension ``vector`` is not installed in
# Postgres this call will fail.  Use ``CREATE EXTENSION IF NOT EXISTS vector;``
# on your database first.
Base.metadata.create_all(engine)


# ----------------------------------------------------------------------------
# Embeddings and LLM clients
# ----------------------------------------------------------------------------

_embedding_client: Optional[OpenAIEmbeddings] = None


def get_embedding_client() -> OpenAIEmbeddings:
    """Initialise and return an embedding client.

    ``OpenAIEmbeddings`` uses the environment variables ``OPENAI_API_KEY`` or
    ``OPENROUTER_API_KEY`` depending on the configured provider.  The client
    caches underlying HTTP sessions, so it is safe to reuse across calls.
    """

    global _embedding_client
    if _embedding_client is None:
        # ``openai_api_key`` can be mapped to ``OPENROUTER_API_KEY`` when using
        # OpenRouter as a proxy for OpenAI endpoints.
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENROUTER_API_KEY or OPENAI_API_KEY must be set to compute embeddings"
            )
        # Provide the API key via environment variable expected by langchain-openai
        os.environ.setdefault("OPENAI_API_KEY", api_key)
        _embedding_client = OpenAIEmbeddings()
    return _embedding_client


def embed_text(text: str) -> List[float]:
    """Compute a 1536‑dimensional embedding for a piece of text.

    Returns a list of floats suitable for storage in a pgvector column.
    """

    client = get_embedding_client()
    # ``embed_query`` returns a list of floats
    return client.embed_query(text)


def call_openrouter(prompt: str, model: str = "openai/gpt-5-nano") -> str:
    """Send a prompt to the OpenRouter API and return the generated text.

    The OpenRouter endpoint is determined by ``OPENROUTER_BASE_URL`` and
    requires an API key set in ``OPENROUTER_API_KEY``.  The response is
    expected to be a JSON object containing the top level field ``response``
    or ``content`` depending on the provider.  If the request fails an
    exception is raised.
    """

    api_key = os.environ.get("OPENROUTER_API_KEY")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY must be set for LLM calls")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": 1024,
        "temperature": 0.0,
    }
    resp = requests.post(f"{base_url}/complete", headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # Try common response fields
    return data.get("response") or data.get("content") or data.get("choices", [{}])[0].get("text") or ""


# ----------------------------------------------------------------------------
# Cache operations
# ----------------------------------------------------------------------------

def find_cached_answer(session: Session, tg_id_md5: str, query_embd: List[float]) -> Optional[Tuple[CacheEntry, float]]:
    """Look up the most similar cached entry for the given user and embedding.

    Returns a tuple of the ``CacheEntry`` instance and the computed cosine
    distance if a record is within the similarity threshold and has not
    expired.  Otherwise returns ``None``.
    """

    # Build a select statement computing cosine distance using pgvector
    # ``cosine_distance`` returns a value between 0 and 2 (0 = identical, 1 =
    # orthogonal, 2 = opposite).  We filter for distances below
    # ``SIMILARITY_THRESHOLD``【283258372823551†L298-L303】.
    distance_expr = CacheEntry.queue_embd.cosine_distance(query_embd)
    stmt = (
        select(CacheEntry, distance_expr.label("distance"))
        .where(CacheEntry.tg_id_md5 == tg_id_md5)
        .where(CacheEntry.cache_ttl > datetime.now(timezone.utc))
        .order_by(distance_expr)
        .limit(1)
    )
    try:
        result = session.execute(stmt).first()
    except SQLAlchemyError:
        return None
    if result is None:
        return None
    entry, distance = result
    if distance is None or distance >= SIMILARITY_THRESHOLD:
        return None
    return entry, float(distance)


def save_cache_entry(
    session: Session,
    tg_id_md5: str,
    queue: str,
    queue_embd: List[float],
    response_text: str,
    response_embd: List[float],
    ttl_hours: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> CacheEntry:
    """Persist a new cache entry in the database.

    The TTL is converted into an expiry timestamp relative to ``datetime.now``.
    Returns the created ``CacheEntry`` instance.
    """

    expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    entry = CacheEntry(
        id=str(uuid.uuid4()),
        tg_id_md5=tg_id_md5,
        queue=queue,
        queue_embd=queue_embd,
        response=response_text,
        response_embd=response_embd,
        cache_ttl=expires,
        metadata=metadata or {},
    )
    session.add(entry)
    session.commit()
    return entry


# ----------------------------------------------------------------------------
# Query classification and SQL generation
# ----------------------------------------------------------------------------

def classify_query(query: str) -> Dict[str, Any]:
    """Classify the user’s query using an LLM.

    The LLM is instructed to output a JSON object with the following keys:
    ``query_type`` (``simple_select``|``select_with_vector``|``complex_hybrid``),
    ``analysis_need`` (``no_analysis``|``need_rag``), ``intent`` (short phrase
    describing the intent), ``confidence`` (0–1), and ``explanation``.

    If the LLM call fails, a simple heuristic classifier is applied: queries
    containing «эмоци» or «тренд» are treated as requiring analysis and
    labelled ``select_with_vector`` with ``need_rag``, otherwise
    ``simple_select`` with ``no_analysis``.  The confidence is set
    accordingly.  This fallback ensures robustness when the external LLM
    service is unavailable.
    """

    try:
        prompt = (
            "Ты — помощник для классификации SQL‑запросов. "
            "Проанализируй следующий запрос пользователя и верни JSON со "
            "следующими полями: query_type (simple_select|select_with_vector|complex_hybrid), "
            "analysis_need (no_analysis|need_rag), intent (краткое описание намерения), "
            "confidence (0.0‑1.0), explanation (почему выбрана такая классификация).\n\n"
            f"Запрос: {query}\n\n"
            "Ответи только JSON без других пояснений."
        )
        response = call_openrouter(prompt)
        classification = json.loads(response.strip())
        return classification
    except Exception:
        # Fallback heuristic
        lower_q = query.lower()
        requires_analysis = any(term in lower_q for term in ["эмоци", "emotion", "тренд", "trend"])
        classification = {
            "query_type": "simple_select" if not requires_analysis else "select_with_vector",
            "analysis_need": "no_analysis" if not requires_analysis else "need_rag",
            "intent": "получение сообщений" if not requires_analysis else "получение сообщений с анализом",
            "confidence": 0.5,
            "explanation": "heuristic classification due to LLM failure",
        }
        return classification


def build_sql(query: str, classification: Dict[str, Any]) -> str:
    """Generate an SQL statement from the user’s query and classification.

    A simple template is used here for demonstration.  In practice you could
    prompt the LLM with the database schema and examples to produce a safe
    query.  The returned SQL should be validated with ``EXPLAIN`` before
    execution.
    """

    # Extract possible user name from the Russian query using a naive heuristic.
    # This works for queries like "Найди все сообщения пользователя Коли".  In
    # a real system you would parse the query properly or ask an LLM to
    # generate the SQL.
    words = query.split()
    user_name: Optional[str] = None
    for i, word in enumerate(words):
        if word.lower().startswith("пользователь") and i + 1 < len(words):
            user_name = words[i + 1]
            break
    user_name = user_name or ""

    # Basic SELECT for retrieving messages.
    base_select = "SELECT message_text, created_at FROM messages"
    if user_name:
        base_select += f" WHERE username ILIKE '%{user_name}%'"

    # For analytical queries we may need to join other tables or compute
    # sentiment/trend.  Use a simple SELECT here; analysis will be done
    # separately.
    sql_query = base_select + " ORDER BY created_at DESC LIMIT 100;"
    return sql_query


def execute_sql(sql_query: str) -> List[Dict[str, Any]]:
    """Execute the SQL query and return the rows as dictionaries.

    Before execution the query is validated using ``EXPLAIN``.  If ``EXPLAIN``
    fails an exception is raised.  The function returns a list of dictionaries
    with keys matching the selected columns.  Exceptions from the database are
    propagated to the caller.
    """

    with SessionLocal() as session:
        # Validate the query plan
        session.execute(f"EXPLAIN {sql_query}")
        result = session.execute(sql_query)
        rows = [dict(r) for r in result.fetchall()]
        return rows


def format_results(rows: List[Dict[str, Any]]) -> str:
    """Format SQL results into a human‑readable string.

    If there are no rows a suitable message is returned.  Otherwise each row
    is converted into a simple textual representation.
    """

    if not rows:
        return "Нет данных, удовлетворяющих запросу."
    formatted_lines = []
    for row in rows:
        parts = [f"{k}: {v}" for k, v in row.items()]
        formatted_lines.append("; ".join(parts))
    return "\n".join(formatted_lines)


def analyze_results(rows: List[Dict[str, Any]], intent: str) -> str:
    """Perform additional analysis on SQL results when required.

    For example, sentiment analysis or trend extraction.  The LLM is
    instructed to summarise the data according to the user’s intent.  If
    analysis fails the raw formatted results are returned.
    """

    try:
        formatted = format_results(rows)
        prompt = (
            f"На основе следующих данных пожалуйста проведи анализ. "
            f"Намерение: {intent}.\n\n{formatted}\n\n"
            "Верни краткое заключение на русском языке."
        )
        summary = call_openrouter(prompt)
        return summary.strip()
    except Exception:
        return format_results(rows)


# ----------------------------------------------------------------------------
# HTTP Handlers
# ----------------------------------------------------------------------------

def handle_check(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle the /check endpoint.

    Performs a semantic lookup in the cache but does not execute the full
    pipeline.  Returns whether a cache entry exists and its expiration time.
    """

    query = body.get("queue", "")
    tg_id_md5 = body.get("tg_id_md5")
    if not query or not tg_id_md5:
        return {"error": "queue and tg_id_md5 are required"}
    query_embd = embed_text(query)
    with SessionLocal() as session:
        found = find_cached_answer(session, tg_id_md5, query_embd)
        if not found:
            return {"cache-hit": False, "cache-ttl": None}
        entry, _ = found
        return {"cache-hit": True, "cache-ttl": entry.cache_ttl.isoformat()}


def handle_retrive(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle the /retrive endpoint.

    Checks the cache first.  On a hit returns the cached answer.  On a miss
    invokes the classification and SQL pipeline, caches the result and
    returns it along with metadata.
    """

    query = body.get("queue", "")
    tg_id_md5 = body.get("tg_id_md5")
    metadata = body.get("metadata", {})
    cache_enabled = body.get("cache", True)
    if not query or not tg_id_md5:
        return {"error": "queue and tg_id_md5 are required"}

    # Compute embedding for the incoming query
    query_embd = embed_text(query)

    with SessionLocal() as session:
        # Step 1: check semantic cache if enabled
        if cache_enabled:
            found = find_cached_answer(session, tg_id_md5, query_embd)
            if found:
                entry, distance = found
                # Determine how many hours remain until expiry
                remaining = entry.cache_ttl - datetime.now(timezone.utc)
                ttl_hours = max(0.0, remaining.total_seconds() / 3600.0)
                return {
                    "output": entry.response,
                    "cache-hit": True,
                    "cache-ttl": f"{ttl_hours:.2f}h",
                }

        # Step 2: no cache hit, proceed with classification and SQL execution
        classification = classify_query(query)
        sql_query = build_sql(query, classification)
        rows = execute_sql(sql_query)
        # Format results or run analysis
        if classification.get("analysis_need") == "need_rag":
            result_text = analyze_results(rows, classification.get("intent", ""))
        else:
            result_text = format_results(rows)

        # Compute embedding for the response
        response_embd = embed_text(result_text)
        ttl_hours = DEFAULT_TTL_HOURS
        # Save to cache for future requests
        if cache_enabled:
            save_cache_entry(
                session,
                tg_id_md5=tg_id_md5,
                queue=query,
                queue_embd=query_embd,
                response_text=result_text,
                response_embd=response_embd,
                ttl_hours=ttl_hours,
                metadata=metadata,
            )
        return {
            "output": result_text,
            "cache-hit": False,
            "cache-ttl": f"{ttl_hours:.2f}h",
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entrypoint for Yandex Cloud serverless function.

    Dispatches incoming HTTP requests based on the request path.  The
    expected structure of ``event`` is documented in Yandex Cloud; it
    contains a ``path`` attribute and a JSON ``body``.
    """

    path = event.get("path", "").rstrip("/")
    try:
        body = json.loads(event.get("body", "{}")) if event.get("body") else {}
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON"})}

    if path.endswith("/check"):
        result = handle_check(body)
    elif path.endswith("/retrive"):
        result = handle_retrive(body)
    else:
        result = {"error": f"Unknown path: {path}"}

    return {"statusCode": 200, "body": json.dumps(result, ensure_ascii=False)}