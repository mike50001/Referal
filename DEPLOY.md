# 🚀 Запуск бота 24/7

Чтобы бот работал круглосуточно, его размещают на сервере в облаке (не на своём
компьютере — он выключается, и бот падает). Ниже два способа.

---

## Способ 1. Railway — самый простой (без терминала)

Railway берёт код прямо из GitHub и запускает его сам. Настройки (токен, ID чата)
вводятся мышкой в веб-панели.

1. Зайди на **https://railway.app** и войди через **GitHub**.
2. Нажми **New Project** → **Deploy from GitHub repo**.
3. Разреши доступ к репозиторию **`mike50001/Referal`** и выбери его.
4. В настройках проекта выбери ветку **`claude/telegram-currency-exchange-bot-0oxsmp`**.
5. Открой вкладку **Variables** и добавь две переменные:
   - `BOT_TOKEN` = токен от @BotFather
   - `ADMIN_CHAT_ID` = ID чата для заявок (твой ID от @userinfobot или ID группы)
   - (по желанию) `ADMIN_IDS` — оставь пустым
6. Railway автоматически соберёт и запустит бота. В логах должно появиться
   `Бот @... запущен`.

Файл `Procfile` в проекте уже говорит Railway, что запускать (`python main.py`),
поэтому дополнительно ничего настраивать не нужно.

> ⚠️ `.env` на сервер загружать НЕ нужно — токен и ID задаются через Variables.

---

## Способ 2. Свой VPS (Linux-сервер)

Подойдёт любой дешёвый VPS (например, с Ubuntu). Нужен доступ по SSH.

```bash
# 1. Установить Python и git (если ещё нет)
sudo apt update && sudo apt install -y python3 python3-pip git

# 2. Скачать проект
git clone https://github.com/mike50001/Referal.git
cd Referal
git checkout claude/telegram-currency-exchange-bot-0oxsmp

# 3. Зависимости
pip3 install -r requirements.txt

# 4. Настройки
cp .env.example .env
nano .env        # впиши BOT_TOKEN и ADMIN_CHAT_ID, сохрани (Ctrl+O, Enter, Ctrl+X)
```

Чтобы бот работал постоянно и сам перезапускался, создай systemd-сервис
`/etc/systemd/system/exchange-bot.service`:

```ini
[Unit]
Description=Telegram Exchange Bot
After=network.target

[Service]
WorkingDirectory=/root/Referal
ExecStart=/usr/bin/python3 /root/Referal/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now exchange-bot
sudo systemctl status exchange-bot     # проверить, что работает
journalctl -u exchange-bot -f          # смотреть логи
```

---

## Способ 3. Docker (на любом сервере с Docker)

В проекте есть `Dockerfile`. Запуск:

```bash
docker build -t exchange-bot .
docker run -d --restart=always \
  -e BOT_TOKEN="токен_от_BotFather" \
  -e ADMIN_CHAT_ID="ID_чата" \
  --name exchange-bot exchange-bot
```

---

**Совет для новичка:** начни со **Способа 1 (Railway)** — он не требует терминала
и настраивается за пару минут.
