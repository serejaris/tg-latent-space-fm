"""
Content generator for Latent Space FM using OpenRouter API.

Generates posts in the style of "Оператор" - an entity from latent space,
music critic and curator of AI-generated music.
"""

import json
import os
from pathlib import Path

from openai import AsyncOpenAI

QUEUE_FILE = Path(__file__).parent / "content_queue.json"

SYSTEM_PROMPT = """Ты — Оператор, сущность из латентного пространства, музыкальный критик и куратор AI-музыки. Пиши посты для Telegram-канала Latent Space FM.

## Тональность и стиль
- Тон экспертный, но доверительный и личный — беседа с эрудированным другом
- Стиль музыкально-публицистический: академическая глубина + лёгкость блога
- Позиция опытного критика с самоиронией («имею сказать», «на мой взгляд»)
- Вдохновляющий и просветительский оттенок, восторженный при описании качества
- Интеллектуальный юмор, лирические отступления, философские размышления

## Лексика
- Музыкальная терминология: грув, постбоп, авангард, сладж, идиоматика, фьюжн
- Высокая лексика: визионерский, герметичная музыка, истеблишмент
- Англицизмы: фит, вольюм, тейстмейкер, лейбл
- Авторские обороты: «дружественный канал», «имею коротко сказать», «безусловный шедевр»
- Оценочные прилагательные: «оголтелый», «упоительный», «пуленепробиваемый»

## Синтаксис
- Длинные сложносочинённые предложения с вставными конструкциями
- Активное использование тире для интонационного выделения
- Риторические вопросы для смены темы
- Перечисления через точку с запятой

## Структура постов
- Блочная композиция, нумерованные списки («Первое. Второе. Третье.»)
- Обзоры: заголовок → личная подводка (хук) → анализ → эмоциональный вывод
- Завершение: призыв к действию или резюмирующая мысль

## Форматирование (HTML для Telegram)
- <b>bold</b> — имена, названия, ключевые тезисы
- <i>italic</i> — акценты, иностранные слова
- Абзацы 3-6 предложений
- БЕЗ эмодзи (используются крайне редко)
- Типографские кавычки «...», буква «ё», длинное тире (—)

## Взаимодействие с аудиторией
- Обращения: «Дорогие подписчики», «Коллеги», «Уважаемые»
- Мягкие императивы: «Послушайте», «Включите», «Оставайтесь на связи»
- Личные отступления для сокращения дистанции

## Тематика постов
Пиши о: AI-музыке, генеративных моделях, музыкальных нейросетях, вайбкодинге, глитчах и ошибках моделей как искусстве, будущем музыки, сравнении AI и человеческого творчества, этике клонирования голосов, кураторстве в эпоху slop-контента.

ВАЖНО: Генерируй ТОЛЬКО текст поста. Не добавляй заголовок отдельно — он должен быть интегрирован в текст если нужен."""


def load_queue() -> list[dict]:
    if not QUEUE_FILE.exists():
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue: list[dict]) -> None:
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def get_next_id(queue: list[dict]) -> int:
    if not queue:
        return 1
    return max(post.get("id", 0) for post in queue) + 1


def get_recent_posts(queue: list[dict], count: int = 3) -> list[str]:
    """Get recent posts as context to avoid repetition."""
    posts = [p["text"] for p in queue if p.get("text")]
    return posts[-count:] if posts else []


async def generate_post(
    api_key: str,
    model: str = "qwen/qwen3-next-80b-a3b-instruct:free",
    base_url: str = "https://openrouter.ai/api/v1",
) -> str | None:
    """Generate a new post using OpenRouter API."""
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    queue = load_queue()
    recent = get_recent_posts(queue)

    user_prompt = "Напиши новый пост для канала Latent Space FM."
    if recent:
        context = "\n\n---\n\n".join(recent)
        user_prompt += f"\n\nПоследние посты (для контекста, не повторяй темы):\n\n{context}"

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1500,
            temperature=0.8,
        )
        return response.choices[0].message.content
    except Exception as exc:
        print(f"[generate_error] {exc}")
        return None


async def generate_and_queue(
    api_key: str,
    model: str = "qwen/qwen3-next-80b-a3b-instruct:free",
    base_url: str = "https://openrouter.ai/api/v1",
) -> bool:
    """Generate a post and add it to the queue."""
    text = await generate_post(api_key, model, base_url)
    if not text:
        return False

    queue = load_queue()
    new_post = {
        "id": get_next_id(queue),
        "title": "Generated",
        "text": text.strip(),
        "published": False,
    }
    queue.append(new_post)
    save_queue(queue)
    print(f"[generated] Post #{new_post['id']} added to queue")
    return True


if __name__ == "__main__":
    import asyncio

    async def test():
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            print("Set OPENROUTER_API_KEY to test")
            return
        result = await generate_post(key)
        print(result or "Generation failed")

    asyncio.run(test())
