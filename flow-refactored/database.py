"""Database access layer using SQLAlchemy.

This module replaces direct psycopg2 usage with SQLAlchemy’s Engine and
Connection objects. It illustrates the Clean Code principle of keeping
functions small and focused: each method performs a single database
operation and clearly documents its intent. SQLAlchemy’s core API
provides safe parameter binding via the `text` function and allows
connection pooling.
"""

from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import Config


class Database:
    """Simple database wrapper built on SQLAlchemy.

    The constructor creates an `Engine` from the provided configuration. The
    engine handles connection pooling, and individual queries are executed
    using context managers to ensure proper cleanup. Methods are kept
    concise and return dictionaries for ease of use in the rest of the
    application.
    """

    def __init__(self, config: Config) -> None:
        self.engine: Engine = create_engine(config.database_url, future=True)

    def query_one(self, sql: str, params: Tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
        """Execute a SELECT returning a single row as a dictionary."""
        stmt = text(sql)
        with self.engine.connect() as conn:
            result = conn.execute(stmt, params)
            row = result.mappings().first()
            return dict(row) if row is not None else None

    def query_all(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT returning all rows as a list of dictionaries."""
        stmt = text(sql)
        with self.engine.connect() as conn:
            result = conn.execute(stmt, params)
            return [dict(row) for row in result.mappings().all()]

    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> None:
        """Execute an INSERT/UPDATE/DELETE and commit the transaction."""
        stmt = text(sql)
        with self.engine.begin() as conn:
            conn.execute(stmt, params)