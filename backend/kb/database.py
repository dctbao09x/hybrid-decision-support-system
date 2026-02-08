# backend/kb/database.py
"""
Database connection and session management (Production-ready)
"""

import os
from contextlib import contextmanager
from typing import Iterator
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# ================= CONFIG =================

DB_ENV = os.getenv("APP_ENV", "dev")  # dev | test | prod

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./career_kb.db" if DB_ENV == "dev"
    else "sqlite:///./career_kb_prod.db"
)

SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"


# ================= ENGINE =================

engine_kwargs = {
    "echo": SQL_ECHO,
    "future": True,
    "pool_pre_ping": True
}

# SQLite special config
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {
        "check_same_thread": False
    }
else:
    # For PostgreSQL/MySQL
    engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", 10)),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 20)),
        "pool_timeout": 30,
        "pool_recycle": 1800
    })


engine = create_engine(
    DATABASE_URL,
    **engine_kwargs
)


# ================= SESSION =================

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session
)


# ================= DEPENDENCY =================

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Iterator[Session]:

    """
    Context manager for scripts / CLI
    """
    db = SessionLocal()

    try:
        yield db
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ================= INIT / HEALTH =================

def check_db_connection() -> bool:
    """
    Check DB health
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def init_db() -> None:
    """
    Create all tables
    """
    from .models import Base

    if not check_db_connection():
        raise RuntimeError("Database connection failed")

    Base.metadata.create_all(bind=engine)

    print("✓ Database initialized")


def reset_db(confirm: bool = False) -> None:
    """
    Reset DB (dangerous)
    """
    if not confirm:
        raise RuntimeError("reset_db(confirm=True) required")

    from .models import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    print("✓ Database reset completed")
