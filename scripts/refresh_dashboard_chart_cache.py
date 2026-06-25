from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Iterator

from app.application.database_service import DatabaseService
from app.data_access.internal_api_client import InternalApiClient
from app.data_access.repository_factory import build_repository
from app.settings import get_settings


def iter_cacheable_widgets(
    service: DatabaseService,
    page_id_filter: str | None = None,
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    layouts = service.app_repository.list_dashboard_layouts()
    for layout_summary in layouts:
        page_id = str(layout_summary.get("page_id") or "").strip()
        if page_id_filter and page_id != page_id_filter:
            continue
        layout_row = service.app_repository.get_dashboard_layout(page_id)
        layout = layout_row.get("layout") if layout_row else {}
        for tab in layout.get("tabs") if isinstance(layout.get("tabs"), list) else []:
            tab_id = str(tab.get("tab_id") or "").strip()
            for row in tab.get("grid_layout") or []:
                row_id = row.get("row_id")
                for widget in row.get("widgets") or []:
                    sql_code = str(widget.get("sql_code") or "").strip().upper()
                    if not sql_code:
                        continue
                    filters = widget.get("filters") if isinstance(widget.get("filters"), dict) else {}
                    metadata = service.dashboard_widget_cache_metadata(
                        page_id=page_id,
                        tab_id=tab_id,
                        row_id=row_id,
                        widget=widget,
                        sql_code=sql_code,
                        filters=filters,
                    )
                    if metadata:
                        yield metadata, widget


def refresh_cache(dry_run: bool = False, page_id: str | None = None, fail_on_error: bool = False) -> int:
    settings = get_settings()
    repository = build_repository(settings)
    service = DatabaseService(InternalApiClient(settings), repository)

    refreshed = 0
    failed = 0
    seen_chart_keys: set[str] = set()
    for metadata, widget in iter_cacheable_widgets(service, page_id_filter=page_id):
        chart_key = metadata["chart_key"]
        if chart_key in seen_chart_keys:
            continue
        seen_chart_keys.add(chart_key)

        started = time.perf_counter()
        result = service.run_dynamic_report(
            ma_bao_cao=metadata["sql_code"],
            filters=metadata.get("filters") or {},
            page=1,
            page_size=50,
            report_id=metadata.get("report_id"),
            report_name=metadata.get("report_name") or widget.get("title"),
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        label = f"{metadata.get('report_name') or metadata['sql_code']} [{chart_key}]"
        if not result.get("ok"):
            failed += 1
            print(f"ERROR {label}: {result.get('message')}")
            continue
        if not dry_run:
            service.save_dashboard_chart_cache(metadata, result, duration_ms=duration_ms)
        refreshed += 1
        print(f"OK {label}: {len(result.get('rows') or [])} rows in {duration_ms} ms")

    print(f"Summary: refreshed={refreshed}, failed={failed}, dry_run={dry_run}")
    return 1 if failed and fail_on_error else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh cached dashboard chart data.")
    parser.add_argument("--dry-run", action="store_true", help="Run source queries without saving cache rows.")
    parser.add_argument("--page-id", help="Only refresh one dashboard page_id.")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit with code 1 if any chart fails.")
    args = parser.parse_args()
    return refresh_cache(dry_run=args.dry_run, page_id=args.page_id, fail_on_error=args.fail_on_error)


if __name__ == "__main__":
    sys.exit(main())
