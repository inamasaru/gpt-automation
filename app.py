from flask import Flask, request, jsonify, abort
import os
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_DB_ID = os.getenv('NOTION_DB_ID')
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL')

NOTION_VERSION = '2022-06-28'


def create_notion_entry(full_name: str, email: str, product_name: str):
    if not NOTION_API_KEY or not NOTION_DB_ID:
        raise RuntimeError('Notion credentials not configured')
    url = 'https://api.notion.com/v1/pages'
    headers = {
        'Authorization': f'Bearer {NOTION_API_KEY}',
        'Notion-Version': NOTION_VERSION,
        'Content-Type': 'application/json',
    }
    payload = {
        'parent': {'database_id': NOTION_DB_ID},
        'properties': {
            'Name': {
                'title': [{
                    'text': {'content': full_name}
                }]
            },
            'Email': {
                'email': email
            },
            'Product': {
                'rich_text': [{
                    'text': {'content': product_name}
                }]
            }
        }
    }
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    return res.json()


def send_slack_notification(full_name: str, product_name: str):
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL:
        print('Slack credentials not configured')
        return
    client = WebClient(token=SLACK_BOT_TOKEN)
    message = f"\U0001F389 {full_name} が {product_name} を購入しました！"
    try:
        client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")


@app.route('/webhook', methods=['POST'])
def webhook():
    if not request.is_json:
        abort(400)
    data = request.get_json()
    full_name = data.get('full_name')
    email = data.get('email')
    product_name = data.get('product_name')
    if not all([full_name, email, product_name]):
        abort(400)
    try:
        create_notion_entry(full_name, email, product_name)
        send_slack_notification(full_name, product_name)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
