# FAQ авто-ответчик (Telegram + WhatsApp)

Отвечает на входящие сообщения готовыми ответами по правилам (без ИИ).
Ответы редактируются в одном файле — `autoresponder/faq.json`.

| Файл | Что делает |
|------|-----------|
| `faq.json`        | Вопросы-триггеры и ответы (редактируй под себя) |
| `faq_engine.py`   | Движок сопоставления сообщения с правилами |
| `telegram_bot.py` | Telegram-бот (long polling) |
| `whatsapp_bot.py` | WhatsApp-вебхук (Meta Cloud API) |

## Как редактировать ответы

Открой `autoresponder/faq.json`. Каждый блок в `rules`:
```json
{ "name": "Цена", "triggers": ["цена", "сколько стоит"], "answer": "Наши цены ..." }
```
- `triggers` — слова/фразы, при которых срабатывает ответ (в любом регистре);
- `answer` — что бот ответит.
Добавляй свои блоки, меняй тексты. После правок — перезапусти сервис.

---

## Часть 1. Telegram (быстро, бесплатно)

### 1. Создать бота
1. В Telegram напиши **@BotFather** → команда **/newbot**.
2. Задай имя и username бота → BotFather пришлёт **токен** вида
   `123456:ABC-DEF...`.

### 2. Настроить и запустить (на сервере)
```bash
cd /root/referal/autoresponder
cp .env.example .env
nano .env          # вставь TELEGRAM_BOT_TOKEN, сохрани Ctrl+O, выйди Ctrl+X
/root/referal/.venv/bin/pip install -r requirements.txt
/root/referal/.venv/bin/python telegram_bot.py     # тест; Ctrl+C для остановки
```
Напиши своему боту в Telegram — он должен ответить.

### 3. Автозапуск 24/7
```bash
cp /root/referal/autoresponder/autoresponder-tg.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable autoresponder-tg
systemctl start autoresponder-tg
systemctl status autoresponder-tg          # active (running)
```
Логи: `journalctl -u autoresponder-tg -f`

---

## Часть 2. WhatsApp (Meta Cloud API)

WhatsApp сложнее: нужен бизнес-аккаунт Meta и HTTPS-вебхук.

### 1. Регистрация в Meta
1. Зайди на **https://developers.facebook.com** → создай аккаунт разработчика.
2. **Create App** → тип **Business** → добавь продукт **WhatsApp**.
3. В разделе WhatsApp → **API Setup** получи:
   - **Temporary access token** (или настрой постоянный) → `WHATSAPP_TOKEN`;
   - **Phone number ID** → `WHATSAPP_PHONE_ID`.
4. Придумай любую строку для `WHATSAPP_VERIFY_TOKEN` (например `my-secret-123`).

### 2. HTTPS для вебхука
Meta принимает вебхук только по HTTPS. Варианты:
- поставить **Caddy/nginx** с доменом и TLS перед портом 8080;
- либо на старте протестировать через туннель (напр. `cloudflared`/`ngrok`).

### 3. Настроить вебхук в Meta
1. В настройках WhatsApp → **Configuration → Webhook** укажи:
   - **Callback URL**: `https://ВАШ_ДОМЕН/webhook`
   - **Verify token**: та же строка, что в `WHATSAPP_VERIFY_TOKEN`.
2. Подпишись на поле **messages**.

### 4. Запуск
```bash
cd /root/referal/autoresponder
nano .env          # заполни WHATSAPP_TOKEN / WHATSAPP_PHONE_ID / WHATSAPP_VERIFY_TOKEN
/root/referal/.venv/bin/python whatsapp_bot.py
```

> ⚠️ Не используй «неофициальные» WhatsApp-библиотеки (whatsapp-web.js и пр.) —
> это нарушение правил WhatsApp и риск блокировки номера. Только Cloud API.

---

## Безопасность
- `.env` с токенами не коммить (уже в `.gitignore`).
- Токен Telegram/WhatsApp — как пароль, никому не показывай.
- Начинай с Telegram; WhatsApp подключай, когда TG-бот работает как надо.
