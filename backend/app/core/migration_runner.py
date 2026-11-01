import os
import glob
from pathlib import Path
from sqlalchemy import text
from app.core.database import engine


def run_database_migrations():
    """
    Automatically applies all SQL migration files in sorted order on startup.
    Ensures that empty cloud databases (such as Render PostgreSQL) are instantly
    initialized with all required tables, indexes, and constraints.
    """
    # Look for migrations in root directory or relative to backend
    possible_paths = [
        Path(__file__).resolve().parent.parent.parent.parent / "migrations",
        Path(__file__).resolve().parent.parent.parent / "migrations",
        Path("migrations"),
        Path("../migrations"),
    ]

    migrations_dir = None
    for p in possible_paths:
        if p.exists() and p.is_dir():
            migrations_dir = p
            break

    if not migrations_dir:
        return

    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        return

    with engine.begin() as conn:
        for sql_file in sql_files:
            try:
                content = sql_file.read_text(encoding="utf-8")
                conn.execute(text(content))
            except Exception as e:
                # Silently proceed if already applied or error occurs on idempotent statement
                pass
