"""Prefect orchestration over the existing, checkpoint-aware ingestion services.

Prefect owns orchestration and task-level state. PostgreSQL ingestion_run remains
the durable source-level progress/checkpoint store; never rely on Prefect result
caching to skip market data.
"""
from datetime import date

from prefect import flow, get_run_logger, task

from .config import Settings
from .database import Database
from .ingestion import IngestionService
from .providers import SseProvider, SzseProvider


def _service() -> IngestionService:
    settings = Settings.from_env()
    db = Database(settings.database_url)
    db.migrate()
    return IngestionService(
        db,
        SzseProvider(settings.raw_data_dir, settings.http_timeout_seconds),
        SseProvider(settings.raw_data_dir, settings.http_timeout_seconds),
    )


def _exchange_list(exchange: str) -> tuple[str, ...]:
    exchange = exchange.upper()
    if exchange == "ALL":
        return ("SZSE", "SSE")
    if exchange in {"SZSE", "SSE"}:
        return (exchange,)
    raise ValueError(f"Unsupported exchange: {exchange}")


@task(name="market-master", task_run_name="master-{exchange}",
      retries=1, retry_delay_seconds=30, persist_result=False)
def master_task(exchange: str) -> dict:
    service = _service()
    if exchange == "SZSE":
        result = service.sync_szse_master()
    elif exchange == "SSE":
        result = service.sync_sse_master()
    else:
        raise ValueError(f"Unsupported exchange: {exchange}")
    get_run_logger().info("%s master imported: %s", exchange, result)
    return result


@task(name="market-daily", task_run_name="daily-{exchange}",
      retries=1, retry_delay_seconds=30, persist_result=False)
def daily_task(exchange: str, trade_date: date | None = None) -> dict:
    service = _service()
    if exchange == "SZSE":
        if trade_date is None:
            raise ValueError("SZSE requires an explicit snapshot date")
        result = {"date": trade_date.isoformat(), "rows": service.sync_szse_daily(trade_date)}
    elif exchange == "SSE":
        # SSE provides its own latest market date; do not pretend a requested date is supported.
        result = service.sync_sse_daily()
    else:
        raise ValueError(f"Unsupported exchange: {exchange}")
    get_run_logger().info("%s daily snapshot: %s", exchange, result)
    if result["rows"] == 0:
        get_run_logger().warning("Zero accepted rows is NOT proof of a market holiday.")
    return result


@task(name="baostock-history", task_run_name="history-{exchange}", persist_result=False)
def history_task(start: date, end: date, exchange: str = "SZSE",
                 codes: list[str] | None = None, batch_size: int = 50,
                 delay_seconds: float = 0.3, retries: int = 2,
                 force: bool = False) -> dict:
    # Existing per-symbol retries + durable SUCCESS checkpoints stay authoritative.
    result = _service().bootstrap_baostock(
        start, end, set(codes) if codes else None, batch_size,
        exchange=exchange, resume=not force,
        retries=retries, delay_seconds=delay_seconds,
    )
    get_run_logger().info("%s history batch: %s", exchange, result)
    if result["failed_instruments"]:
        symbols = ", ".join(f["symbol"] for f in result["failures"][:10])
        raise RuntimeError(
            f"BaoStock {exchange}: {result['failed_instruments']} instruments failed "
            f"({symbols}); successful symbols remain checkpointed. Re-run same window."
        )
    return result


@task(name="szse-date-range", persist_result=False)
def szse_range_task(start: date, end: date, batch_size: int = 30,
                    delay_seconds: float = 1.0, force: bool = False,
                    retry_empty: bool = False) -> dict:
    result = _service().sync_szse_range(
        start, end, batch_size=batch_size, delay_seconds=delay_seconds,
        force=force, retry_empty=retry_empty,
    )
    get_run_logger().info("SZSE range batch: %s", result)
    if result["failed_dates"]:
        days = ", ".join(item["date"] for item in result["failed_dates"][:10])
        raise RuntimeError(
            f"SZSE snapshot failed on {len(result['failed_dates'])} dates ({days}); "
            "successfully imported dates remain checkpointed."
        )
    return result


@flow(name="stock-market-master", log_prints=True, persist_result=False)
def market_master_flow(exchange: str = "ALL") -> dict:
    results = {}
    failures = []
    for item in _exchange_list(exchange):
        try:
            results[item] = master_task(item)
        except Exception:
            get_run_logger().exception("Failed to synchronize %s master", item)
            failures.append(item)
    if failures:
        raise RuntimeError(f"Master synchronization failed: {', '.join(failures)}")
    return results


@flow(name="stock-market-daily", log_prints=True, persist_result=False)
def market_daily_flow(szse_date: date, sync_master: bool = True) -> dict:
    """Synchronize both markets. One exchange failing won't prevent the other."""
    results = {}
    failures = []
    for exchange in ("SZSE", "SSE"):
        try:
            if sync_master:
                master_task(exchange)
            results[exchange] = daily_task(exchange, szse_date if exchange == "SZSE" else None)
        except Exception:
            get_run_logger().exception("Failed to synchronize %s daily", exchange)
            failures.append(exchange)
    if failures:
        raise RuntimeError(f"Daily synchronization failed: {', '.join(failures)}")
    return results


@flow(name="stock-baostock-history", log_prints=True, persist_result=False)
def market_history_flow(start: date, end: date, exchange: str = "SZSE",
                        codes: list[str] | None = None, batch_size: int = 50,
                        delay_seconds: float = 0.3, retries: int = 2,
                        force: bool = False) -> dict:
    if exchange not in {"SSE", "SZSE"}:
        raise ValueError(f"Unsupported exchange: {exchange}")
    return history_task(start, end, exchange, codes, batch_size, delay_seconds, retries, force)


@flow(name="stock-szse-date-range", log_prints=True, persist_result=False)
def market_szse_range_flow(start: date, end: date, batch_size: int = 30,
                           delay_seconds: float = 1.0, force: bool = False,
                           retry_empty: bool = False) -> dict:
    return szse_range_task(start, end, batch_size, delay_seconds, force, retry_empty)
