from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_access.supabase_repository import SupabaseRepository
from app.settings import get_settings


TABLES = [
    ("users", "id"),
    ("audit_logs", "id"),
    ("website_catalog", "id"),
    ("features", "code"),
    ("user_permissions", None),
    ("web_credentials", "id"),
]


def main() -> None:
    settings = get_settings()
    sqlite_path = Path(settings.app_database_path)
    if not sqlite_path.exists():
        raise SystemExit(f"Khong tim thay SQLite DB: {sqlite_path}")

    supabase = SupabaseRepository(
        settings.supabase_rest_url,
        settings.supabase_secret_key.get_secret_value(),
    )

    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        for table_name, conflict_column in TABLES:
            rows = [dict(row) for row in connection.execute(f"SELECT * FROM {table_name}").fetchall()]
            if not rows:
                print(f"{table_name}: 0 rows")
                continue
            if conflict_column:
                for row in rows:
                    supabase._upsert(table_name, row, conflict_column)
            else:
                # user_permissions co khoa chinh kep, dung insert bo qua duplicate tu Postgres.
                for row in rows:
                    try:
                        supabase._post(table_name, row, {"Prefer": "return=minimal"})
                    except Exception as error:
                        if "duplicate" not in str(error).lower():
                            raise
            print(f"{table_name}: migrated {len(rows)} rows")


if __name__ == "__main__":
    main()
