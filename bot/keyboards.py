"""Клавиатуры бота."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

# Публичный адрес Mini App; задаётся при старте из config.webapp_url.
_WEBAPP_URL = ""


def set_webapp_url(url: str) -> None:
    global _WEBAPP_URL
    _WEBAPP_URL = url or ""


# Валюты для кнопок: (код, подпись на кнопке).
# Код уходит в заявку менеджеру, подпись видит клиент.
# Клиент также может ввести свою валюту вручную.
CURRENCIES: list[tuple[str, str]] = [
    ("KZT", "🇰🇿 Тенге"),
    ("RUB", "🇷🇺 Рубль"),
    ("THB", "🇹🇭 Тайский бат"),
    ("USDT", "💵 USDT"),
]


def start_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="💱 Оставить заявку на обмен")],
        [KeyboardButton(text="📈 Узнать курс")],
    ]
    if _WEBAPP_URL.startswith("https://"):
        rows.append([
            KeyboardButton(
                text="📱 Приложение",
                web_app=WebAppInfo(url=_WEBAPP_URL),
            )
        ])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
    )


def currency_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура выбора валюты.

    prefix используется, чтобы различать шаг «отдаю» и «получаю»
    в callback_data (give / get).
    """
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, (code, label) in enumerate(CURRENCIES, start=1):
        row.append(
            InlineKeyboardButton(text=label, callback_data=f"{prefix}:{code}")
        )
        if i % 2 == 0:  # по 2 кнопки в ряд
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text="✍️ Другая валюта", callback_data=f"{prefix}:custom")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def amount_side_keyboard() -> InlineKeyboardMarkup:
    """Как клиент задаёт сумму: сколько отдаёт или сколько хочет получить."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💸 Указать сумму, которую отдаю", callback_data="side:give")],
            [InlineKeyboardButton(text="🎯 Указать сумму, которую хочу получить", callback_data="side:get")],
        ]
    )


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="confirm:yes"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="confirm:no"),
            ]
        ]
    )
