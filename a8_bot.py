"""A8.net → Notion → LINE pipeline."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)

A8_API_KEY = os.getenv("A8_API_KEY")
A8_API_URL = os.getenv("A8_API_URL", "https://api.a8.net/asp/v1/report")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_A8_DB_ID = os.getenv("NOTION_A8_DB_ID")
LINE_TOKEN = os.getenv("LINE_TOKEN")
raw_lookback = os.getenv("A8_LOOKBACK_DAYS", "1")
try:
    A8_LOOKBACK_DAYS = int(raw_lookback)
except (TypeError, ValueError):
    LOGGER.warning(
        "Invalid A8_LOOKBACK_DAYS=%r provided; defaulting to 1 day", raw_lookback
    )
    A8_LOOKBACK_DAYS = 1


class MissingEnvError(RuntimeError):
    pass


def require_env(value: Optional[str], key: str) -> str:
    if not value:
        raise MissingEnvError(f"Environment variable {key} is required")
    return value


def _parse_reward(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(",", "").replace("¥", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        LOGGER.warning("Could not parse reward value %s; defaulting to 0", value)
        return 0.0


def _parse_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(value[:10], fmt).date()
            except ValueError:
                continue
    return date.today()


@dataclass
class A8Report:
    report_date: date
    program: str
    status: str
    reward: float
    result: str
    raw: Dict[str, object]

    @property
    def summary(self) -> str:
        reward_label = f"{self.reward:,.0f}" if self.reward % 1 == 0 else f"{self.reward:,.2f}"
        return (
            f"{self.report_date.isoformat()} {self.program}"
            f" / {self.status} / 報酬 {reward_label}"
        )


class A8Client:
    def __init__(self, api_key: str, base_url: str = A8_API_URL):
        self.api_key = api_key
        self.base_url = base_url

    @classmethod
    def from_env(cls) -> "A8Client":
        return cls(api_key=require_env(A8_API_KEY, "A8_API_KEY"))

    def fetch_reports(self, start: date, end: date) -> List[A8Report]:
        params = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        LOGGER.info("Fetching A8 reports %s → %s", start, end)
        response = requests.get(
            self.base_url, headers=headers, params=params, timeout=30
        )
        response.raise_for_status()
        reports = list(self._parse_response(response))
        LOGGER.info("Received %d A8 report rows", len(reports))
        return reports

    def _parse_response(self, response: requests.Response) -> Iterable[A8Report]:
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            payload = response.json()
            records = self._extract_records(payload)
        else:
            # fallback to CSV / text
            reader = csv.DictReader(StringIO(response.text))
            records = list(reader)
        for record in records:
            yield self._normalize_record(record)

    def _extract_records(self, payload: object) -> Sequence[dict]:
        if isinstance(payload, dict):
            for key in ("reports", "data", "results", "items", "list"):
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
        if isinstance(payload, list):
            return payload
        LOGGER.warning("Unrecognized A8 payload shape; defaulting to empty list")
        return []

    def _normalize_record(self, record: dict) -> A8Report:
        raw_date = record.get("date") or record.get("report_date") or record.get("ymd")
        program = (
            record.get("program")
            or record.get("program_name")
            or record.get("advertiser")
            or record.get("programName")
            or "Unknown Program"
        )
        status = (
            record.get("status")
            or record.get("state")
            or record.get("approval_status")
            or "pending"
        )
        reward = _parse_reward(
            record.get("reward")
            or record.get("reward_amount")
            or record.get("commission")
            or record.get("price")
            or 0
        )
        result = (
            record.get("result")
            or record.get("action")
            or record.get("summary")
            or record.get("description")
            or ""
        )
        return A8Report(
            report_date=_parse_date(raw_date),
            program=str(program),
            status=str(status),
            reward=reward,
            result=str(result),
            raw=record,
        )


def get_notion_client() -> Client:
    token = require_env(NOTION_TOKEN, "NOTION_TOKEN")
    return Client(auth=token)


class NotionA8Sync:
    def __init__(self, client: Client, database_id: str):
        self.client = client
        self.database_id = database_id

    def sync(self, reports: Sequence[A8Report]) -> tuple[int, int]:
        created = updated = 0
        for report in reports:
            page_id = self._find_existing(report)
            if page_id:
                self._update_page(page_id, report)
                updated += 1
            else:
                self._create_page(report)
                created += 1
        return created, updated

    def _find_existing(self, report: A8Report) -> Optional[str]:
        try:
            resp = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "and": [
                        {"property": "Date", "date": {"equals": report.report_date.isoformat()}},
                        {"property": "Program", "title": {"equals": report.program}},
                    ]
                },
                page_size=1,
            )
        except Exception as exc:  # pragma: no cover - Notion API typing
            LOGGER.warning("Failed to query Notion DB: %s", exc)
            return None
        results = resp.get("results", [])
        if results:
            return results[0]["id"]
        return None

    def _base_properties(self, report: A8Report) -> dict:
        return {
            "Program": {"title": [{"text": {"content": report.program}}]},
            "Date": {"date": {"start": report.report_date.isoformat()}},
            "Status": {"status": {"name": report.status}},
            "Reward": {"number": report.reward},
            "Result": {"rich_text": [{"text": {"content": report.result or "-"}}]},
            "Payload": {"rich_text": [{"text": {"content": json.dumps(report.raw, ensure_ascii=False)[:2000]}}]},
        }

    def _create_page(self, report: A8Report) -> None:
        self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=self._base_properties(report),
        )

    def _update_page(self, page_id: str, report: A8Report) -> None:
        self.client.pages.update(page_id=page_id, properties=self._base_properties(report))


def send_line_notification(reports: Sequence[A8Report], start: date, end: date, created: int, updated: int) -> None:
    token = require_env(LINE_TOKEN, "LINE_TOKEN")
    reward_total = sum(report.reward for report in reports)
    header = f"A8成果報告 {start.isoformat()} → {end.isoformat()}"
    lines = [header, f"新規 {created} / 更新 {updated} / 件数 {len(reports)}"]
    lines.append(f"報酬合計: {reward_total:,.0f}")
    for report in reports[:5]:
        lines.append(f"・{report.summary}")
    if len(reports) > 5:
        lines.append(f"…他 {len(reports) - 5} 件")
    message = "\n".join(lines)
    LOGGER.info("Sending LINE notification (%d chars)", len(message))
    resp = requests.post(
        "https://notify-api.line.me/api/notify",
        headers={"Authorization": f"Bearer {token}"},
        data={"message": message},
        timeout=10,
    )
    resp.raise_for_status()


def _load_sample_reports() -> List[A8Report]:
    today = date.today()
    payload = [
        {
            "report_date": today.isoformat(),
            "program": "サンプルショップ A",
            "status": "approved",
            "reward": "1,200",
            "result": "注文 #1234",
        },
        {
            "report_date": (today - timedelta(days=1)).isoformat(),
            "program": "テスト広告 B",
            "status": "pending",
            "reward": 450,
            "result": "クリック 25 件",
        },
    ]
    normalized: List[A8Report] = []
    for item in payload:
        normalized.append(
            A8Report(
                report_date=_parse_date(item["report_date"]),
                program=item["program"],
                status=item["status"],
                reward=_parse_reward(item["reward"]),
                result=item["result"],
                raw=item,
            )
        )
    return normalized


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A8.net → Notion → LINE pipeline")
    parser.add_argument(
        "--start",
        type=_parse_date,
        help="Start date (YYYY-MM-DD). Defaults to today - A8_LOOKBACK_DAYS.",
    )
    parser.add_argument("--end", type=_parse_date, help="End date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument(
        "--use-sample-data",
        action="store_true",
        help="Skip API access and use built-in sample data for testing.",
    )
    parser.add_argument(
        "--skip-notion",
        action="store_true",
        help="Log Notion payloads instead of writing to the API.",
    )
    parser.add_argument(
        "--skip-line",
        action="store_true",
        help="Log LINE notification instead of sending it.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run an end-to-end dry-run using sample data. Implies --use-sample-data --skip-notion --skip-line.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Keep connections live but avoid writing to Notion/LINE. Useful for smoke tests in production mode.",
    )
    return parser.parse_args()


def _notion_target(skip: bool) -> Tuple[NotionA8Sync, bool]:
    if skip:
        class _StubNotion(NotionA8Sync):
            def __init__(self) -> None:  # pragma: no cover - simple logger
                self.actions: list[str] = []

            def sync(self, reports: Sequence[A8Report]) -> tuple[int, int]:
                for report in reports:
                    self.actions.append(f"would upsert {report.summary}")
                LOGGER.info("[dry-run] %d Notion operations queued", len(self.actions))
                return len(self.actions), 0

        return _StubNotion(), True
    return NotionA8Sync(client=get_notion_client(), database_id=require_env(NOTION_A8_DB_ID, "NOTION_A8_DB_ID")), False


def _notify_target(skip: bool):
    if skip:
        return lambda *args, **kwargs: LOGGER.info("[dry-run] LINE notification skipped")
    return send_line_notification


def main() -> None:
    args = _parse_args()
    start = args.start or (date.today() - timedelta(days=A8_LOOKBACK_DAYS))
    end = args.end or date.today()

    use_sample = args.use_sample_data or args.self_test
    skip_notion = args.skip_notion or args.self_test or args.dry_run
    skip_line = args.skip_line or args.self_test or args.dry_run

    if args.self_test:
        LOGGER.info("Running self-test with sample data")
    elif args.dry_run:
        LOGGER.info("Running production dry-run (A8 API live, Notion/LINE skipped)")
    else:
        LOGGER.info("Running in production mode (A8/Notion/LINE live)")

    if use_sample:
        reports = _load_sample_reports()
    else:
        client = A8Client.from_env()
        reports = client.fetch_reports(start, end)

    if not reports:
        LOGGER.info("No A8 reports to process")
        return

    notion, is_dry_run = _notion_target(skip_notion)
    created, updated = notion.sync(reports)
    LOGGER.info("Notion sync finished (created=%d, updated=%d)%s", created, updated, " [dry-run]" if is_dry_run else "")

    notify = _notify_target(skip_line)
    notify(reports, start, end, created, updated)


if __name__ == "__main__":
    main()
