"""SQLAlchemy setup. SQLite is the local/dev default; Postgres (+pgvector
in Docker Compose) is the deployed path — same models, same code.
PostgreSQL is the source of truth for metadata/clauses/audit; the vector
hash-embeddings and graph edges are derived stores rebuildable from it.
"""
import logging

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)


def normalize_database_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


effective_database_url = normalize_database_url(settings.database_url)
connect_args = {}
if effective_database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    logger.info("DATABASE_URL is SQLite — local/dev only; use Postgres for shared deployments.")

engine = create_engine(effective_database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    # Idempotently add columns for models that gained one after first create.
    try:
        inspector = inspect(engine)
        existing = {t: {c["name"] for c in inspector.get_columns(t)} for t in inspector.get_table_names()}
        with engine.begin() as conn:
            for table in Base.metadata.tables.values():
                cols = existing.get(table.name, set())
                for col in table.columns:
                    if col.name not in cols:
                        ctype = col.type.compile(dialect=engine.dialect)
                        default = ""
                        if col.default is not None and col.default.arg is not None:
                            v = col.default.arg
                            default = f" DEFAULT '{v}'" if isinstance(v, str) else f" DEFAULT {v}"
                        conn.execute(__import__("sqlalchemy").text(
                            f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ctype}{default}'))
    except Exception as exc:  # never break startup on a migration nicety
        logger.warning("init_db column sync skipped: %s", exc)
