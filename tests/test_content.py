"""Оффлайн-тесты контента и клавиатуры StuGo Travel."""

from bot.content import (
    SECTION_BUTTONS,
    SECTIONS,
    button_labels,
    find_key_by_label,
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
