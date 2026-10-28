from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models import DailyBar, InstrumentRecord, NameChangeRecord


@dataclass
class FetchResult:
    records: list
    raw_path: Path
    sha256: str
    byte_size: int


def _text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _symbol(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    return digits.zfill(6) if digits else None


def _number(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).replace(",", "").strip()
    if not text or text in {"--", "-"}:
        return None
    return float(text)


def _date(value) -> date | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _is_a_share(symbol: str | None) -> bool:
    return bool(symbol and symbol[0] in {"0", "3"})


class SzseProvider:
    name = "SZSE"
    priority = 10
    base_url = "https://www.szse.cn/api/report/ShowReport"

    def __init__(self, raw_dir: Path, timeout_seconds: int = 40):
        self.raw_dir = raw_dir
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36",
            "Referer": "https://www.szse.cn/market/trend/index.html",
            "Accept": "*/*",
        })
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            status=4,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _fetch(self, dataset: str, catalog_id: str, tab_key: str, params: dict, business_date: date | None = None) -> tuple[pd.DataFrame, Path, str, int]:
        query = {"SHOWTYPE": "xlsx", "CATALOGID": catalog_id, "TABKEY": tab_key, **params}
        response = self.session.get(self.base_url, params=query, timeout=(10, self.timeout_seconds))
        response.raise_for_status()
        content = response.content
        if not content.startswith(b"PK"):
            raise RuntimeError(f"SZSE {dataset} did not return XLSX: {response.headers.get('Content-Type')}")

        stamp = business_date or date.today()
        target_dir = self.raw_dir / "szse" / dataset / f"{stamp.year:04d}" / f"{stamp.month:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{stamp.isoformat()}.xlsx"
        target.write_bytes(content)
        digest = sha256(content).hexdigest()
        frame = pd.read_excel(BytesIO(content))
        return frame, target, digest, len(content)

    def fetch_instruments(self) -> FetchResult:
        frame, path, digest, size = self._fetch("instrument", "1110", "tab1", {})
        records: list[InstrumentRecord] = []
        for _, row in frame.iterrows():
            symbol = _symbol(row.get("A股代码"))
            if not symbol:
                continue
            records.append(InstrumentRecord(
                exchange="SZSE",
                symbol=symbol,
                current_name=_text(row.get("A股简称")),
                full_name=_text(row.get("公司全称")),
                english_name=_text(row.get("英文名称")),
                board=_text(row.get("板块")),
                list_date=_date(row.get("A股上市日期")),
                status="LISTED",
                registered_address=_text(row.get("注册地址")),
                region=_text(row.get("地区")),
                province=_text(row.get("省份")),
                city=_text(row.get("城市")),
                industry=_text(row.get("所属行业")),
                website=_text(row.get("公司网址")),
                source=self.name,
            ))
        return FetchResult(records, path, digest, size)

    def fetch_delisted(self) -> FetchResult:
        frame, path, digest, size = self._fetch("delisted", "1793_ssgs", "tab2", {})
        records: list[InstrumentRecord] = []
        for _, row in frame.iterrows():
            symbol = _symbol(row.get("证券代码"))
            if not _is_a_share(symbol):
                continue
            records.append(InstrumentRecord(
                exchange="SZSE",
                symbol=symbol,
                current_name=_text(row.get("证券简称")),
                list_date=_date(row.get("上市日期")),
                delist_date=_date(row.get("终止上市日期")),
                status="DELISTED",
                source=self.name,
            ))
        return FetchResult(records, path, digest, size)

    def fetch_name_changes(self) -> FetchResult:
        frame, path, digest, size = self._fetch("name_change", "SSGSGMXX", "tab2", {})
        records: list[NameChangeRecord] = []
        for _, row in frame.iterrows():
            symbol = _symbol(row.get("证券代码"))
            effective_date = _date(row.get("变更日期"))
            if not _is_a_share(symbol) or not effective_date:
                continue
            records.append(NameChangeRecord(
                exchange="SZSE",
                symbol=symbol,
                effective_date=effective_date,
                before_name=_text(row.get("变更前简称")),
                after_name=_text(row.get("变更后简称")),
                source=self.name,
            ))
        return FetchResult(records, path, digest, size)

    def fetch_daily_snapshot(self, trade_date: date) -> FetchResult:
        month_start = trade_date.replace(day=1).isoformat()
        frame, path, digest, size = self._fetch(
            "stock_snapshot",
            "1815_stock_snapshot",
            "tab1",
            {
                "txtBeginDate": trade_date.isoformat(),
                "txtEndDate": trade_date.isoformat(),
                "archiveDate": month_start,
            },
            business_date=trade_date,
        )
        if frame.empty or str(frame.iloc[0].get("交易日期", "")).strip() == "没有找到符合条件的数据！":
            return FetchResult([], path, digest, size)

        records: list[DailyBar] = []
        for _, row in frame.iterrows():
            symbol = _symbol(row.get("证券代码"))
            actual_date = _date(row.get("交易日期"))
            if not symbol or not actual_date:
                continue
            volume_wan = _number(row.get("成交量(万股)"))
            amount_wan = _number(row.get("成交金额(万元)"))
            records.append(DailyBar(
                exchange="SZSE",
                symbol=symbol,
                trade_date=actual_date,
                source=self.name,
                source_priority=self.priority,
                pre_close=_number(row.get("前收")),
                open=_number(row.get("开盘")),
                high=_number(row.get("最高")),
                low=_number(row.get("最低")),
                close=_number(row.get("今收")),
                volume_shares=round(volume_wan * 10_000) if volume_wan is not None else None,
                turnover_cny=amount_wan * 10_000 if amount_wan is not None else None,
                pct_change=_number(row.get("涨跌幅（%）")),
                pe_ratio=_number(row.get("市盈率")),
            ))
        return FetchResult(records, path, digest, size)
