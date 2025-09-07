import json
import re
from enum import Enum
from typing import Dict, Any
from openai import OpenAI

# ─────────────────────────────────────────────
# 1. Категории запросов
# ─────────────────────────────────────────────
class QueryCategory(str, Enum):
    EXACT_ID = "EXACT_ID"        # Точный артефакт / id
    PROCEDURE = "PROCEDURE"      # Пошаговая инструкция
    CONCEPT = "CONCEPT"          # Концептуальное объяснение
    OVERVIEW = "OVERVIEW"        # Обзор «всё по теме»


# ─────────────────────────────────────────────
# 2. Настройки Retrieval в зависимости от категории
# ─────────────────────────────────────────────
CATEGORY_CONFIGS: Dict[QueryCategory, Dict[str, Any]] = {
    QueryCategory.EXACT_ID: dict(
        hybrid=True,
        bm25_weight=0.45,
        k=5,
        mmr=False,
        rerank=False,
        token_budget=800,
    ),
    QueryCategory.PROCEDURE: dict(
        hybrid=True,
        bm25_weight=0.30,
        k=10,
        mmr=True,
        mmr_lambda=0.60,
        rerank=False,
        token_budget=1200,
    ),
    QueryCategory.CONCEPT: dict(
        hybrid=True,
        bm25_weight=0.25,
        k=15,
        mmr=True,
        mmr_lambda=0.55,
        rerank=True,
        rerank_pool=30,
        token_budget=1800,
    ),
    QueryCategory.OVERVIEW: dict(
        hybrid=False,
        k=20,
        mmr=True,
        mmr_lambda=0.40,
        rerank=True,
        rerank_pool=40,
        token_budget=2500,
    ),
}


# ─────────────────────────────────────────────
# 3. Промпт для LLM‑классификатора
# ─────────────────────────────────────────────
CLASSIFIER_PROMPT = (
    "Ты модуль, который классифицирует пользовательские вопросы в одну из категорий: "
    "EXACT_ID — вопрос содержит точный идентификатор или артефакт (короткий, с цифрами, 'HR-42', 'VPN-ip').\n"
    "PROCEDURE — запрос о пошаговых действиях (начинается со слов 'как', 'how', 'что делать', 'where to', содержит глаголы настройки или действий).\n"
    "CONCEPT — вопрос о смысловом объяснении или принципе (8+ слов, без слова 'все', 'list').\n"
    "OVERVIEW — запрос об обзоре / перечислении всего по теме (12+ слов и содержит слова 'все', 'list', 'обзор', 'all').\n\n"
    "Ответь ровно JSON вида {\"category\": \"<CATEGORY>\"} без лишнего текста."
)


# ─────────────────────────────────────────────
# 4. Heuristic fallback (если LLM не дал валидный JSON)
# ─────────────────────────────────────────────
ID_PATTERN = re.compile(r"[A-Z]{2,}[-_][\w\d]+|\d{2,}\b")


def _heuristic_detect(query: str) -> QueryCategory:
    q = query.lower()
    tokens = q.split()
    if ID_PATTERN.search(query) and len(tokens) <= 4:
        return QueryCategory.EXACT_ID
    if tokens[0] in {"как", "how", "where", "что", "what", "когда"} and len(tokens) <= 12:
        return QueryCategory.PROCEDURE
    if len(tokens) >= 12 and any(w in q for w in ("all", "все", "list", "обзор")):
        return QueryCategory.OVERVIEW
    return QueryCategory.CONCEPT


# ─────────────────────────────────────────────
# 5. Основная функция классификации
# ─────────────────────────────────────────────

