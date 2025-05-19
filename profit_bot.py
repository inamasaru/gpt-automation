import os
import requests
from dotenv import load_dotenv

load_dotenv()

KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def fetch_product():
    asin = "B08N5WRWNW"  # 任意のASIN（テスト用）
    url = f"https://api.keepa.com/product?key={KEEPA_API_KEY}&domain=JP&asin={asin}"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    return asin

def notify_slack(asin):
    message = (
        f"【テスト通知】\n"
        f"Keepa API接続成功 ✅\n"
        f"https://www.amazon.co.jp/dp/{asin}"
    )
    requests.post(SLACK_WEBHOOK_URL, json={"text": message})

if __name__ == "__main__":
    asin = fetch_product()
    notify_slack(asin)
