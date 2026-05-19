# n8n Next Steps for A8 Payload

このドキュメントは、A8 Botからn8n Webhookへ送信されたpayloadを、Notion記録・通知・日次レポートへつなげるための実装仕様です。

## 現在の到達点

- A8 Botは `N8N_WEBHOOK_URL` へPOSTできる
- GitHub Actionsで `python3 -B a8_bot.py --self-test` を実行済み
- n8n WebhookはHTTP 200を返し、`{"message":"Workflow was started"}` を確認済み
- GitHub Actions artifact `n8n-payload` に `n8n_payload.json` / `n8n_response.json` が保存される

## 固定payload仕様

A8 Botからn8nへ送るpayloadは、成功・エラーともに同じトップレベル構造に固定します。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `event_type` | string | Yes | A8イベント種別。現状は `a8_result` 固定 |
| `source` | string | Yes | 送信元。現状は `a8_bot` 固定 |
| `status` | string | Yes | `success` または `error` |
| `revenue` | number | Yes | A8報酬合計。エラー時は取得済み分、未取得なら `0` |
| `message` | string | Yes | 人間が読める実行結果またはエラー概要 |
| `occurred_at` | string | Yes | ISO 8601形式の発生日時 |
| `raw` | object | Yes | n8n/Notionで参照する詳細payload |

`raw` の標準フィールド:

| Field | Type | Description |
| --- | --- | --- |
| `start` | string | A8取得対象の開始日 |
| `end` | string | A8取得対象の終了日 |
| `count` | number | レポート件数 |
| `created` | number | Notion作成予定または作成済み件数 |
| `updated` | number | Notion更新予定または更新済み件数 |
| `reports` | array | A8成果レポート配列 |
| `error` | string/null | エラー時の内容。成功時は `null` |

## 成功payload例

```json
{
  "event_type": "a8_result",
  "source": "a8_bot",
  "status": "success",
  "revenue": 1650.0,
  "message": "A8 sync finished: 2 reports, created=2, updated=0",
  "occurred_at": "2026-05-19T14:30:22",
  "raw": {
    "start": "2026-05-18",
    "end": "2026-05-19",
    "count": 2,
    "created": 2,
    "updated": 0,
    "reports": [
      {
        "report_date": "2026-05-19",
        "program": "サンプルショップ A",
        "status": "approved",
        "reward": 1200.0,
        "result": "注文 #1234",
        "raw": {
          "report_date": "2026-05-19",
          "program": "サンプルショップ A",
          "status": "approved",
          "reward": "1,200",
          "result": "注文 #1234"
        }
      }
    ],
    "error": null
  }
}
```

## エラーpayload例

```json
{
  "event_type": "a8_result",
  "source": "a8_bot",
  "status": "error",
  "revenue": 0,
  "message": "Environment variable A8_API_KEY is required",
  "occurred_at": "2026-05-19T14:30:22",
  "raw": {
    "start": "2026-05-18",
    "end": "2026-05-19",
    "count": 0,
    "created": 0,
    "updated": 0,
    "reports": [],
    "error": "Environment variable A8_API_KEY is required"
  }
}
```

## n8n Node構成

推奨する最小構成:

1. `Webhook`
   - Method: `POST`
   - Path: GitHub Secret `N8N_WEBHOOK_URL` に設定済みのpath
   - Response: `Workflow was started` を返す設定
2. `IF`
   - 条件: `{{$json.status}}` が `error`
   - True: エラー通知へ
   - False: Notion記録と成功通知へ
3. `Notion Create/Update Page`
   - A8 payloadをNotion DBへ保存
   - 初期フェーズではCreate Pageでよい
   - 重複排除が必要になったら `Date + Source + Event Type` で検索してUpdateに切り替える
4. `Slack` or `LINE通知`
   - 成功時はサマリー通知
   - エラー時は即時通知
5. `Error分岐`
   - IF True側に接続
   - Slack/LINEで `message` と `raw.error` を通知
   - Notionにも `Status=error` で保存

日次レポートを追加する場合:

1. `Schedule Trigger`
   - 毎日任意の時刻に実行
2. `Notion Database Query`
   - 当日または前日の `Date` を対象に集計
3. `Function` / `Code`
   - `Revenue` 合計、成功件数、エラー件数を集計
4. `Slack` / `LINE` / `Email`
   - 日次レポートとして送信

