import os
import requests
from dotenv import load_dotenv

load_dotenv()

KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def fetch_product():
    asin = "B08N5WRWNW"  # テスト用ASIN
url = f"https://api.keepa.com/v1/deal?key={KEEPA_API_KEY}&domain=JP&buybox=1&history=0"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    return asin

def notify_slack(asin):
    message = (
        f"【テスト通知】\n"
        f"Keepa API接続成功 ✅\n"
        f"https://www.amazon.co.jp/dp/{asin}"
    )
    res = requests.post(SLACK_WEBHOOK_URL, json={"text": message})
    res.raise_for_status()

if __name__ == "__main__":
    asin = fetch_product()
    notify_slack(asin)
