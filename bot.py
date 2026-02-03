"""
Telegram bot that posts content from queue.

Settings:
  BOT_TOKEN   - bot token
  CHANNEL_ID  - channel id or @username
  OPENROUTER_API_KEY - API key for content generation (optional)
  OPENROUTER_MODEL - model to use (default: qwen/qwen3-next-80b-a3b-instruct:free)
  GENERATE_INTERVAL_HOURS - hours between generations (default: 1)

Run:
  python bot.py
"""

import asyncio
import json
import os
from pathlib import Path

from aiogram import Bot

from content_generator import generate_and_queue

INTERVAL_SECONDS = 60  # 1 minute between posts
GENERATE_INTERVAL_HOURS = 1  # default, can be overridden by env
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


async def publish_loop(bot: Bot, channel_id: int | str) -> None:
    """Publish posts from queue at regular intervals."""
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


async def generate_loop(
    api_key: str,
    model: str,
    interval_hours: float,
) -> None:
    """Generate new posts at regular intervals using OpenRouter."""
    interval_seconds = interval_hours * 3600
    print(f"[generator] Will generate every {interval_hours}h")

    # Generate first post immediately on startup
    print("[generator] Generating first post on startup...")
    success = await generate_and_queue(api_key, model)
    if success:
        print("[generator] First post generated successfully")
    else:
        print("[generator] First generation failed, will retry next cycle")

    while True:
        await asyncio.sleep(interval_seconds)
        print("[generator] Generating new post...")
        success = await generate_and_queue(api_key, model)
        if not success:
            print("[generator] Generation failed, will retry next cycle")


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

    # Build list of tasks to run
    tasks = [publish_loop(bot, channel_id)]

    # Add generation loop if API key is configured
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free")
        interval = float(os.getenv("GENERATE_INTERVAL_HOURS", GENERATE_INTERVAL_HOURS))
        tasks.append(generate_loop(openrouter_key, model, interval))
        print(f"[startup] Auto-generation enabled (model: {model})")
    else:
        print("[startup] Auto-generation disabled (no OPENROUTER_API_KEY)")

    try:
        await asyncio.gather(*tasks)
    finally:
        await bot.session.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nBot stopped.")
