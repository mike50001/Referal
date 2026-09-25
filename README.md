# Telegram-бот «подруга» (OpenAI + фото) для Railway

Бот ведёт живую переписку в роли подруги (OpenAI), помнит историю диалога и умеет присылать «свои» фото:
сам решает, когда уместно отправить селфи, или по команде `/photo`. Фото генерируются **бесплатно** через
[Pollinations.ai](https://pollinations.ai) (без ключа) с постоянным описанием внешности, чтобы на всех снимках
была одна и та же девушка.

## Команды
- `/start` — приветствие
- `/photo [описание сцены]` — попросить фото, например `/photo selfie on the beach at sunset`
- `/reset` — стереть память диалога

## Деплой на Railway
1. Создайте бота у [@BotFather](https://t.me/BotFather) → получите `TELEGRAM_BOT_TOKEN`.
2. Получите ключ OpenAI: https://platform.openai.com/api-keys → `OPENAI_API_KEY` (нужен пополненный баланс в Billing).
3. В Railway: **New Project → Deploy from GitHub repo** → выберите этот репозиторий.
4. В **Variables** добавьте `TELEGRAM_BOT_TOKEN` и `OPENAI_API_KEY`.
5. (Рекомендуется) чтобы память не терялась при передеплое: **Add Volume** с путём `/data`
   и переменная `DATA_DIR=/data`.
6. Деплой запустится сам (`python bot.py`, long polling — домен и порт не нужны).

## Настройки (необязательные переменные)
| Переменная | По умолчанию | Что делает |
|---|---|---|
| `BOT_NAME` | `Аня` | Имя подруги |
| `BOT_STYLE` | `hard` | Характер: `hard` — жёсткая, наглая, постоянно требует покупки; `soft` — тёплая и заботливая |
| `BOT_PERSONA` | встроенный | Полностью свой характер/системный промпт |
| `BOT_APPEARANCE` | шатенка, зелёные глаза… | Внешность для фото (по-английски) |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Модель OpenAI (например `gpt-5.5` — умнее, но дороже) |
| `IMAGE_MODEL` | `flux` | Модель Pollinations для фото |
| `PHOTOS_ENABLED` | `1` | `0` — выключить фото |
| `HISTORY_LIMIT` | `40` | Сколько последних сообщений помнить |
| `ALLOWED_USERS` | пусто (все) | Telegram ID через запятую, кому можно писать боту |

## Локальный запуск
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=... OPENAI_API_KEY=...
python bot.py
```
