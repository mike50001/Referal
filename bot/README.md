# Telegram-бот: VPN-магазин (тарифы, ручная оплата, рефералка)

Бот продаёт доступ к твоему VPN: показывает тарифы, принимает оплату
**ручным подтверждением**, начисляет пригласившему **% на баланс**, и после
подтверждения **сам создаёт ключ в панели 3x-ui** и присылает пользователю
ссылку `vless://`.

## Возможности

- 🔑 Покупка/продление доступа (тарифы редактируются в `tariffs.py`)
- 🧾 Оплата: пользователь переводит по реквизитам → жмёт «Я оплатил» → админу
  прилетает заявка с кнопками **Подтвердить / Отклонить**
- 🎁 Рефералка: `REFERRAL_PERCENT`% от платежа реферала падает пригласившему на
  баланс; балансом можно оплачивать подписку
- ⚙️ Автовыдача: после подтверждения бот создаёт/продлевает клиента в 3x-ui
- 👤 Личный кабинет: срок подписки, ссылка, реф-ссылка и статистика
- 🛠 Админка: пользователи / активные / выручка

## Требования

- Python 3.10+
- Работающая панель 3x-ui с reality-inbound (уже настроена)
- Токен бота от [@BotFather](https://t.me/BotFather)

## Установка на сервере

```bash
cd /root && git clone <этот-репозиторий> referal-bot && cd referal-bot/bot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env          # заполни все поля (см. ниже)
python bot.py      # тестовый запуск; Ctrl+C чтобы остановить
```

### Что вписать в `.env`

| Переменная | Что это |
|---|---|
| `BOT_TOKEN` | токен от @BotFather |
| `ADMIN_IDS` | твой Telegram id (узнать: напиши боту `/id` или [@userinfobot](https://t.me/userinfobot)) |
| `XUI_BASE_URL` | адрес панели **с web base path**, без слэша: `http://IP:2053/xxxxx` |
| `XUI_USERNAME` / `XUI_PASSWORD` | логин/пароль панели |
| `XUI_INBOUND_ID` | ID reality-подключения (колонка ID во «Входящие», обычно `1`) |
| `SERVER_IP` | IP сервера для ссылки `vless://` |
| `CLIENT_FLOW` | `xtls-rprx-vision` (или пусто, если flow не задавали) |
| `REFERRAL_PERCENT` | процент рефереру, напр. `20` |
| `PAYMENT_DETAILS` | твои реквизиты (карта/USDT/СБП) — покажутся пользователю |

## Автозапуск (systemd)

Создай `/etc/systemd/system/vpn-bot.service`:

```ini
[Unit]
Description=VPN Telegram bot
After=network.target

[Service]
WorkingDirectory=/root/referal-bot/bot
EnvironmentFile=/root/referal-bot/bot/.env
ExecStart=/root/referal-bot/bot/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Затем:

```bash
systemctl daemon-reload
systemctl enable --now vpn-bot
systemctl status vpn-bot        # проверить, что active (running)
journalctl -u vpn-bot -f        # логи
```

## Как это работает (поток оплаты)

1. Пользователь: меню → «Купить» → выбирает тариф → «Оплатить (перевод)».
2. Бот показывает реквизиты (`PAYMENT_DETAILS`). Пользователь переводит и жмёт
   «Я оплатил».
3. Тебе (админу) приходит заявка. Проверяешь поступление → **Подтвердить**.
4. Бот создаёт/продлевает клиента в 3x-ui, шлёт пользователю ссылку, начисляет
   рефереру процент.

> Оплата балансом (из реферальных начислений) проходит **мгновенно**, без
> подтверждения.

## Заметки

- Один ключ на пользователя (email в панели = `tg<user_id>`); продление
  добавляет дни к текущему сроку.
- Эндпоинты API — под MHSanaei 3x-ui v2.x (`/panel/api/inbounds/...`). Если у
  тебя другая версия и выдача не срабатывает — смотри `xui.py`.
- Панель по http (без SSL) — для API это ок, но не свети её наружу без нужды.
- Это MVP. Дальше можно добавить: приём скринов оплаты, промокоды, несколько
  серверов, вывод баланса, авто-уведомления об окончании подписки.
