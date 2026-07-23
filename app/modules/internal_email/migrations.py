from __future__ import annotations

import sqlite3


INTERNAL_EMAIL_FEATURE_ROWS = [
    ("internalemail", "Mail noi bo", "quantriweb", 29),
    ("internal_email.view", "Xem Mail noi bo", "internalemail", 281),
    ("internal_email.manage", "Quan tri Mail noi bo", "internalemail", 282),
]


def ensure_internal_email_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS internal_email_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_key TEXT NOT NULL DEFAULT 'internal_email',
            mailbox TEXT NOT NULL DEFAULT 'INBOX',
            uid TEXT NOT NULL,
            message_id TEXT NOT NULL DEFAULT '',
            sender TEXT NOT NULL DEFAULT '',
            sender_email TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            body_masked TEXT NOT NULL DEFAULT '',
            received_at TEXT NOT NULL,
            synced_at TEXT NOT NULL,
            is_otp_candidate INTEGER NOT NULL DEFAULT 0,
            otp_code_masked TEXT NOT NULL DEFAULT '',
            otp_service_code TEXT NOT NULL DEFAULT '',
            otp_request_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(account_key, mailbox, uid)
        );

        CREATE INDEX IF NOT EXISTS internal_email_messages_received_idx
        ON internal_email_messages (received_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS internal_email_messages_otp_idx
        ON internal_email_messages (is_otp_candidate, received_at DESC);
        """
    )
