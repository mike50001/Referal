"""Движок FAQ-автоответчика: сопоставляет сообщение с правилами из faq.json.

Логика простая и предсказуемая (без ИИ):
  - текст нормализуется (нижний регистр, убираем лишнее);
  - для каждого правила ищем вхождение его триггеров как подстрок;
  - выигрывает правило с самым «специфичным» совпадением (сумма длин
    совпавших триггеров) — так «время работы» победит одиночное «работа»;
  - если совпадений нет — отдаём fallback.
Команды «меню»/«menu»/«/start» показывают приветствие и список тем.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


@dataclass
class Rule:
    name: str
    triggers: list[str]
    answer: str


class FaqEngine:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(os.path.dirname(__file__), "faq.json")
        self.welcome = ""
        self.fallback = ""
        self.menu_title = ""
        self.rules: list[Rule] = []
        self.load()

    def load(self) -> None:
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self.welcome = data.get("welcome", "Здравствуйте!")
        self.fallback = data.get("fallback", "Не понял вопрос.")
        self.menu_title = data.get("menu_title", "Темы:")
        self.rules = [
            Rule(r.get("name", ""), [t.lower() for t in r["triggers"]], r["answer"])
            for r in data.get("rules", [])
        ]

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().replace("ё", "е")
        # оставляем буквы/цифры/пробелы, остальное в пробелы
        text = re.sub(r"[^0-9a-zа-я ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def menu(self) -> str:
        lines = [self.menu_title]
        for r in self.rules:
            if r.name:
                lines.append(f"• {r.name}")
        return "\n".join(lines)

    def reply(self, text: str) -> str:
        norm = self._normalize(text)
        if not norm:
            return self.fallback
        if norm in ("меню", "menu", "start", "помощь", "help"):
            return f"{self.welcome}\n\n{self.menu()}"

        best_rule, best_score = None, 0
        for rule in self.rules:
            score = 0
            for trig in rule.triggers:
                t = self._normalize(trig)
                if t and t in norm:
                    score += len(t)
            if score > best_score:
                best_rule, best_score = rule, score

        if best_rule is not None:
            ans = best_rule.answer
            return self.welcome if ans == "__welcome__" else ans
        return self.fallback


if __name__ == "__main__":
    # быстрый ручной тест
    eng = FaqEngine()
    for q in ["привет", "сколько стоит?", "во сколько вы работаете",
              "где вы находитесь", "как оплатить картой", "бла бла", "меню"]:
        print(f"[{q}] -> {eng.reply(q)[:60]}")
