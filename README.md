# 🧭 Telegram-бот путешественника

Бот-помощник для путешественников: погода, конвертация валют, справка о
странах, местное время, разговорник и чек-листы для сборов. Работает
«из коробки» — все внешние сервисы бесплатны и **не требуют API-ключей**
(нужен только токен самого бота).

## ✨ Возможности

| Команда | Что делает | Пример |
|---|---|---|
| `/weather` | Текущая погода в городе | `/weather Париж` |
| `/currency` | Конвертация валют по курсу ЕЦБ | `/currency 100 USD RUB` |
| `/country` | Справка о стране (столица, валюта, язык, код…) | `/country Япония` |
| `/time` | Местное время в городе | `/time Токио` |
| `/phrases` | Разговорник базовых фраз (6 языков) | `/phrases` |
| `/checklist` | Чек-листы для сборов в поездку | `/checklist` |
| `/help` | Список команд | `/help` |

Разговорник и чек-листы используют inline-кнопки для выбора языка/категории.

## 🔌 Используемые сервисы (бесплатные, без ключей)

- **[Open-Meteo](https://open-meteo.com/)** — погода и геокодирование городов
- **[Frankfurter](https://www.frankfurter.app/)** — курсы валют (данные ЕЦБ)
- **[REST Countries](https://restcountries.com/)** — информация о странах

## 🚀 Запуск

### 1. Получите токен бота

Напишите [@BotFather](https://t.me/BotFather) в Telegram, создайте бота
командой `/newbot` и скопируйте выданный токен.

### 2. Установите зависимости

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Настройте окружение

```bash
cp .env.example .env
# откройте .env и вставьте BOT_TOKEN
```

### 4. Запустите

```bash
python run.py
```

Бот работает в режиме long polling — внешний веб-сервер не нужен.

## ☁️ Деплой на Railway

Бот готов к деплою на [Railway](https://railway.app/) «из коробки».

1. Зайдите на Railway → **New Project** → **Deploy from GitHub repo** и
   выберите этот репозиторий (ветку с ботом).
2. Railway сам определит Python-проект (через Nixpacks) и установит
   зависимости из `requirements.txt`.
3. Откройте вкладку **Variables** и добавьте переменную окружения:
   - `BOT_TOKEN` — токен вашего бота от [@BotFather](https://t.me/BotFather).
   - (необязательно) `LOG_LEVEL` — например `INFO`.
4. Нажмите **Deploy**. Бот запустится как worker-процесс (`python run.py`)
   и начнёт принимать сообщения.

> ⚠️ **Никогда не коммитьте токен в код.** Токен задаётся только в
> переменных окружения Railway. Файл `.env` добавлен в `.gitignore`.

Конфигурация деплоя уже включена в репозиторий:

| Файл | Назначение |
|---|---|
| `Procfile` | процесс `worker: python run.py` |
| `railway.json` | параметры сборки и запуска, политика перезапуска |
| `nixpacks.toml` | фиксация версии Python и команд сборки |
| `runtime.txt` | версия Python (`3.11`) |

Так как бот работает через long polling, **HTTP-порт не требуется** — это
именно worker, а не web-сервис.

## 🧪 Тесты

```bash
pip install pytest
python -m pytest tests/ -q
```

Тесты проверяют чистую логику (без обращения к сети).

## 📁 Структура проекта

```
bot/
├── main.py            # сборка и запуск приложения
├── config.py          # конфигурация из переменных окружения
├── handlers/          # обработчики команд Telegram
│   ├── common.py      # /start, /help, ошибки
│   ├── weather.py     # /weather
│   ├── currency.py    # /currency
│   ├── country.py     # /country
│   ├── time.py        # /time
│   ├── phrases.py     # /phrases (inline-кнопки)
│   └── checklist.py   # /checklist (inline-кнопки)
└── services/          # клиенты внешних API и данные
    ├── http.py        # общий HTTP-клиент с ретраями
    ├── geocoding.py   # поиск городов
    ├── weather.py     # погода
    ├── currency.py    # валюты
    ├── country.py     # страны
    ├── localtime.py   # часовые пояса
    ├── phrasebook.py  # разговорник
    └── checklist.py   # чек-листы
tests/                 # оффлайн-тесты
run.py                 # точка входа
```

## 🛠 Технологии

- Python 3.11+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 21.x (async)
- [httpx](https://www.python-httpx.org/) — асинхронные HTTP-запросы

## 📝 Особенности реализации

- Асинхронная архитектура на `asyncio`.
- Единый HTTP-клиент с пулом соединений и повторными запросами при
  сетевых сбоях (экспоненциальная задержка).
- Понятные пользователю сообщения об ошибках при недоступности сервисов.
- Модульная структура: сервисы отделены от обработчиков команд.
- Меню команд бота настраивается автоматически при запуске.
