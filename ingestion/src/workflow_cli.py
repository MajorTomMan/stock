"""Run Prefect-managed market-data flows without deploying a Prefect server.

Run from ingestion/: python -m stock_data.workflow_cli <command> [options]
"""
import argparse
import json
from datetime import date

from .cli import _normalize_code, _parse_date
from .flows import (
    market_daily_flow,
    market_history_flow,
    market_master_flow,
    market_szse_range_flow,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prefect market-data workflows")
    sub = parser.add_subparsers(dest="command", required=True)

    master = sub.add_parser("master", help="Synchronize current SSE/SZSE security master data")
    master.add_argument("--exchange", choices=["ALL", "SZSE", "SSE"], default="ALL")

    daily = sub.add_parser("daily", help="Sync official snapshots; SSE uses provider-reported latest date")
    daily.add_argument("--date", required=True, type=_parse_date,
                       help="Requested SZSE snapshot date (YYYY-MM-DD)")
    daily.add_argument("--skip-master", action="store_true",
                       help="Use already imported security master data")

    history = sub.add_parser("history", help="One resumable BaoStock history batch")
    history.add_argument("--exchange", choices=["SZSE", "SSE"], default="SZSE")
    history.add_argument("--start", type=_parse_date,
                         help="Default: SZSE 1991-01-01, SSE 1990-12-19")
    history.add_argument("--end", required=True, type=_parse_date)
    history.add_argument("--codes", nargs="*")
    history.add_argument("--batch-size", type=int, default=50)
    history.add_argument("--delay", type=float, default=0.3)
    history.add_argument("--retries", type=int, default=2,
                         help="Existing retries per stock (not Prefect batch retries)")
    history.add_argument("--force", action="store_true",
                         help="Ignore successful per-symbol checkpoints")

    snapshot_range = sub.add_parser("szse-range", help="One resumable SZSE date-range batch")
    snapshot_range.add_argument("--start", required=True, type=_parse_date)
    snapshot_range.add_argument("--end", required=True, type=_parse_date)
    snapshot_range.add_argument("--batch-size", type=int, default=30)
    snapshot_range.add_argument("--delay", type=float, default=1.0)
    snapshot_range.add_argument("--retry-empty", action="store_true")
    snapshot_range.add_argument("--force", action="store_true")

    args = parser.parse_args()
    if args.command == "master":
        result = market_master_flow(args.exchange)
    elif args.command == "daily":
        result = market_daily_flow(args.date, sync_master=not args.skip_master)
    elif args.command == "history":
        start = args.start or date.fromisoformat(
            "1990-12-19" if args.exchange == "SSE" else "1991-01-01"
        )
        codes = sorted({_normalize_code(value) for value in args.codes}) if args.codes else None
        result = market_history_flow(
            start, args.end, args.exchange, codes, args.batch_size,
            args.delay, args.retries, args.force,
        )
    else:
        result = market_szse_range_flow(
            args.start, args.end, args.batch_size,
            args.delay, args.force, args.retry_empty,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
