from __future__ import annotations

import sqlite3


PUBLIC_MESSAGES_FEATURE_ROWS = [
    ("publicmessages", "N\u1ed9i dung public", "baocaomoi", 39),
    ("public_messages.view", "Xem n\u1ed9i dung public", "publicmessages", 391),
    ("public_messages.manage", "Qu\u1ea3n tr\u1ecb n\u1ed9i dung public", "publicmessages", 392),
]


def ensure_public_messages_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS public_message_sender_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            sender_pattern TEXT COLLATE NOCASE NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_type, sender_pattern)
        );

        CREATE INDEX IF NOT EXISTS public_message_sender_rules_active_idx
        ON public_message_sender_rules (source_type, is_active, sender_pattern);
        """
    )
