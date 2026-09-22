"""Publication gate for SZSE daily snapshots.

Does not alter canonical/history tables. A successful import is staged and
requires an explicit offline audit before it can be published.
"""
import json
from datetime import date

from psycopg.rows import dict_row

from .database import Database
from .quality import audit_snapshot


class PublicationService:
    DATASET = "stock_snapshot"

    def __init__(self, db: Database):
        self.db = db

    def stage(self, trade_date: date, run_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO market_daily_publication(exchange,dataset,trade_date,status,ingestion_run_id)
                VALUES ('SZSE',%s,%s,'STAGED',%s)
                ON CONFLICT(exchange,dataset,trade_date) DO UPDATE SET
                    status='STAGED', ingestion_run_id=EXCLUDED.ingestion_run_id,
                    observed_count=0, eligible_count=0, quality_summary='{}'::jsonb,
                    checked_at=NULL, published_at=NULL, updated_at=now()
                """,
                (self.DATASET, trade_date, run_id),
            )

    def fail_import(self, trade_date: date, run_id: int, reason: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE market_daily_publication
                SET status='BLOCKED', published_at=NULL,
                    quality_summary=jsonb_build_object('import_error', %s), updated_at=now()
                WHERE exchange='SZSE' AND dataset=%s AND trade_date=%s AND ingestion_run_id=%s
                """,
                (reason, self.DATASET, trade_date, run_id),
            )

    def prepare_existing(self, trade_date: date) -> None:
        """Only for snapshots imported before this publication feature existed."""
        with self.db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM ingestion_run
                WHERE provider='SZSE' AND dataset=%s AND requested_from=%s
                  AND requested_to=%s AND status='SUCCESS'
                ORDER BY id DESC LIMIT 1
                """,
                (self.DATASET, trade_date, trade_date),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"No successful SZSE stock_snapshot import for {trade_date}")
            cur.execute(
                """
                INSERT INTO market_daily_publication(exchange,dataset,trade_date,status,ingestion_run_id)
                VALUES ('SZSE',%s,%s,'STAGED',%s)
                ON CONFLICT(exchange,dataset,trade_date) DO NOTHING
                """,
                (self.DATASET, trade_date, row[0]),
            )

    def audit(self, trade_date: date, *, publish: bool = False,
              min_coverage: float = 0.65) -> dict:
        """Read and assess within the same transaction that changes publication state."""
        self.prepare_existing(trade_date)
        with self.db.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT p.status, p.ingestion_run_id, r.status AS run_status,
                       r.row_count, r.requested_from, r.requested_to
                FROM market_daily_publication p
                JOIN ingestion_run r ON r.id=p.ingestion_run_id
                WHERE p.exchange='SZSE' AND p.dataset=%s AND p.trade_date=%s
                FOR UPDATE OF p
                """,
                (self.DATASET, trade_date),
            )
            context = cur.fetchone()
            if context is None:
                raise RuntimeError(f"No snapshot publication found for {trade_date}")
            if context["run_status"] != "SUCCESS":
                raise RuntimeError(
                    f"Snapshot import {context['ingestion_run_id']} is "
                    f"{context['run_status']}; re-import before auditing"
                )
            if context["requested_from"] != trade_date or context["requested_to"] != trade_date:
                raise RuntimeError("Snapshot import date does not match publication date")

            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM instrument
                WHERE exchange='SZSE' AND security_type='STOCK'
                  AND list_date IS NOT NULL AND list_date<=%s
                  AND (delist_date IS NULL OR delist_date >= %s)
                """,
                (trade_date, trade_date),
            )
            eligible = cur.fetchone()["count"]
            cur.execute(
                """
                SELECT o.instrument_id, i.symbol, o.open, o.high, o.low, o.close,
                       o.volume_shares, o.turnover_cny,
                       b.close AS baostock_close, d.selected_source
                FROM market_daily_observation o
                JOIN instrument i ON i.id=o.instrument_id
                LEFT JOIN market_daily_observation b
                    ON b.instrument_id=o.instrument_id AND b.trade_date=o.trade_date
                   AND b.source='BAOSTOCK'
                LEFT JOIN market_daily d
                    ON d.instrument_id=o.instrument_id AND d.trade_date=o.trade_date
                WHERE i.exchange='SZSE' AND o.trade_date=%s AND o.source='SZSE'
                ORDER BY i.symbol
                """,
                (trade_date,),
            )
            bars = cur.fetchall()
            result = audit_snapshot(
                trade_date, bars, eligible, context["row_count"], min_coverage=min_coverage,
            )
            if any(row["selected_source"] != "SZSE" for row in bars):
                result["blockers"].append({
                    "issue_type": "CANONICAL_SOURCE_MISMATCH",
                    "severity": "ERROR",
                    "details": {"reason": "Canonical source is not SZSE for some snapshot records"},
                    "instrument_id": None,
                })
                result["blocker_count"] += 1

            status = "PUBLISHED" if publish and result["blocker_count"] == 0 else (
                "BLOCKED" if result["blocker_count"] else (
                    "PUBLISHED" if context["status"] == "PUBLISHED" else "STAGED"
                )
            )
            # Preserve prior audit outcomes, but only one live issue per
            # instrument, source, date and audit rule after each execution.
            cur.execute(
                """
                UPDATE data_quality_issue SET status='RESOLVED', resolved_at=now()
                WHERE trade_date=%s AND source='SZSE' AND status='OPEN'
                  AND issue_type IN (
                      'SNAPSHOT_EMPTY','SNAPSHOT_SOURCE_COUNT',
                      'SNAPSHOT_BASELINE_UNAVAILABLE','SNAPSHOT_LOW_COVERAGE',
                      'OHLC_INVALID','SOURCE_CLOSE_MISMATCH',
                      'CANONICAL_SOURCE_MISMATCH'
                  )
                """,
                (trade_date,),
            )
            all_issues = result["blockers"] + result["warnings"]
            for issue in all_issues[:100]:
                if isinstance(issue, dict):
                    issue_type, severity, details, instrument_id = (
                        issue["issue_type"], issue["severity"],
                        issue["details"], issue["instrument_id"],
                    )
                else:
                    issue_type, severity, details, instrument_id = (
                        issue.issue_type, issue.severity, issue.details, issue.instrument_id,
                    )
                cur.execute(
                    """
                    INSERT INTO data_quality_issue(instrument_id,trade_date,issue_type,severity,source,details)
                    VALUES (%s,%s,%s,%s,'SZSE',%s::jsonb)
                    """,
                    (instrument_id, trade_date, issue_type, severity, json.dumps(details)),
                )
            summary = {
                "rule_version": 1,
                "import_run_id": context["ingestion_run_id"],
                "observed_count": result["observed_count"],
                "eligible_count": result["eligible_count"],
                "imported_count": result["imported_count"],
                "min_coverage": min_coverage,
                "blocker_count": result["blocker_count"],
                "warning_count": result["warning_count"],
                "issue_rows_saved": min(len(all_issues), 100),
            }
            cur.execute(
                """
                UPDATE market_daily_publication
                SET status=%s, observed_count=%s, eligible_count=%s,
                    quality_summary=%s::jsonb, checked_at=now(),
                    published_at=CASE WHEN %s='PUBLISHED' THEN
                        COALESCE(published_at,now()) ELSE NULL END,
                    updated_at=now()
                WHERE exchange='SZSE' AND dataset=%s AND trade_date=%s
                """,
                (status, len(bars), eligible, json.dumps(summary), status,
                 self.DATASET, trade_date),
            )
            return {
                "date": trade_date.isoformat(), "status": status, **summary,
                "issues": [
                    {
                        "issue_type": i["issue_type"] if isinstance(i, dict) else i.issue_type,
                        "severity": i["severity"] if isinstance(i, dict) else i.severity,
                        "details": i["details"] if isinstance(i, dict) else i.details,
                    }
                    for i in all_issues[:20]
                ],
            }
