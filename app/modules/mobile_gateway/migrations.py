from __future__ import annotations

import sqlite3


MOBILE_GATEWAY_FEATURE_ROWS = [
    ("mobilegateway", "Mobile Gateway", "quantriweb", 29),
    ("mobile_gateway.view", "Xem Mobile Gateway", "mobilegateway", 291),
    ("mobile_gateway.manage", "Quan tri Mobile Gateway", "mobilegateway", 292),
    ("mobile_gateway.devices.view", "Xem thiet bi Mobile", "mobilegateway", 293),
    ("mobile_gateway.devices.manage", "Quan tri thiet bi Mobile", "mobilegateway", 294),
    ("mobile_gateway.sms.view", "Xem SMS Mobile", "mobilegateway", 295),
    ("mobile_gateway.sms.view_content", "Xem noi dung SMS Mobile", "mobilegateway", 296),
    ("mobile_gateway.notifications.view", "Xem thong bao Mobile", "mobilegateway", 297),
    ("mobile_gateway.notifications.view_content", "Xem noi dung thong bao Mobile", "mobilegateway", 298),
    ("mobile_gateway.otp.view", "Xem OTP Mobile", "mobilegateway", 299),
    ("mobile_gateway.otp.manage", "Quan tri OTP Mobile", "mobilegateway", 300),
    ("mobile_gateway.commands.view", "Xem lenh Mobile", "mobilegateway", 301),
    ("mobile_gateway.commands.manage", "Gui lenh Mobile", "mobilegateway", 302),
    ("mobile_gateway.audit.view", "Xem nhat ky Mobile", "mobilegateway", 303),
    ("mobile_gateway.media.view", "Xem media Mobile", "mobilegateway", 304),
    ("mobile_gateway.media.manage", "Quan tri media Mobile", "mobilegateway", 305),
]


def _sqlite_column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in connection.execute(f"PRAGMA table_info({table})").fetchall())


