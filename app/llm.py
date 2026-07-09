"""Обёртка над Claude API для генерации ответов бота."""
from anthropic import AsyncAnthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from app.persona import SYSTEM_PROMPT

_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def reply(history: list[dict], user_text: str) -> str:
    """Сгенерировать ответ на основе истории диалога и нового сообщения.

    history — список {'role': 'user'|'assistant', 'content': str} по возрастанию.
    """
    messages = history + [{"role": "user", "content": user_text}]

    response = await _client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    parts = [block.text for block in response.content if block.type == "text"]
    return "".join(parts).strip() or "Прости, я немного отвлеклась 🙈 повтори?"
