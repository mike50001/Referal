"""Оффлайн-тесты контента и клавиатуры StuGo Travel."""

from bot.content import (
    SECTIONS,
    button_labels,
    find_section_by_label,
)
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
