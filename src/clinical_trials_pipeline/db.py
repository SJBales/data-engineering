"""Supabase/Postgres connection helpers."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from clinical_trials_pipeline.config import PROJECT_ROOT


def get_engine() -> Engine:
    """Engine for the Supabase database named by SUPABASE_PROJECT_URL in .env."""
    load_dotenv(PROJECT_ROOT / ".env")
    return create_engine(os.environ["SUPABASE_PROJECT_URL"])


def run_sql_file(engine: Engine, path: Path) -> None:
    """Run a .sql file as-is. Files manage their own transaction (begin/commit),
    so the connection is in autocommit mode."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql(path.read_text())
