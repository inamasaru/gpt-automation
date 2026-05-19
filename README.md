# Daily Short Video Generator (JP)

topics.csv のネタから、毎日1本の縦動画（720x1280 / 60秒以内）を自動生成します。OpenAIのテキスト生成とTTSのみで完結します。

## セットアップ

1. Python 3.10+ を用意
2. 依存をインストール
   ```bash
   pip install -r requirements.txt
   ```
3. `.env.example` を参考に `OPENAI_API_KEY` を設定
4. 必要なら `assets/` に背景画像を追加（無ければ単色背景）

## 実行コマンド

```bash
python main.py --run-once
python main.py --id 001
python main.py --dry-run
```

### A8 Bot

```bash
python a8_bot.py
python a8_bot.py --dry-run
python a8_bot.py --self-test
```

`--self-test` はサンプルデータで実行し、Notion / LINE は dry-run、n8n は `N8N_WEBHOOK_URL` が設定されていれば実際にPOSTします。n8n へ送る標準JSONはログに出力され、`logs/n8n_payload.json` に保存されるため、Webhook連携前の確認に使えます。

## 生成物

- `out/YYYYMMDD_id/`
  - `video.mp4`
  - `meta.json`（title/description/hashtags/script/theme）
  - `audio.mp3`
  - `subtitles.srt`

## AI音声の開示

生成される description には **AI音声である旨の短い開示** が自動挿入されます。公開時にも必ず開示要件を確認してください。

## 失敗時の確認ポイント

- GitHub Actions のログ
- `topics.csv` の `status` が `ERROR` になっていないか
- `error` 列の内容

## GitHub Actions

`.github/workflows/daily.yml` を使うと、毎日スケジュール実行されます。
`topics.csv` が更新された場合は自動コミットして push します（workflow は push トリガーしないのでループしません）。

## n8n連携

A8 Botは実行結果とエラーをn8n Webhookへ標準JSONで通知できます。

1. n8nでWebhookノードを作成し、POST用URLを取得
2. `.env` またはGitHub Actions Secretsに `N8N_WEBHOOK_URL` を設定
3. `python a8_bot.py --self-test` でdry-run内容を確認
4. 問題なければ `python a8_bot.py` またはGitHub Actionsで実行

`N8N_WEBHOOK_URL` が未設定の場合、n8n通知はスキップされ、Bot処理は継続します。Webhook送信に失敗した場合も警告ログのみを出して処理を止めません。`--dry-run` ではPOSTせず、payload保存のみ行います。WebhookのHTTPステータスとレスポンス本文は `logs/n8n_response.json` に保存されます。

GitHub Actionsでは `N8N_WEBHOOK_URL` Secretを使ってA8 Botからn8nへPOSTします。手動実行時に `self_test=true` を指定すると `python3 -B a8_bot.py --self-test` を実行します。実行後はActionsのArtifactsに `n8n-payload` として `logs/n8n_payload.json` と `logs/n8n_response.json` が残ります。

送信payload:

```json
{
  "event_type": "a8_result",
  "status": "success",
  "revenue": 1650,
  "source": "a8_bot",
  "message": "A8 sync finished: 2 reports, created=2, updated=0",
  "occurred_at": "2026-05-19T10:00:00",
  "raw": {
    "start": "2026-05-18",
    "end": "2026-05-19",
    "count": 2,
    "created": 2,
    "updated": 0,
    "reports": []
  }
}
```

## メモ

- TTSモデルは `OPENAI_TTS_MODEL`、音声は `OPENAI_TTS_VOICE` で変更可能
- テキスト生成モデルは `OPENAI_MODEL` で変更可能
- n8n通知先は `N8N_WEBHOOK_URL` で設定可能
