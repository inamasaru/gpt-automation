import argparse
import csv
import datetime as dt
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
TOPICS_CSV = ROOT / "topics.csv"
ASSETS_DIR = ROOT / "assets"
OUT_DIR = ROOT / "out"

DEFAULT_MODEL = "gpt-5.2"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "alloy"


class ScriptOutput(BaseModel):
    title: str = Field(..., description="40文字以内の短いタイトル")
    hook: str = Field(..., description="冒頭の1文")
    body_lines: List[str] = Field(..., description="7〜12行の短文")
    outro: str = Field(..., description="締めの1文")
    description: str = Field(
        ..., description="YouTube用説明文。AI音声である旨の短い開示を含める"
    )
    hashtags: List[str] = Field(..., description="5〜10個のハッシュタグ")


def load_topics() -> List[dict]:
    if not TOPICS_CSV.exists():
        raise FileNotFoundError("topics.csv が見つかりません")
    with TOPICS_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_topics(rows: List[dict]) -> None:
    fieldnames = [
        "id",
        "theme",
        "status",
        "title",
        "description",
        "hashtags",
        "script",
        "audio_file",
        "video_file",
        "error",
        "updated_at",
    ]
    with TOPICS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def select_target(rows: List[dict], target_id: Optional[str]) -> Optional[int]:
    if target_id:
        for idx, row in enumerate(rows):
            if row.get("id") == target_id:
                return idx
        return None
    for idx, row in enumerate(rows):
        if row.get("status") == "TODO":
            return idx
    return None


def ensure_dirs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def pick_background() -> Optional[Path]:
    if not ASSETS_DIR.exists():
        return None
    candidates = [
        p
        for p in ASSETS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    if not candidates:
        return None
    return random.choice(candidates)


def generate_script(theme: str, dry_run: bool) -> ScriptOutput:
    if dry_run:
        return ScriptOutput(
            title=f"{theme}の1分解説",
            hook=f"今日は「{theme}」のポイントを30秒で紹介します。",
            body_lines=[
                "ポイントは3つだけ",
                "まず背景を一言でまとめる",
                "次にメリットを短く伝える",
                "最後に注意点を入れる",
                "例え話で理解を助ける",
                "具体策を1つ提示",
                "締めは行動を促す",
            ],
            outro="続きが気になったらフォローしてね。",
            description="AI音声で読み上げています。短く学べる要点まとめです。",
            hashtags=["#学び", "#ショート", "#豆知識", "#1分解説", "#AI音声"],
        )

    client = OpenAI()
    system_message = (
        "あなたは日本語のショート動画台本ライターです。"
        "60秒以内で読める短い文だけを使い、各行を短く。"
        "体言止めや箇条書き風でもOK。"
    )
    user_message = (
        "以下のテーマで日本語ショート動画の台本を作成してください。\n"
        f"テーマ: {theme}\n"
        "条件:\n"
        "- titleは40文字以内\n"
        "- hookは1文\n"
        "- body_linesは7〜12行、各行は短く\n"
        "- outroは1文\n"
        "- descriptionにはAI音声である旨の短い開示を含める\n"
        "- hashtagsは5〜10個\n"
        "- 60秒以内に収まる分量\n"
    )
    response = client.responses.parse(
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        input=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        text_format=ScriptOutput,
    )
    return response.output_parsed


def synthesize_audio(script_text: str, output_path: Path, dry_run: bool) -> None:
    if dry_run:
        ensure_dirs(output_path.parent)
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            "5",
            str(output_path),
        ]
        subprocess.run(cmd, check=True)
        return

    client = OpenAI()
    voice = os.getenv("OPENAI_TTS_VOICE", DEFAULT_TTS_VOICE)
    audio = client.audio.speech.create(
        model=os.getenv("OPENAI_TTS_MODEL", DEFAULT_TTS_MODEL),
        voice=voice,
        input=script_text,
        format="mp3",
    )
    ensure_dirs(output_path.parent)
    output_path.write_bytes(audio.read())


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def seconds_to_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours = millis // 3_600_000
    minutes = (millis % 3_600_000) // 60_000
    secs = (millis % 60_000) // 1000
    ms = millis % 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def generate_subtitles(lines: List[str], audio_path: Path, srt_path: Path) -> None:
    duration = max(get_audio_duration(audio_path), 0.5)
    total_chars = sum(len(line) for line in lines) or 1
    current = 0.0
    entries = []
    for idx, line in enumerate(lines, start=1):
        portion = max(len(line) / total_chars, 0.02)
        line_duration = portion * duration
        start = current
        end = min(current + line_duration, duration)
        entries.append(
            f"{idx}\n{seconds_to_timestamp(start)} --> {seconds_to_timestamp(end)}\n{line}\n"
        )
        current = end
    srt_path.write_text("\n".join(entries), encoding="utf-8")


