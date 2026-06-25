from __future__ import annotations

import argparse
import sys

from app.application.database_service import DatabaseService
from app.data_access.internal_api_client import InternalApiClient
from app.data_access.repository_factory import build_repository
from app.settings import get_settings


def refresh_cache(dry_run: bool = False, page_id: str | None = None, fail_on_error: bool = False) -> int:
    settings = get_settings()
    repository = build_repository(settings)
    service = DatabaseService(InternalApiClient(settings), repository)

    result = service.refresh_dashboard_chart_cache(page_id=page_id, dry_run=dry_run)
    for item in result["results"]:
        prefix = "OK" if item["ok"] else "ERROR"
        print(
            f"{prefix} {item['report_name']} [{item['chart_key']}]: "
            f"{item['row_count']} rows in {item['duration_ms']} ms"
        )
        if not item["ok"]:
            print(f"  {item.get('message')}")
    print(
        "Summary: "
        f"refreshed={result['refreshed']}, "
        f"failed={result['failed']}, "
        f"skipped={result['skipped']}, "
        f"deleted_stale={result.get('deleted_stale', 0)}, "
        f"dry_run={result['dry_run']}"
    )
    return 1 if result["failed"] and fail_on_error else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh cached dashboard chart data.")
    parser.add_argument("--dry-run", action="store_true", help="Run source queries without saving cache rows.")
    parser.add_argument("--page-id", help="Only refresh one dashboard page_id.")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit with code 1 if any chart fails.")
    args = parser.parse_args()
    return refresh_cache(dry_run=args.dry_run, page_id=args.page_id, fail_on_error=args.fail_on_error)


if __name__ == "__main__":
    sys.exit(main())
