# Деплой бота на VPS (Hetzner)

Пошаговая инструкция, как развернуть бота на сервере, чтобы он торговал
круглосуточно без твоего компьютера. Все команды выполняются на сервере,
если не указано иное.

---

## 1. Создать сервер в Hetzner Cloud

1. Зарегистрируйся на **https://www.hetzner.com/cloud** → войди в **Cloud Console**
   (https://console.hetzner.cloud).
2. **New Project** → назови как угодно (напр. `trading`).
3. **Add Server**:
   - **Location**: Nuremberg / Falkenstein / Helsinki (Германия/Финляндия).
     ⚠️ НЕ выбирай США — Binance блокирует US-IP.
   - **Image**: **Ubuntu 24.04**.
   - **Type**: самый дешёвый, напр. **CX22** (2 vCPU / 4 GB, ~€4/мес) — с запасом.
   - **SSH Key**: если есть — добавь; если нет — оставь пароль (Hetzner пришлёт
     root-пароль на почту). Для простоты можно с паролем.
   - Остальное по умолчанию → **Create & Buy Now**.
4. Запиши **IP-адрес** сервера (вида `95.217.xx.xx`).

## 2. Подключиться к серверу по SSH (с мака)

В Terminal на маке:

```bash
ssh root@ВАШ_IP
```

- При первом подключении спросит `yes/no` → набери `yes`.
- Введи пароль (из письма Hetzner) или подключится по SSH-ключу.
- Если попросит сменить пароль при первом входе — смени и запомни.

Ты на сервере, когда приглашение выглядит как `root@ubuntu:~#`.

## 3. Установить зависимости

```bash
apt update && apt install -y python3 python3-venv python3-pip git
```

## 4. Скачать проект

```bash
cd /root
git clone https://github.com/mike50001/referal.git
cd referal
git checkout claude/session-ghnpqa
```

## 5. Настроить окружение

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6. Создать .env с ключами

Файл `.env` НЕ хранится в git — создаём его на сервере:

```bash
cp .env.example .env
nano .env
```

В редакторе `nano`:
- впиши `BINANCE_API_KEY=...` и `BINANCE_API_SECRET=...`;
- проверь `USE_TESTNET=true` и `DRY_RUN=false`;
- сохранить: **Ctrl+O**, Enter; выйти: **Ctrl+X**.

Быстрая проверка, что бот стартует (10–20 сек, затем Ctrl+C):

```bash
python3 bot.py
```

Если видишь строки `price=... rsi=...` — всё работает. Останови (**Ctrl+C**).

## 7. Автозапуск через systemd (бот работает 24/7)

Скопировать юнит и включить сервис:

```bash
cp /root/referal/deploy/trading-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable trading-bot     # автозапуск при перезагрузке сервера
systemctl start trading-bot      # запустить сейчас
```

Проверить статус:

```bash
systemctl status trading-bot
```

Должно быть `active (running)`. Теперь можно закрыть Terminal и выключить мак —
бот работает на сервере.

## 8. Управление ботом

```bash
# посмотреть живой лог
journalctl -u trading-bot -f          # выход из просмотра — Ctrl+C

# последние 100 строк лога
journalctl -u trading-bot -n 100

# остановить / запустить / перезапустить
systemctl stop trading-bot
systemctl start trading-bot
systemctl restart trading-bot
```

## 9. Обновить бота после изменений в коде

```bash
cd /root/referal
git pull
source .venv/bin/activate
pip install -r requirements.txt      # если менялись зависимости
systemctl restart trading-bot
```

## 10. Изменить настройки (.env)

```bash
nano /root/referal/.env
systemctl restart trading-bot        # чтобы применить
```

---

## Безопасность (важно)

- На сервере лежит `.env` с ключами — не давай к нему доступ посторонним.
- Ключ Binance должен быть **без права вывода средств**, желательно с
  привязкой к IP сервера (IP restriction в настройках API-ключа).
- Начинай с `USE_TESTNET=true`. Переходить на реальные деньги — только после
  долгого успешного теста и осознанно.
- Смени/усиль root-пароль сервера; по возможности используй SSH-ключи.
