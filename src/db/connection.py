"""
Database connection and session factory for UniResolve AI.

Settings are read from config/settings.yaml. Set DB_BACKEND=firestore to
store data in Google Cloud Firestore instead of SQL (used on Cloud Run).
"""
import os
from pathlib import Path

import yaml
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).parent.parent.parent


def _load_db_url() -> str:
    settings_path = BASE_DIR / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("database", {}).get("url", "sqlite:///./grievances.db")


DATABASE_URL = _load_db_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def using_firestore() -> bool:
    return os.getenv("DB_BACKEND", "sql").strip().lower() == "firestore"


def get_db():
    """FastAPI dependency that yields a DB session and ensures cleanup."""
    if using_firestore():
        from src.db.firestore_store import FirestoreSession

        db = FirestoreSession()
    else:
        db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables (called at application startup)."""
    if using_firestore():
        return
    from src.db.models import Base  # local import to avoid circular deps
    Base.metadata.create_all(bind=engine)
    migrations = {
        "ai_analyses": {"analysis_details": "TEXT"},
        "users": {"department": "VARCHAR(120)"},
        "human_decisions": {"resolution_solution": "TEXT"},
    }
    with engine.begin() as connection:
        for table, additions in migrations.items():
            existing = {column["name"] for column in inspect(engine).get_columns(table)}
            for column, column_type in additions.items():
                if column not in existing:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                    )