## Notion DBプロパティ一覧

| Property | Type | Required | Source |
| --- | --- | --- | --- |
| `Date` | Date | Yes | `occurred_at` または `raw.end` |
| `Source` | Select / Text | Yes | `source` |
| `Event Type` | Select / Text | Yes | `event_type` |
| `Status` | Status / Select | Yes | `status` |
| `Revenue` | Number | Yes | `revenue` |
| `Message` | Rich text | Yes | `message` |
| `Raw Payload` | Rich text | Yes | payload全体をJSON文字列化 |
| `Error` | Rich text | No | `raw.error` |

推奨オプション:

| Property | Type | Purpose |
| --- | --- | --- |
| `Report Count` | Number | `raw.count` を保存 |
| `Created Count` | Number | `raw.created` を保存 |
| `Updated Count` | Number | `raw.updated` を保存 |
| `Workflow Run` | URL | GitHub Actions run URLを後続で追加する場合に利用 |

## n8nマッピング表

| n8n Expression | Notion Property | Transform |
| --- | --- | --- |
| `{{$json.occurred_at}}` | `Date` | Dateとして保存 |
| `{{$json.source}}` | `Source` | そのまま |
| `{{$json.event_type}}` | `Event Type` | そのまま |
| `{{$json.status}}` | `Status` | `success` / `error` |
| `{{$json.revenue}}` | `Revenue` | Number |
| `{{$json.message}}` | `Message` | そのまま |
| `{{JSON.stringify($json)}}` | `Raw Payload` | JSON文字列 |
| `{{$json.raw.error || ""}}` | `Error` | nullなら空文字 |
| `{{$json.raw.count}}` | `Report Count` | Number |
| `{{$json.raw.created}}` | `Created Count` | Number |
| `{{$json.raw.updated}}` | `Updated Count` | Number |

## 通知メッセージ案

成功通知:

```text
A8 Bot success
Revenue: {{$json.revenue}}
Reports: {{$json.raw.count}}
Message: {{$json.message}}
```

エラー通知:

```text
A8 Bot error
Message: {{$json.message}}
Error: {{$json.raw.error}}
Period: {{$json.raw.start}} - {{$json.raw.end}}
```

## 本番A8 API接続確認チェックリスト

GitHub Actions Secrets:

- `A8_API_KEY` が登録されている
- `A8_API_URL` が本番A8 API URLになっている
- `A8_LOOKBACK_DAYS` が意図した日数になっている
- `NOTION_TOKEN` が登録されている
- `NOTION_A8_DB_ID` が登録されている
- `LINE_TOKEN` が必要なら登録されている
- `N8N_WEBHOOK_URL` がProduction Webhook URLになっている

A8 Bot実行前:

- `python3 -B a8_bot.py --self-test` でn8n HTTP 200を確認
- n8n Executionsでpayload受信を確認
- Notion DBにテストページが作成されることを確認
- Error分岐で通知が飛ぶことを確認

本番接続時:

- GitHub Actionsを手動実行し、`self_test=false` で起動
- A8 APIから実データが取得できることを確認
- `logs/n8n_payload.json` artifactで `raw.reports` が実データになっていることを確認
- Notion DBに本番データが保存されることを確認
- n8nの日次レポート対象に本番データが含まれることを確認

## n8n画面で次にクリックするもの

1. n8nでA8 Webhook Workflowを開く
2. `+` をクリックして `IF` Nodeを追加
3. 条件に `{{$json.status}}` equals `error` を設定
4. False側に `Notion` Nodeを追加し、`Create Page` を選択
5. Notion DBを選び、上記マッピング表どおりに各プロパティを設定
6. False側に `Slack` または `LINE` Nodeを追加して成功通知を設定
7. True側に `Notion` Nodeを追加してエラーを記録
8. True側に `Slack` または `LINE` Nodeを追加してエラー通知を設定
9. `Execute workflow` でテスト
10. 問題なければ `Save` して `Active` を維持

## Codex側の次実装候補

1. 本番A8 APIのレスポンス実例に合わせて `A8Client._normalize_record()` を調整
2. n8n payloadに `github_run_url` を追加
3. payload schemaの自動テストを追加
4. エラー時に例外種別やstack trace要約を `raw` へ追加
5. n8nがNotion記録を担当する場合、A8 Bot側のNotion直接同期をオプション化または廃止
