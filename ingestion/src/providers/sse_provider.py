from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models import DailyBar, InstrumentRecord


@dataclass
class SseFetchResult:
    records: list
    raw_path: Path
    sha256: str
    byte_size: int
    business_date: date | None = None


def _date(value) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    return None


def _number(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _symbol(row: dict) -> str | None:
    value = row.get("A_STOCK_CODE") or row.get("COMPANY_CODE") or row.get("SEC_CODE")
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits.zfill(6) if digits else None


class SseProvider:
    name = "SSE"
    priority = 10
    master_url = "https://query.sse.com.cn/sseQuery/commonQuery.do"
    quote_urls = (
        "https://yunhq.sse.com.cn:32042/v1/sh1/list/exchange/equity",
        "http://yunhq.sse.com.cn:32041/v1/sh1/list/exchange/equity",
    )

    def __init__(self, raw_dir: Path, timeout_seconds: int = 40):
        self.raw_dir = raw_dir
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36",
            "Referer": "https://www.sse.com.cn/",
            "Accept": "application/json,text/plain,*/*",
        })
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def _save_raw(self, dataset: str, payload, business_date: date | None = None) -> tuple[Path, str, int]:
        stamp = business_date or date.today()
        target_dir = self.raw_dir / "sse" / dataset / f"{stamp.year:04d}" / f"{stamp.month:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{stamp.isoformat()}.json"
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        target.write_bytes(content)
        return target, sha256(content).hexdigest(), len(content)

    def _fetch_stock_type(self, stock_type: str, company_status: str) -> dict:
        params = {
            "STOCK_TYPE": stock_type,
            "REG_PROVINCE": "",
            "CSRC_CODE": "",
            "STOCK_CODE": "",
            "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L",
            "COMPANY_STATUS": company_status,
            "type": "inParams",
            "isPagination": "true",
            "pageHelp.cacheSize": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.pageSize": "10000",
            "pageHelp.pageNo": "1",
            "pageHelp.endPage": "1",
        }
        response = self.session.get(self.master_url, params=params, timeout=(10, self.timeout_seconds))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get("result"), list):
            raise RuntimeError("SSE instrument API returned an unexpected payload")
        return payload

    @staticmethod
    def _instrument_from_row(row: dict, board: str, status: str) -> InstrumentRecord | None:
        symbol = _symbol(row)
        if not symbol:
            return None
        return InstrumentRecord(
            exchange="SSE",
            symbol=symbol,
            current_name=row.get("COMPANY_ABBR") or row.get("SEC_NAME_CN"),
            full_name=row.get("FULL_NAME") or row.get("COMPANY_FULL_NAME"),
            english_name=row.get("COMPANY_ABBR_EN"),
            board=board,
            list_date=_date(row.get("LIST_DATE")),
            delist_date=_date(row.get("DELIST_DATE")),
            status=status,
            region=row.get("AREA_NAME"),
            industry=row.get("CSRC_CODE_DESC") or row.get("CSRC_DESC"),
            source="SSE",
        )

    def fetch_instruments(self) -> SseFetchResult:
        payloads = {
            "main_a": self._fetch_stock_type("1", "2,4,5,7,8"),
            "star": self._fetch_stock_type("8", "2,4,5,7,8"),
        }
        records: dict[str, InstrumentRecord] = {}
        for key, board in (("main_a", "MAIN"), ("star", "STAR")):
            for row in payloads[key]["result"]:
                record = self._instrument_from_row(row, board, "LISTED")
                if record:
                    records[record.symbol] = record
        path, digest, size = self._save_raw("instrument", payloads)
        return SseFetchResult(list(records.values()), path, digest, size)

    def fetch_delisted(self) -> SseFetchResult:
        payloads = {
            "main_a": self._fetch_stock_type("1", "3"),
            "star": self._fetch_stock_type("8", "3"),
        }
        records: dict[str, InstrumentRecord] = {}
        for key, board in (("main_a", "MAIN"), ("star", "STAR")):
            for row in payloads[key]["result"]:
                record = self._instrument_from_row(row, board, "DELISTED")
                if record:
                    records[record.symbol] = record
        path, digest, size = self._save_raw("delisted", payloads)
        return SseFetchResult(list(records.values()), path, digest, size)

    def _fetch_quote_payload(self) -> tuple[dict, str]:
        params = {
            "select": "code,name,open,high,low,last,prev_close,chg_rate,volume,amount,tradephase,cpxxsubtype",
            "order": "",
            "begin": "0",
            "end": "5000",
            "_": str(int(time.time() * 1000)),
        }
        errors: list[str] = []
        for url in self.quote_urls:
            try:
                response = self.session.get(url, params=params, timeout=(10, self.timeout_seconds))
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload.get("list"), list):
                    raise RuntimeError("missing list")
                return payload, url
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        raise RuntimeError("SSE quote service unavailable: " + " | ".join(errors))

    def fetch_daily_snapshot(self) -> SseFetchResult:
        payload, endpoint = self._fetch_quote_payload()
        trade_date = _date(payload.get("date"))
        if trade_date is None:
            raise RuntimeError(f"SSE quote payload has invalid market date: {payload.get('date')!r}")

        records: list[DailyBar] = []
        for row in payload["list"]:
            if not isinstance(row, list) or len(row) < 11:
                continue
            symbol = str(row[0]).strip().zfill(6)
            subtype = str(row[11]).strip() if len(row) > 11 and row[11] is not None else None
            if not re.fullmatch(r"\d{6}", symbol):
                continue
            if subtype and subtype not in {"ASH", "KSH"}:
                continue
            records.append(DailyBar(
                exchange="SSE",
                symbol=symbol,
                trade_date=trade_date,
                source=self.name,
                source_priority=self.priority,
                pre_close=_number(row[6]),
                open=_number(row[2]),
                high=_number(row[3]),
                low=_number(row[4]),
                close=_number(row[5]),
                volume_shares=_int(row[8]),
                turnover_cny=_number(row[9]),
                pct_change=_number(row[7]),
                extra={
                    "name": row[1],
                    "trade_phase": row[10],
                    "security_subtype": subtype,
                },
            ))

        raw = {"endpoint": endpoint, "response": payload}
        path, digest, size = self._save_raw("stock_snapshot", raw, trade_date)
        return SseFetchResult(records, path, digest, size, trade_date)