def classify_query(client: OpenAI, query: str) -> QueryCategory:
    """Определяет категорию запроса с помощью LLM. Возвращает QueryCategory."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": CLASSIFIER_PROMPT},
                {"role": "user", "content": query},
            ],
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        category = QueryCategory(data.get("category", ""))
    except Exception:
        # если LLM ошибся — fallback на эвристику
        category = _heuristic_detect(query)
    return category


# ─────────────────────────────────────────────
# 6. Функция получения динамических параметров для RAG
# ─────────────────────────────────────────────

def get_dynamic_params(client: OpenAI, query: str) -> Dict[str, Any]:
    cat = classify_query(client, query)
    return CATEGORY_CONFIGS[cat]


# ─────────────────────────────────────────────
# 7. Пример использования
# ─────────────────────────────────────────────
if __name__ == "__main__":
    from openai import OpenAI

    client = OpenAI()
    examples = [
        "VPN-ip 10.15.7.42",
        "Как настроить почту в Outlook?",
        "Что такое принцип Security Champions и почему он важен?",
        "Дай список всех наших корпоративных бонусов на 2025 год",
    ]

    for q in examples:
        params = get_dynamic_params(client, q)
        print(f"→ '{q}' → {params}\n")



# Седлать на lagrfge можели и заливать сразу в два места в colab
# уточнить нужно ли в colab как то очистить форматировать текст и разделять роли user gpt чат
import logging, itertools, math, re, numpy as np
from openai import OpenAI
from rank_bm25 import BM25Okapi
from pathlib import Path
import faiss                   # тот же, что вы уже используете

logger = logging.getLogger(__name__)

# ────────────────────── 1. Загрузка индекса и вспомогательных структур
def _load_index_and_chunks():
    index = faiss.read_index("kb.index")
    chunks = Path("chunks.txt").read_text(encoding="utf-8").split("\n\n<<<DOCSEP>>>\n\n")
    # токенизированные варианты для BM25-гибрида
    tokenized_chunks = [c.lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized_chunks)
    return index, chunks, bm25

# ────────────────────── 2. MMR-диверсификация
def _mmr(qvec, cand_vecs, λ=0.6, top_k=10):
    """Maximal-Marginal-Relevance (cosine). cand_vecs — (N, D) ndarray"""
    selected, rest = [], list(range(len(cand_vecs)))
    sim_to_query = (cand_vecs @ qvec.T).ravel()
    # первая выборка — самый близкий
    selected.append(rest.pop(int(sim_to_query.argmax())))
    while len(selected) < top_k and rest:
        mmr_scores = [
            λ * sim_to_query[i] -
            (1 - λ) * max((cand_vecs[i] @ cand_vecs[j] / (
                np.linalg.norm(cand_vecs[i]) * np.linalg.norm(cand_vecs[j]))
               ) for j in selected)
            for i in rest
        ]
        selected.append(rest.pop(int(np.argmax(mmr_scores))))
    return selected

# ────────────────────── 3. (Необязательный) LLM-re-rank top-N
def _llm_rerank(client: OpenAI, query: str, candidates: list[str], top_k: int):
    msgs = [{"role": "system",
             "content": "Ты re-rank-модуль. Для каждого фрагмента верни число 0-100 — "
                        "насколько он полезен, одно число в отдельной строке."},
            {"role": "user", "content": query}]
    msgs.extend({"role": "assistant", "content": f"<doc{i}>{c}</doc{i}>"} for i, c in enumerate(candidates))
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=msgs,
        temperature=0.0
    ).choices[0].message.content
    scores = list(map(float, re.findall(r"\d+(?:\.\d+)?", res)))
    order = np.argsort(scores)[::-1][:top_k]
    return [candidates[i] for i in order]

# ────────────────────── 4. Главная функция
def ask(
    client: OpenAI,
    query: str,
    k: int = 10,
    *,
    hybrid: bool = True,        # BM25 + dense
    bm25_weight: float = 0.3,
    mmr: bool = True,
    mmr_lambda: float = 0.6,
    rerank: bool = True,
    rerank_pool: int = 20,
    token_budget: int = 2_000,  # макс. токенов контекста
):
    index, chunks, bm25 = _load_index_and_chunks()

    # 1) embedding запроса
    logger.debug(f"Embedding query «{query}» …")
    qvec = np.array(
        client.embeddings.create(
            model="text-embedding-3-large",   # тот же API, ↑ recall
            input=query).data[0].embedding,
        dtype="float32")[None, :]

    # 2) поиск
    dense_k = max(k * 4, rerank_pool)
    dense_scores, dense_idx = index.search(qvec, dense_k)  # cosine в FAISS
    dense_idx, dense_scores = dense_idx[0], dense_scores[0]

    if hybrid:
        # BM25-гибрид: берём суммы z-nормированных скорингов
        bm25_scores = bm25.get_scores(query.lower().split())
        # нормализуем
        bm25_scores = (bm25_scores - bm25_scores.mean()) / (bm25_scores.std() + 1e-9)
        d_scores = (dense_scores - dense_scores.mean()) / (dense_scores.std() + 1e-9)
        total_scores = (1 - bm25_weight) * d_scores + bm25_weight * bm25_scores[dense_idx]
        order = np.argsort(total_scores)[::-1]
        dense_idx, dense_scores = dense_idx[order], total_scores[order]

    # 3) MMR-diversity
    if mmr and len(dense_idx) > k:
        cand_vecs = index.reconstruct_n(int(dense_idx[0]), len(dense_idx))  # (N, D)
        selected = _mmr(qvec.squeeze(), cand_vecs, λ=mmr_lambda, top_k=k)
        dense_idx = dense_idx[selected]

    # 4) (опц.) LLM-re-rank
    top_pool_idx = dense_idx[:rerank_pool] if rerank else dense_idx[:k]
    candidates = [chunks[i] for i in top_pool_idx]
    if rerank:
        candidates = _llm_rerank(client, query, candidates, k)

    # 5) Adaptive token budget
    context_parts, used = [], 0
    for part in candidates:
        used += len(part) // 4  # очень грубая оценка токенов
        if used > token_budget:
            break
        context_parts.append(part)
    context = "\n\n---\n\n".join(context_parts)

    # 6) Генерация
    logger.debug("Запрашиваем ответ LLM…")
    chat = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": (
                "Ты эксперт-ассистент. Отвечай максимально точно, опираясь только "
                "на предоставленный контекст. Если не уверен — скажи, что ответа нет.")},
            {"role": "system", "name": "context", "content": context},
            {"role": "user", "content": query},
        ],
    )
    answer = chat.choices[0].message.content.strip()
    return answer