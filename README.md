# Telegram-бот-ассистент для продаж контента

Бот ведёт переписку с подписчиками (ответы генерирует Claude) и продаёт
контент за **Telegram Stars** — без внешнего платёжного провайдера.

> ⚠️ Бот работает как **ассистент** от лица модели, а не выдаёт себя за
> живого человека и не ведёт 18+ переписку в тексте. Так задумано намеренно:
> это соответствует правилам Telegram и снижает риск бана. Отредактируй
> персону в `app/persona.py` под свой стиль, оставаясь в этих рамках.

## Стек
- [aiogram 3](https://docs.aiogram.dev/) — Telegram-бот
- [Claude API](https://docs.anthropic.com/) — генерация ответов
- SQLite (`aiosqlite`) — история диалогов и покупки
- Telegram Stars (валюта `XTR`) — оплата

## Структура
```
bot.py              — запуск
config.py           — настройки из .env
app/persona.py      — персона и системный промпт (редактируй под себя)
app/catalog.py      — товары и цены в звёздах
app/llm.py          — обращение к Claude
app/db.py           — SQLite: история и покупки
app/handlers.py     — команды, диалог, оплата, выдача контента
content/            — файлы для продажи (в git не коммитятся)
```

## Быстрый старт
1. Создай бота у [@BotFather](https://t.me/BotFather), получи токен.
2. Узнай свой `user_id` у [@userinfobot](https://t.me/userinfobot).
3. Получи ключ на [console.anthropic.com](https://console.anthropic.com/).
4. Настрой окружение:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # заполни BOT_TOKEN, ANTHROPIC_API_KEY, OWNER_ID
   ```
5. Положи файлы контента в `content/` (имена — как в `app/catalog.py`)
   или подставь Telegram `file_id` в поле `file`.
6. Запусти:
   ```bash
   python bot.py
   ```

## Как работает оплата (Telegram Stars)
- `/shop` показывает каталог с кнопками.
- Нажатие → `send_invoice` с `currency="XTR"`, где `amount` — число звёзд.
- Telegram сам проводит оплату; `provider_token` не нужен.
- После оплаты бот записывает покупку и отправляет файл.
- `telegram_payment_charge_id` сохраняется в БД — по нему можно сделать
  возврат через `refundStarPayment`.

## Что доработать под себя
- `app/persona.py` — стиль общения.
- `app/catalog.py` — товары, цены, файлы.
- Вынести файлы контента в облако/CDN, если их много.
