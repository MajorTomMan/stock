from datetime import date
import time

import baostock as bs

from ..models import DailyBar
from .base import DailyMarketProvider


def _float(value: str) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def _int(value: str) -> int | None:
    value = (value or "").strip()
    return int(float(value)) if value else None


class BaoStockProvider(DailyMarketProvider):
    name = "BAOSTOCK"
    priority = 50

    LOGIN_ATTEMPTS = 4

    def __enter__(self):
        self._login_with_retry("login")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            bs.logout()
        except Exception:
            # A dropped connection can also cause logout to fail; do not mask
            # an earlier per-stock failure or a successful import.
            pass

    def _login_with_retry(self, action: str) -> None:
        """Retry transient login errors before starting or resuming a batch."""
        last_error: Exception | None = None
        for attempt in range(1, self.LOGIN_ATTEMPTS + 1):
            try:
                result = bs.login()
                if result is not None and result.error_code == "0":
                    return
                code = getattr(result, "error_code", "NO_RESPONSE")
                message = getattr(result, "error_msg", "BaoStock returned no login result")
                last_error = RuntimeError(f"{code} {message}")
            except Exception as exc:
                last_error = exc
            if attempt == self.LOGIN_ATTEMPTS:
                break
            delay = min(2 ** attempt, 8)
            print(
                f"[BAOSTOCK] {action} attempt {attempt}/{self.LOGIN_ATTEMPTS} failed: "
                f"{last_error}; retry in {delay}s",
                flush=True,
            )
            try:
                bs.logout()
            except Exception:
                pass
            time.sleep(delay)
        raise RuntimeError(
            f"BaoStock {action} failed after {self.LOGIN_ATTEMPTS} attempts: {last_error}. "
            "Previously completed stocks remain stored; retry the same command later."
        ) from last_error

    def reconnect(self) -> None:
        """Renew the BaoStock login after a transient network/session error."""
        try:
            bs.logout()
        except Exception:
            pass
        self._login_with_retry("reconnect")

    @staticmethod
    def _code(symbol: str) -> str:
        return f"sz.{symbol}"

    def fetch_daily(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
        result = bs.query_history_k_data_plus(
            self._code(symbol),
            fields,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            frequency="d",
            adjustflag="3",
        )
        if result.error_code != "0":
            raise RuntimeError(f"BaoStock query failed for {symbol}: {result.error_code} {result.error_msg}")

        bars: list[DailyBar] = []
        while result.next():
            row = dict(zip(result.fields, result.get_row_data()))
            bars.append(
                DailyBar(
                    exchange="SZSE",
                    symbol=symbol,
                    trade_date=date.fromisoformat(row["date"]),
                    source=self.name,
                    source_priority=self.priority,
                    pre_close=_float(row["preclose"]),
                    open=_float(row["open"]),
                    high=_float(row["high"]),
                    low=_float(row["low"]),
                    close=_float(row["close"]),
                    volume_shares=_int(row["volume"]),
                    turnover_cny=_float(row["amount"]),
                    pct_change=_float(row["pctChg"]),
                    trade_status=_int(row["tradestatus"]),
                    is_st=bool(_int(row["isST"])) if (row.get("isST") or "").strip() else None,
                    extra={"turnover_rate": _float(row["turn"]), "adjust_flag": row["adjustflag"]},
                )
            )
        return bars
