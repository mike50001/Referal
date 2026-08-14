"""Оффлайн-тесты контента и клавиатуры StuGo Travel."""

from bot.content import (
    CARS,
    SECTION_BUTTONS,
    SECTIONS,
    button_labels,
    find_key_by_label,
    find_section_by_label,
    get_car,
)
from bot.handlers.cars import PREFIX, _list_keyboard, entry_button
from bot.keyboards import _LAYOUT, main_menu


def test_every_section_has_label_and_body():
    for key, value in SECTIONS.items():
        label, body = value
        assert label.strip(), f"пустая подпись у {key}"
        assert body.strip(), f"пустой текст у {key}"


def test_lookup_by_button_label():
    for label, body in SECTIONS.values():
        assert find_section_by_label(label) == body


def test_unknown_label_returns_none():
    assert find_section_by_label("что-то левое") is None


def test_layout_covers_all_sections_once():
    keys_in_layout = [key for row in _LAYOUT for key in row]
    # Каждый раздел встречается в раскладке ровно один раз.
    assert sorted(keys_in_layout) == sorted(SECTIONS.keys())


def test_keyboard_builds():
    kb = main_menu()
    rendered = [btn.text for row in kb.keyboard for btn in row]
    assert set(rendered) == set(button_labels())


def test_section_buttons_reference_valid_sections():
    for key, buttons in SECTION_BUTTONS.items():
        assert key in SECTIONS, f"кнопка для несуществующего раздела: {key}"
        for label, url in buttons:
            assert label.strip()
            assert url.startswith("https://") or url.startswith("http://")


def test_currency_has_exchanger_button():
    assert "currency" in SECTION_BUTTONS
    labels_urls = SECTION_BUTTONS["currency"]
    assert any("t.me/" in url for _, url in labels_urls)


def test_find_key_by_label():
    for key, (label, _body) in SECTIONS.items():
        assert find_key_by_label(label) == key
    assert find_key_by_label("левый текст") is None


def test_cars_have_unique_ids_and_details():
    ids = [c["id"] for c in CARS]
    assert len(ids) == len(set(ids)), "дублирующиеся id машин"
    for c in CARS:
        assert c["name"].strip()
        assert c["details"].strip()
        assert get_car(c["id"]) is c
    assert get_car("нет такой") is None


def test_car_callbacks_within_telegram_limit():
    # callback_data должен умещаться в 64 байта.
    for c in CARS:
        data = f"{PREFIX}c:{c['id']}"
        assert len(data.encode()) <= 64


def test_car_list_keyboard_covers_all_cars_plus_menu():
    kb = _list_keyboard()
    rows = kb.inline_keyboard
    # Каждая машина + строка «В меню».
    assert len(rows) == len(CARS) + 1
    entry = entry_button()
    assert entry.inline_keyboard[0][0].callback_data == f"{PREFIX}list"
