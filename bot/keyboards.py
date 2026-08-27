"""Постоянная reply-клавиатура главного меню StuGo Travel."""

from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup

from .content import SECTIONS

# Раскладка меню: списки ключей разделов по рядам.
# Первые разделы — по два в ряд, последние два — на всю ширину
# (как в оригинале: «Важные законы» и «Экскурсии»).
_LAYOUT: list[list[str]] = [
    ["docs", "currency"],
    ["car", "housing"],
    ["license", "tours"],
    ["sim", "apps"],
    ["insurance", "visa"],
    ["laws"],
    ["work"],
    ["channel"],
]


def main_menu() -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    for row in _LAYOUT:
        rows.append([KeyboardButton(SECTIONS[key][0]) for key in row])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выбери раздел 👇",
    )
