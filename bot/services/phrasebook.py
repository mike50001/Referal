"""Мини-разговорник базовых фраз на популярных языках."""

from __future__ import annotations

# Ключевые фразы для путешественника по языкам.
PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "lang": "🇬🇧 Английский",
        "Здравствуйте": "Hello",
        "Спасибо": "Thank you",
        "Пожалуйста": "Please / You're welcome",
        "Да / Нет": "Yes / No",
        "Извините": "Excuse me / Sorry",
        "Сколько стоит?": "How much is it?",
        "Где туалет?": "Where is the toilet?",
        "Помогите!": "Help!",
        "Я не понимаю": "I don't understand",
        "Вызовите врача": "Call a doctor",
    },
    "es": {
        "lang": "🇪🇸 Испанский",
        "Здравствуйте": "Hola",
        "Спасибо": "Gracias",
        "Пожалуйста": "Por favor / De nada",
        "Да / Нет": "Sí / No",
        "Извините": "Perdón / Lo siento",
        "Сколько стоит?": "¿Cuánto cuesta?",
        "Где туалет?": "¿Dónde está el baño?",
        "Помогите!": "¡Ayuda!",
        "Я не понимаю": "No entiendo",
        "Вызовите врача": "Llame a un médico",
    },
    "fr": {
        "lang": "🇫🇷 Французский",
        "Здравствуйте": "Bonjour",
        "Спасибо": "Merci",
        "Пожалуйста": "S'il vous plaît / De rien",
        "Да / Нет": "Oui / Non",
        "Извините": "Excusez-moi / Pardon",
        "Сколько стоит?": "Combien ça coûte ?",
        "Где туалет?": "Où sont les toilettes ?",
        "Помогите!": "Au secours !",
        "Я не понимаю": "Je ne comprends pas",
        "Вызовите врача": "Appelez un médecin",
    },
    "de": {
        "lang": "🇩🇪 Немецкий",
        "Здравствуйте": "Hallo / Guten Tag",
        "Спасибо": "Danke",
        "Пожалуйста": "Bitte",
        "Да / Нет": "Ja / Nein",
        "Извините": "Entschuldigung",
        "Сколько стоит?": "Wie viel kostet das?",
        "Где туалет?": "Wo ist die Toilette?",
        "Помогите!": "Hilfe!",
        "Я не понимаю": "Ich verstehe nicht",
        "Вызовите врача": "Rufen Sie einen Arzt",
    },
    "it": {
        "lang": "🇮🇹 Итальянский",
        "Здравствуйте": "Ciao / Buongiorno",
        "Спасибо": "Grazie",
        "Пожалуйста": "Per favore / Prego",
        "Да / Нет": "Sì / No",
        "Извините": "Scusi / Mi dispiace",
        "Сколько стоит?": "Quanto costa?",
        "Где туалет?": "Dov'è il bagno?",
        "Помогите!": "Aiuto!",
        "Я не понимаю": "Non capisco",
        "Вызовите врача": "Chiami un medico",
    },
    "tr": {
        "lang": "🇹🇷 Турецкий",
        "Здравствуйте": "Merhaba",
        "Спасибо": "Teşekkürler",
        "Пожалуйста": "Lütfen / Rica ederim",
        "Да / Нет": "Evet / Hayır",
        "Извините": "Affedersiniz / Özür dilerim",
        "Сколько стоит?": "Ne kadar?",
        "Где туалет?": "Tuvalet nerede?",
        "Помогите!": "İmdat!",
        "Я не понимаю": "Anlamıyorum",
        "Вызовите врача": "Doktor çağırın",
    },
}


def available_languages() -> list[tuple[str, str]]:
    """Список (код, отображаемое имя) доступных языков."""
    return [(code, data["lang"]) for code, data in PHRASES.items()]


def phrases_for(code: str) -> dict[str, str] | None:
    return PHRASES.get(code)
