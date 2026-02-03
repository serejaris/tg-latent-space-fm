"""
Telegram bot that posts content from queue.

Settings:
  BOT_TOKEN   - bot token
  CHANNEL_ID  - channel id or @username

Run:
  python bot.py
"""

import asyncio
import json
import os
from pathlib import Path

from aiogram import Bot

INTERVAL_SECONDS = 60  # 1 minute between posts
QUEUE_FILE = Path(__file__).parent / "content_queue.json"


def load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def normalize_channel_id(value: str) -> int | str:
    value = value.strip()
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def load_queue() -> list[dict]:
    if not QUEUE_FILE.exists():
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue: list[dict]) -> None:
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def get_next_post(queue: list[dict]) -> dict | None:
    for post in queue:
        if not post.get("published", False):
            return post
    return None


def mark_published(queue: list[dict], post_id: int) -> None:
    for post in queue:
        if post.get("id") == post_id:
            post["published"] = True
            break
    save_queue(queue)


async def send_post(bot: Bot, channel_id: int | str, text: str) -> bool:
    try:
        await bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode="HTML"
        )
        return True
    except Exception as exc:
        print(f"[send_error] {exc}")
        return False


async def run_loop(bot: Bot, channel_id: int | str) -> None:
    while True:
        queue = load_queue()
        post = get_next_post(queue)

        if post is None:
            print("[info] Queue empty. Waiting for new content...")
            await asyncio.sleep(INTERVAL_SECONDS)
            continue

        print(f"[posting] #{post['id']}: {post.get('title', 'Untitled')}")
        success = await send_post(bot, channel_id, post["text"])

        if success:
            mark_published(queue, post["id"])
            print(f"[done] Post #{post['id']} published")

        await asyncio.sleep(INTERVAL_SECONDS)


async def main() -> int:
    load_env_file()
    token = os.getenv("BOT_TOKEN")
    channel_raw = os.getenv("CHANNEL_ID")
    if not token or not channel_raw:
        print("Set BOT_TOKEN and CHANNEL_ID in environment variables.")
        return 1

    channel_id = normalize_channel_id(channel_raw)
    bot = Bot(token=token)

    queue = load_queue()
    unpublished = sum(1 for p in queue if not p.get("published", False))
    print(f"[startup] {unpublished} posts in queue")

    try:
        await run_loop(bot, channel_id)
    finally:
        await bot.session.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nBot stopped.")