def _sqlite_add_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if not _sqlite_column_exists(connection, table, column):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_mobile_gateway_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS mobile_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT 'android',
            manufacturer TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            android_version TEXT NOT NULL DEFAULT '',
            app_version TEXT NOT NULL DEFAULT '',
            encrypted_device_secret TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            paired_at TEXT,
            last_seen_at TEXT,
            last_ip TEXT NOT NULL DEFAULT '',
            revoked_at TEXT,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mobile_pairing_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_hash TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            used_by_device_id TEXT,
            policy_payload TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS mobile_device_nonces (
            device_id TEXT NOT NULL,
            nonce TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            PRIMARY KEY (device_id, nonce)
        );

        CREATE TABLE IF NOT EXISTS mobile_device_policies (
            device_id TEXT PRIMARY KEY,
            sms_enabled INTEGER NOT NULL DEFAULT 1,
            notifications_enabled INTEGER NOT NULL DEFAULT 0,
            clipboard_enabled INTEGER NOT NULL DEFAULT 0,
            camera_enabled INTEGER NOT NULL DEFAULT 0,
            diagnostics_enabled INTEGER NOT NULL DEFAULT 1,
            notification_allowlist TEXT NOT NULL DEFAULT '[]',
            heartbeat_interval_minutes INTEGER NOT NULL DEFAULT 15,
            sync_interval_minutes INTEGER NOT NULL DEFAULT 15,
            batch_size INTEGER NOT NULL DEFAULT 50,
            local_retention_days INTEGER NOT NULL DEFAULT 14,
            minimum_app_version TEXT NOT NULL DEFAULT '1.3.0',
            force_update INTEGER NOT NULL DEFAULT 0,
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mobile_device_heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            app_version TEXT NOT NULL DEFAULT '',
            android_version TEXT NOT NULL DEFAULT '',
            manufacturer TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            battery_percent INTEGER,
            charging INTEGER NOT NULL DEFAULT 0,
            network_type TEXT NOT NULL DEFAULT '',
            pending_sms INTEGER NOT NULL DEFAULT 0,
            pending_notifications INTEGER NOT NULL DEFAULT 0,
            sms_permission INTEGER NOT NULL DEFAULT 0,
            notification_access INTEGER NOT NULL DEFAULT 0,
            battery_optimization_ignored INTEGER NOT NULL DEFAULT 0,
            last_sms_received_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mobile_sms_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            normalized_sender TEXT NOT NULL,
            body_encrypted TEXT NOT NULL,
            body_masked TEXT NOT NULL DEFAULT '',
            received_at TEXT NOT NULL,
            subscription_id TEXT NOT NULL DEFAULT '',
            sim_slot INTEGER,
            synced_at TEXT NOT NULL,
            is_otp_candidate INTEGER NOT NULL DEFAULT 0,
            used_for_otp INTEGER NOT NULL DEFAULT 0,
            otp_request_id TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(device_id, external_id)
        );

        CREATE TABLE IF NOT EXISTS mobile_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            package_name TEXT NOT NULL,
            app_name TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            text_encrypted TEXT NOT NULL DEFAULT '',
            text_masked TEXT NOT NULL DEFAULT '',
            posted_at TEXT NOT NULL,
            used_for_otp INTEGER NOT NULL DEFAULT 0,
            otp_request_id TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(device_id, external_id)
        );

        CREATE TABLE IF NOT EXISTS mobile_commands (
            command_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            command_type TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            delivered_at TEXT,
            acknowledged_at TEXT,
            completed_at TEXT,
            sanitized_error TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS mobile_command_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            sanitized_error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mobile_diagnostics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            app_version TEXT NOT NULL DEFAULT '',
            android_version TEXT NOT NULL DEFAULT '',
            manufacturer TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            payload TEXT NOT NULL DEFAULT '{}',
            sanitized_error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mobile_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            command_id TEXT NOT NULL DEFAULT '',
            media_type TEXT NOT NULL,
            file_name TEXT NOT NULL DEFAULT '',
            mime_type TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0,
            captured_at TEXT,
            uploaded_at TEXT,
            drive_file_id TEXT NOT NULL DEFAULT '',
            drive_url TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS otp_configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_code TEXT NOT NULL UNIQUE,
            service_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            source_type TEXT NOT NULL DEFAULT 'sms',
            sender_pattern TEXT NOT NULL DEFAULT '',
            sender_match_type TEXT NOT NULL DEFAULT 'contains',
            package_pattern TEXT NOT NULL DEFAULT '',
            title_pattern TEXT NOT NULL DEFAULT '',
            otp_regex TEXT NOT NULL DEFAULT '(?<!\\d)(\\d{4,8})(?!\\d)',
            otp_keyword TEXT NOT NULL DEFAULT '',
            otp_length_min INTEGER NOT NULL DEFAULT 4,
            otp_length_max INTEGER NOT NULL DEFAULT 8,
            wait_timeout_seconds INTEGER NOT NULL DEFAULT 120,
            validity_seconds INTEGER NOT NULL DEFAULT 180,
            device_id TEXT NOT NULL DEFAULT '',
            sim_slot INTEGER,
            auto_fill_enabled INTEGER NOT NULL DEFAULT 1,
            manual_fallback_enabled INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS otp_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL UNIQUE,
            service_code TEXT NOT NULL,
            job_id TEXT NOT NULL DEFAULT '',
            configuration_id INTEGER,
            source_type TEXT NOT NULL DEFAULT 'sms',
            requested_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            matched_source_type TEXT,
            matched_source_id TEXT,
            matched_at TEXT,
            consumed_at TEXT,
            cancelled_at TEXT,
            failure_code TEXT,
            code_encrypted TEXT NOT NULL DEFAULT '',
            code_masked TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS otp_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT '',
            source_id TEXT NOT NULL DEFAULT '',
            details TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS otp_filter_configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filter_id TEXT NOT NULL UNIQUE,
            rule_name TEXT NOT NULL,
            service_code TEXT NOT NULL DEFAULT 'onebss',
            sender_pattern TEXT NOT NULL DEFAULT '',
            sender_match_type TEXT NOT NULL DEFAULT 'contains',
            otp_length INTEGER NOT NULL DEFAULT 6,
            start_prefix TEXT NOT NULL DEFAULT '',
            validity_seconds INTEGER NOT NULL DEFAULT 60,
            enabled INTEGER NOT NULL DEFAULT 1,
            device_id TEXT NOT NULL DEFAULT '',
            sim_slot INTEGER,
            priority INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS otp_latest_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filter_id TEXT NOT NULL DEFAULT '',
            service_code TEXT NOT NULL DEFAULT '',
            rule_name TEXT NOT NULL DEFAULT '',
            sender TEXT NOT NULL DEFAULT '',
            code_masked TEXT NOT NULL DEFAULT '',
            received_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'valid',
            source_type TEXT NOT NULL DEFAULT '',
            source_id TEXT NOT NULL DEFAULT '',
            otp_request_id TEXT NOT NULL DEFAULT '',
            used_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS mobile_devices_active_idx ON mobile_devices (is_active, last_seen_at);
        CREATE INDEX IF NOT EXISTS mobile_sms_received_idx ON mobile_sms_messages (received_at DESC);
        CREATE INDEX IF NOT EXISTS mobile_sms_otp_idx ON mobile_sms_messages (is_otp_candidate, used_for_otp, received_at DESC);
        CREATE INDEX IF NOT EXISTS mobile_notifications_posted_idx ON mobile_notifications (posted_at DESC);
        CREATE INDEX IF NOT EXISTS mobile_commands_device_status_idx ON mobile_commands (device_id, status, expires_at);
        CREATE INDEX IF NOT EXISTS mobile_media_device_idx ON mobile_media (device_id, uploaded_at DESC);
        CREATE INDEX IF NOT EXISTS otp_requests_status_idx ON otp_requests (status, service_code, expires_at);
        CREATE INDEX IF NOT EXISTS otp_filters_service_idx ON otp_filter_configurations (service_code, enabled, priority);
        CREATE INDEX IF NOT EXISTS otp_latest_values_filter_idx ON otp_latest_values (filter_id, received_at DESC);
        """
    )
    _sqlite_add_column(connection, "mobile_pairing_codes", "policy_payload", "TEXT NOT NULL DEFAULT '{}'")
    _sqlite_add_column(connection, "mobile_device_policies", "camera_enabled", "INTEGER NOT NULL DEFAULT 0")

    now = "1970-01-01T00:00:00+00:00"
    connection.execute(
        """
        INSERT OR IGNORE INTO otp_configurations
        (service_code, service_name, enabled, source_type, sender_pattern, sender_match_type,
         otp_regex, wait_timeout_seconds, validity_seconds, auto_fill_enabled, manual_fallback_enabled,
         priority, created_at, updated_at)
        VALUES ('onebss', 'OneBSS', 1, 'sms', 'VNPT', 'contains',
                '(?<!\\d)(\\d{4,8})(?!\\d)', 120, 180, 1, 1, 10, ?, ?)
        """,
        (now, now),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO otp_filter_configurations
        (filter_id, rule_name, service_code, sender_pattern, sender_match_type, otp_length,
         start_prefix, validity_seconds, enabled, priority, created_at, updated_at)
        VALUES ('onebss', 'OneBSS mac dinh', 'onebss', '293', 'contains', 6,
                '1364', 60, 1, 10, ?, ?)
        """,
        (now, now),
    )
