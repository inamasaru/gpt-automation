# Repository Audit / 収益エンジン棚卸し

## 結論

本命リポジトリは `inamasaru/gpt-automation` に統一する。

理由:
- A8 Bot、Stripe、LP生成、Keepa、ショート動画など既存実装が最も多い
- A8 Botはすでに Notion / LINE / GitHub Actions 連携まで進んでいる
- Codex作業履歴が最も集中している

## 残す

### inamasaru/gpt-automation

役割: AI収益エンジン本体

優先機能:
1. A8成果取得
2. Notion保存
3. n8n Webhook通知
4. LINE/Slack通知
5. GitHub Actions定期実行
6. 実行ログ保存

## 統合候補

### inamasaru/a8-affiliate-bot

状態:
- Hugging Face APIエラー処理のPRがある
- A8本体としては `gpt-automation` より弱い

判断:
- 単独運用しない
- 必要な処理だけ `gpt-automation` に統合する

### inamasaru/aga-auto-bot

状態:
- AGAアフィリ用の可能性あり

判断:
- 今は停止
- A8 Botが安定後、ジャンル別Botとして再利用

## 保留

### inamasaru/ai-side-hustle-affiliate-mvp

状態:
- 名前は近いが、現時点の本命ではない

判断:
- 今は触らない
- 後で中身を確認して、使えるLP/記事/商品選定ロジックだけ移植

### inamasaru/365bot

状態:
- 構想・大目標系の可能性が高い

判断:
- 今の収益導線からは外す
- 実装本体にしない

## 停止候補

- inamasaru/auto-revenue-system
- inamasaru/mega-biz
- inamasaru/-dropship-ai
- inamasaru/rakuten-threads-agent
- gpt-engine/auto-affiliate-engine

判断:
- いったん新規作業停止
- `gpt-automation` が安定するまで触らない

## 危険確認

### inamasaru/env-secrets

注意:
- APIキー、.env、トークン類が入っている場合は危険
- GitHubに秘密情報を置かない
- もし本物のキーが入っていたら即削除し、各サービスでキー再発行する

## 今日の最優先

1. `gpt-automation` のA8 Botを本命に固定
2. Codexのn8n連携作業を完了させる
3. `N8N_WEBHOOK_URL` をGitHub Secretsへ登録
4. n8n側にWebhookを作成
5. A8 self-testでn8nにJSONが届くか確認
6. n8nからNotion/LINE/Slackへ流す

## やらないこと

- 新しいリポジトリを増やさない
- n8nで複雑なロジックを作らない
- Claude Codeでエラー修正ループを回さない
- Codex作業中のブランチに別AIが同時編集しない

## 役割分担

- Claude Code: 設計レビュー、棚卸し、Codex向け指示作成
- Codex: 実装、テスト、エラー修正、PR作成
- GitHub: 共通記憶・実装本体
- n8n: Webhook受信、通知、Notion/LINE/Slack連携
- Notion: 実行ログ・売上ログ
- LINE/Slack: 通知
