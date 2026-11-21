import os
from contextlib import contextmanager
from contextvars import ContextVar
from sqlalchemy import URL, create_engine

engine = create_engine(
    URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    ),
    pool_pre_ping=True,
)


# Authentication and stock GET dependencies cannot write to the operational database.
def connection():
    with engine.connect() as conn:
        with conn.begin():
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            yield conn


_transaction = ContextVar("factory_transaction", default=None)


# Nested service calls share one connection with savepoints; benchmark rollback spans every step.
@contextmanager
def transaction():
    existing = _transaction.get()
    if existing is not None:
        with existing.begin_nested():
            yield existing
        return
    with engine.begin() as conn:
        token = _transaction.set(conn)
        try:
            yield conn
        finally:
            _transaction.reset(token)
