# 🌴 STU GO TRAVEL — бот-гид по переезду на Пхукет

Telegram-бот: личный гид по переезду и жизни на Пхукете. Собирает всё
важное в одном месте — документы, визы, жильё, деньги, законы — и выдаёт
по разделам через удобное меню-клавиатуру.

Это Python-версия бота (`@StuGoTravelMoveBot`), готовая к деплою на Railway.

## 🧩 Как устроен бот

- `/start` — приветствие + постоянная клавиатура с разделами.
- Каждая кнопка выдаёт свой раздел с информацией.
- `/menu` — вернуть клавиатуру, если её скрыли.

### Разделы (кнопки меню)

📝 Документы для переезда • 💸 Обмен валют • 🚗 Аренда авто •
🏠 Аренда жилья • 🪪 Водительские права • 💼 Работа в Таиланде •
📱 Связь и приложения • 🛡 Страховка • 🛂 Визы и продление •
⚖️ Важные законы • 🌴 Экскурсии

> Тексты разделов в `bot/content.py` — рабочий черновик. Замените значения
> на свои финальные тексты: структура и кнопки при этом не меняются.

## 🚀 Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # вставьте BOT_TOKEN в .env
python run.py
```

Токен берётся у [@BotFather](https://t.me/BotFather). Бот работает через
long polling — веб-сервер не нужен.

## ☁️ Деплой на Railway

1. Railway → **New Project** → **Deploy from GitHub repo** → выберите этот
   репозиторий и ветку с ботом.
2. Railway сам определит Python-проект (Nixpacks) и поставит зависимости.
3. Вкладка **Variables** → добавьте переменную:
   - `BOT_TOKEN` — токен бота от @BotFather (тот же, что у `@StuGoTravelMoveBot`).
   - (необязательно) `LOG_LEVEL` — например `INFO`.
4. **Deploy** — бот запустится как worker (`python run.py`).

> ⚠️ Токен задаётся только в переменных окружения Railway, в код не
> коммитится (`.env` в `.gitignore`).

Конфигурация деплоя уже в репозитории:

| Файл | Назначение |
|---|---|
| `Procfile` | процесс `worker: python run.py` |
| `railway.json` | параметры сборки/запуска, автоперезапуск |
| `nixpacks.toml` | версия Python и команды сборки |
| `runtime.txt` | версия Python (3.11) |

## 🧪 Тесты

```bash
pip install pytest
python -m pytest tests/ -q
```

## 📁 Структура

```
bot/
├── main.py          # сборка и запуск приложения
├── config.py        # конфигурация (BOT_TOKEN из окружения)
├── content.py       # тексты: приветствие и разделы по кнопкам
├── keyboards.py     # постоянная клавиатура-меню
└── handlers/
    ├── start.py     # /start, /menu — приветствие и меню
    └── sections.py  # реакция на нажатие кнопок разделов
tests/               # оффлайн-тесты контента и клавиатуры
run.py               # точка входа
```

## 🛠 Технологии

- Python 3.11+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 21.x (async)
