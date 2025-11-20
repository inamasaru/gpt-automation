import logging
import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv

load_dotenv()  # .env ／ GitHub Secrets 両対応

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)

KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")
TEST_ASIN = os.getenv("KEEPA_TEST_ASIN", "B08N5WRNW")
DOMAIN = int(os.getenv("KEEPA_DOMAIN", "6"))  # JP=6  US=1  EU=3  … Keepa ドキュメント参照


def require_env(value: str | None, key: str) -> str:
    if not value:
        raise RuntimeError(f"Environment variable {key} is required")
    return value


def fetch_product(asin: str) -> Dict[str, Any]:
    """Keepa から商品情報を 1 件取得して JSON を返す"""
    api_key = require_env(KEEPA_API_KEY, "KEEPA_API_KEY")
    url = (
        "https://api.keepa.com/product"
        f"?key={api_key}"
        f"&domain={DOMAIN}"
        f"&asin={asin}"
        f"&history=0"          # 価格履歴は不要なので 0
    )
    LOGGER.info("Fetching Keepa data for ASIN %s", asin)
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:          # ←ここで本文を吐き出してデバッグしやすく
        raise RuntimeError(
            f"Keepa API error {resp.status_code}: {resp.text[:400]}"
        )
    return resp.json()


def notify_slack(text: str) -> None:
    webhook = require_env(SLACK_WEBHOOK, "SLACK_WEBHOOK_URL")
    LOGGER.info("Sending Slack notification")
    resp = requests.post(webhook, json={"text": text}, timeout=10)
    resp.raise_for_status()


def main() -> None:
    data = fetch_product(TEST_ASIN)
    ok_emoji = "✅"
    message = (
        f"{ok_emoji} Keepa API に接続できました\n"
        f"テスト ASIN: {TEST_ASIN}\n"
        f"https://www.amazon.co.jp/dp/{TEST_ASIN}"
    )
    if data.get("products"):
        product = data["products"][0]
        title = product.get("title")
        if title:
            message += f"\n商品名: {title}"
    notify_slack(message)


if __name__ == "__main__":
    main()
