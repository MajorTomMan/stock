import argparse
import json
from datetime import date

from .config import Settings
from .database import Database
from .ingestion import IngestionService
from .providers import SzseProvider


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _normalize_code(value: str) -> str:
    return value.upper().replace(".SZ", "").strip().zfill(6)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock market-data ingestion CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate")
    sub.add_parser("sync-szse-master")

    daily = sub.add_parser("sync-szse-daily")
    daily.add_argument("--date", required=True, type=_parse_date)

    bootstrap = sub.add_parser("bootstrap-baostock")
    bootstrap.add_argument("--start", default="1991-01-01", type=_parse_date)
    bootstrap.add_argument("--end", required=True, type=_parse_date)
    bootstrap.add_argument("--codes", nargs="*")
    bootstrap.add_argument("--limit", "--batch-size", dest="limit", type=int, default=50,
                           help="Process at most N pending stocks in this invocation (default: 50)")
    bootstrap.add_argument("--force", action="store_true", help="Ignore SUCCESS checkpoints and re-import")
    bootstrap.add_argument("--retries", type=int, default=2, help="Retries per failed symbol (default: 2)")
    bootstrap.add_argument("--delay", type=float, default=0.3, help="Seconds between symbols (default: 0.3)")

    args = parser.parse_args()
    settings = Settings.from_env()
    db = Database(settings.database_url)
    db.migrate()

    if args.command == "migrate":
        print("database migrations applied")
        return

    szse = SzseProvider(settings.raw_data_dir, settings.http_timeout_seconds)
    service = IngestionService(db, szse)

    if args.command == "sync-szse-master":
        print(json.dumps(service.sync_szse_master(), ensure_ascii=False, indent=2))
        return

    if args.command == "sync-szse-daily":
        count = service.sync_szse_daily(args.date)
        print(json.dumps({"date": args.date.isoformat(), "rows": count}, ensure_ascii=False, indent=2))
        return

    if args.command == "bootstrap-baostock":
        codes = {_normalize_code(code) for code in args.codes} if args.codes else None
        result = service.bootstrap_baostock(
            args.start, args.end, codes, args.limit,
            resume=not args.force, retries=args.retries, delay_seconds=args.delay,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
