import os
import glob
from pathlib import Path
from sqlalchemy import text
from app.core.database import engine


def run_migrations():
    """
    Simple SQL migration runner.
    Finds all .sql files in the migrations/ directory in order,
    checks the schema_migrations table, and applies unapplied scripts.
    """
    migrations_dir = Path(__file__).resolve().parent.parent.parent.parent / "migrations"
    sql_files = sorted(glob.glob(str(migrations_dir / "*.sql")))

    if not sql_files:
        print(f"No SQL migration files found in {migrations_dir}")
        return

    with engine.begin() as conn:
        # Create migrations tracking table if it doesn't exist
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                version VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
        """))

        # Fetch already applied migrations
        result = conn.execute(text("SELECT version FROM schema_migrations;"))
        applied_versions = {row[0] for row in result.fetchall()}

        # Apply pending migrations
        for file_path in sql_files:
            version = os.path.basename(file_path)
            if version in applied_versions:
                print(f"[SKIP] {version} (already applied)")
                continue

            print(f"[APPLYING] {version}...")
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()

            # Execute the migration inside the transaction
            conn.execute(text(sql_content))

            # Record that this migration was applied
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version);"),
                {"version": version}
            )
            print(f"[SUCCESS] {version} applied successfully.")


if __name__ == "__main__":
    run_migrations()
