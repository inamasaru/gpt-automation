import os
import requests
from dotenv import load_dotenv

# .env または GitHub Secrets からキーを読み込む
load_dotenv()
KEEPA_API_KEY   = os.getenv("KEEPA_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def fetch_product():
    """固定 ASIN の商品データを 1 件取得してレスポンス確認だけ行う"""
    asin = "B08N5WRNW"                     # ★好きな ASIN に変えて OK
    url = (
        f"https://api.keepa.com/v1/product"
        f"?key={KEEPA_API_KEY}"
        f"&domain=4"                      # 4 = Amazon.co.jp
        f"&asin={asin}"
        f"&history=0"
    )
    res = requests.get(url, timeout=10)
    res.raise_for_status()                # 2xx でなければ例外
    return asin

def notify_slack(asin: str):
    message = (
        f"【テスト通知】\n"
        f"Keepa API 連携成功 ✅\n"
        f"https://www.amazon.co.jp/dp/{asin}"
    )
    res = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": message},
        timeout=10,
    )
    res.raise_for_status()

if __name__ == "__main__":
    asin = fetch_product()
    notify_slack(asin)
