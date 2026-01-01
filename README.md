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

## メモ

- TTSモデルは `OPENAI_TTS_MODEL`、音声は `OPENAI_TTS_VOICE` で変更可能
- テキスト生成モデルは `OPENAI_MODEL` で変更可能
