"""Utility to surface the single next business step."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Iterable, List

import requests


@dataclass(frozen=True)
class Step:
    area: str
    title: str
    actions: List[str]
    impact: str


SHORT_TERM_OBJECTIVES = [
    "売上1億円",
    "Stripe Payment Link × LP の自動生成ファネル完成",
    "A8→Notion→LINE→GitHub Actions 完全自動化の安定稼働",
    "営業：1日60件以上、地主10名のホットリード化",
]


def prioritize_steps() -> Iterable[Step]:
    """Return a deterministic list of high-leverage steps."""
    return [
        Step(
            area="収益ファネル",
            title="Stripe Payment Link x LP 自動生成のテンプレート定義",
            actions=[
                "Stripe API で再利用する商品マスタ（SKU, 価格, アップセル有無）を Notion DB に設計",
                "Notion DB の各レコードに LP コピー断片（見出し/CTA/証拠）フィールドを追加",
                "GitHub Actions で Notion API をポーリングし、Payment Link + LP HTML を自動生成するスクリプトを作成",
            ],
            impact=(
                "自動生成されたリンクをメール/LINE で即時配信でき、45日以内の 1 億円達成に直結"
            ),
        ),
        Step(
            area="営業オペレーション",
            title="1日60件アプローチの自動ダイヤラー設定",
            actions=[
                "LINE Official アカウント API のメッセージ予約スクリプトを整備",
                "地主セグメントごとに 1 日 6 ブロックのメッセージテンプレートを作成",
                "GitHub Actions から毎朝の送信ジョブをキック",
            ],
            impact="ホットリード 10 名の創出速度を最大化",
        ),
    ]


def determine_next_step() -> Step:
    return next(iter(prioritize_steps()))


def format_step(step: Step) -> str:
    header = (
        "稲村優Codex 起動完了\n"
        f"次にやるべき最初の1ステップ ({step.area})\n"
        f"▶ {step.title}\n"
    )
    body = "\n".join(f"{idx+1}. {action}" for idx, action in enumerate(step.actions))
    footer = "\n理由: " + step.impact
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    meta = json.dumps({"timestamp": timestamp, "objectives": SHORT_TERM_OBJECTIVES}, ensure_ascii=False)
    return f"{header}{body}{footer}\n---\n{meta}"


def notify_slack(message: str) -> None:
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    resp = requests.post(webhook, json={"text": message}, timeout=10)
    resp.raise_for_status()


def main() -> None:
    step = determine_next_step()
    message = format_step(step)
    print(message)
    notify_slack(message)


if __name__ == "__main__":
    main()