def build_video(
    audio_path: Path,
    srt_path: Path,
    video_path: Path,
    background: Optional[Path],
) -> None:
    ensure_dirs(video_path.parent)
    subtitle_filter = (
        "subtitles={}:force_style='FontName=Noto Sans CJK JP,FontSize=42,"
        "PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,Outline=2,Shadow=1,MarginV=110'"
    ).format(str(srt_path).replace("'", "\\'"))

    if background:
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(background),
            "-i",
            str(audio_path),
            "-vf",
            "scale=720:1280:force_original_aspect_ratio=cover,crop=720:1280," + subtitle_filter,
            "-shortest",
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=720x1280:r=30",
            "-i",
            str(audio_path),
            "-vf",
            subtitle_filter,
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ]
    subprocess.run(cmd, check=True)


def build_metadata(output: ScriptOutput, theme: str, out_path: Path) -> dict:
    return {
        "title": output.title,
        "description": output.description,
        "hashtags": output.hashtags,
        "script": "\n".join([output.hook, *output.body_lines, output.outro]),
        "theme": theme,
        "path": str(out_path),
    }


def process_topic(row: dict, dry_run: bool) -> dict:
    theme = row.get("theme", "").strip()
    if not theme:
        raise ValueError("theme が空です")

    today = dt.datetime.now().strftime("%Y%m%d")
    output_dir = OUT_DIR / f"{today}_{row.get('id')}"
    ensure_dirs(output_dir)

    script_output = generate_script(theme, dry_run=dry_run)

    lines = [script_output.hook, *script_output.body_lines, script_output.outro]
    script_text = "\n".join(lines)

    audio_path = output_dir / "audio.mp3"
    synthesize_audio(script_text, audio_path, dry_run=dry_run)

    srt_path = output_dir / "subtitles.srt"
    generate_subtitles(lines, audio_path, srt_path)

    video_path = output_dir / "video.mp4"
    background = pick_background()
    build_video(audio_path, srt_path, video_path, background)

    meta = build_metadata(script_output, theme, output_dir)
    (output_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    row.update(
        {
            "status": "DONE",
            "title": script_output.title,
            "description": script_output.description,
            "hashtags": " ".join(script_output.hashtags),
            "script": script_text,
            "audio_file": str(audio_path),
            "video_file": str(video_path),
            "error": "",
            "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
    )
    return row


def mark_error(row: dict, error_message: str) -> dict:
    row.update(
        {
            "status": "ERROR",
            "error": error_message,
            "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
    )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily short video generator")
    parser.add_argument("--run-once", action="store_true", help="process one TODO entry")
    parser.add_argument("--id", help="process a specific topic id")
    parser.add_argument("--dry-run", action="store_true", help="skip OpenAI calls")
    args = parser.parse_args()

    rows = load_topics()

    # 1) --id がある場合：その1件だけ（--run-once無視）
    if args.id:
        target_index = select_target(rows, args.id)
        if target_index is None:
            print("[INFO] 指定idが見つかりません。終了します。")
            return 0

        target_row = rows[target_index]

        # id指定のときは DONE でも処理したいケースがあり得るので、ここではスキップしない
        try:
            rows[target_index] = process_topic(target_row, dry_run=args.dry_run)
            save_topics(rows)
            print("[INFO] 完了しました。")
            return 0
        except Exception as exc:
            rows[target_index] = mark_error(target_row, str(exc))
            save_topics(rows)
            print(f"[ERROR] {exc}")
            return 1

    # 2) --id なし
    #    --run-once: TODOの先頭1件だけ
    #    それ以外: TODOを全件（batch）
    todo_indexes = [i for i, r in enumerate(rows) if (r.get("status") or "").upper() == "TODO"]

    if not todo_indexes:
        print("[INFO] 対象がありません。終了します。")
        return 0

    if args.run_once:
        todo_indexes = todo_indexes[:1]

    any_error = False

    for idx in todo_indexes:
        target_row = rows[idx]

        try:
            rows[idx] = process_topic(target_row, dry_run=args.dry_run)
        except Exception as exc:
            rows[idx] = mark_error(target_row, str(exc))
            any_error = True
            print(f"[ERROR] id={target_row.get('id','')} {exc}")

        # 進捗を落とさないために都度保存
        save_topics(rows)

    if any_error:
        print("[WARN] 一部エラーがありました。")
        return 1

    print("[INFO] 完了しました。")
    return 0


    target_row = rows[target_index]
    if target_row.get("status") == "DONE" and not args.id:
        print("[INFO] すでにDONEのためスキップします。")
        return 0

    try:
        rows[target_index] = process_topic(target_row, dry_run=args.dry_run)
    except Exception as exc:
        rows[target_index] = mark_error(target_row, str(exc))
        save_topics(rows)
        print(f"[ERROR] {exc}")
        return 1

    save_topics(rows)
    print("[INFO] 完了しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
