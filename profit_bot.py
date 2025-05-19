import os
import requests
from dotenv import load_dotenv

load_dotenv()
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
KEEPA_BASE_URL = "https://api.keepa.com"

def fetch_deals():
    url = f"{KEEPA_BASE_URL}/deals?key={KEEPA_API_KEY}&domain=JP&buybox=1&history=0"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()

def notify_slack(deal):
    asin = deal.get("asin", "N/A")
    title = deal.get("title", "No title")
    profit = 2000
    message = (
        f"【利益商品】\n"
        f"📦 商品名: {title}\n"
        f"💰 利益: {profit}円\n"
        f"https://www.amazon.co.jp/dp/{asin}"
    )
    requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)

def main():
    deals = fetch_deals()
    for deal in deals.get("deals", []):
        notify_slack(deal)

if __name__ == "__main__":
    main()
