"""
Database connection and session factory for UniResolve AI.

Settings are read from config/settings.yaml or DATABASE_URL env var.
"""
import os
import re
import time
from pathlib import Path

import yaml
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).parent.parent.parent


def _load_db_url() -> str:
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        # Strip potential wrapping quotes or psql command prefix
        env_url = env_url.strip("'\"")
        if env_url.startswith("psql "):
            env_url = env_url[5:].strip().strip("'\"")
        if env_url.startswith("postgres://"):
            env_url = env_url.replace("postgres://", "postgresql://", 1)

        # Remove channel_binding parameter which causes libpq/psycopg connection errors with Neon
        env_url = re.sub(r'([?&])channel_binding=[^&]*', '', env_url)
        env_url = re.sub(r'[?&]+$', '', env_url)
        if '?' not in env_url and '&' in env_url:
            env_url = env_url.replace('&', '?', 1)
        env_url = env_url.strip().strip("'\"")

        # Ensure sslmode=require for serverless PostgreSQL if not present
        if ("neon.tech" in env_url or "supabase.co" in env_url) and "sslmode=" not in env_url:
            separator = "&" if "?" in env_url else "?"
            env_url = f"{env_url}{separator}sslmode=require"
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

    # Retry connection in case of cloud database cold start
    max_retries = 3
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise e

    # Apply legacy column migrations safely without failing startup
    migrations = {
        "ai_analyses": {"analysis_details": "TEXT"},
        "users": {"department": "VARCHAR(120)"},
        "human_decisions": {"resolution_solution": "TEXT"},
    }
    try:
        with engine.begin() as connection:
            inspector = inspect(connection)
            for table, additions in migrations.items():
                if inspector.has_table(table):
                    existing = {col["name"] for col in inspector.get_columns(table)}
                    for column, column_type in additions.items():
                        if column not in existing:
                            try:
                                connection.execute(
                                    text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                                )
                            except Exception:
                                pass
    except Exception as e:
        print(f"Schema migration check note (non-fatal): {e}")
