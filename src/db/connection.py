"""
Database connection and session factory for UniResolve AI.

Settings are read from config/settings.yaml or DATABASE_URL env var.
"""
import os
from pathlib import Path

import yaml
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).parent.parent.parent


def _load_db_url() -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        if env_url.startswith("postgres://"):
            env_url = env_url.replace("postgres://", "postgresql://", 1)
        return env_url
    settings_path = BASE_DIR / "config" / "settings.yaml"
    if settings_path.exists():
        with open(settings_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("database", {}).get("url", "sqlite:///./grievances.db")
    return "sqlite:///./grievances.db"


DATABASE_URL = _load_db_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables (called at application startup)."""
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
