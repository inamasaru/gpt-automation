import os
import requests
from dotenv import load_dotenv

load_dotenv()                                     # .env ／ GitHub Secrets 両対応

KEEPA_API_KEY   = os.getenv("KEEPA_API_KEY")
SLACK_WEBHOOK   = os.getenv("SLACK_WEBHOOK_URL")

# === 固定テスト ASIN  =========================================
TEST_ASIN = "B08N5WRNW"        # 好きな ASIN に差し替えて OK
DOMAIN   = 6                   # JP=6  US=1  EU=3  … Keepa ドキュメント参照
# ============================================================

def fetch_product(asin: str) -> dict:
    """Keepa から商品情報を 1 件取得して JSON を返す"""
    url = (
        "https://api.keepa.com/product"
        f"?key={KEEPA_API_KEY}"
        f"&domain={DOMAIN}"
        f"&asin={asin}"
        f"&history=0"          # 価格履歴は不要なので 0
    )
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:          # ←ここで本文を吐き出してデバッグしやすく
        raise RuntimeError(
            f"Keepa API error {resp.status_code}: {resp.text[:400]}"
        )
    return resp.json()

def notify_slack(text: str) -> None:
    resp = requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    resp.raise_for_status()

def main() -> None:
    data = fetch_product(TEST_ASIN)
    ok_emoji = "✅"
    message = (
        f"{ok_emoji} Keepa API に接続できました\n"
        f"テスト ASIN: {TEST_ASIN}\n"
        f"https://www.amazon.co.jp/dp/{TEST_ASIN}"
    )
    notify_slack(message)

if __name__ == "__main__":
    main()
