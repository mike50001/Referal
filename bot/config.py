"""Конфиг бота. Читает переменные из окружения (.env через systemd EnvironmentFile
или экспорт в шелле). Ничего секретного в коде не храним."""
import os


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


BOT_TOKEN = _get("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in _get("ADMIN_IDS").replace(" ", "").split(",") if x]

# --- 3x-ui ---
XUI_BASE_URL = _get("XUI_BASE_URL").rstrip("/")
XUI_USERNAME = _get("XUI_USERNAME")
XUI_PASSWORD = _get("XUI_PASSWORD")
XUI_INBOUND_ID = int(_get("XUI_INBOUND_ID", "1"))
SERVER_IP = _get("SERVER_IP")
CLIENT_FLOW = _get("CLIENT_FLOW", "xtls-rprx-vision")

# --- рефералка ---
REFERRAL_PERCENT = float(_get("REFERRAL_PERCENT", "20"))

# --- оплата ---
CURRENCY = _get("CURRENCY", "руб.")
PAYMENT_DETAILS = _get("PAYMENT_DETAILS", "Реквизиты не заданы").replace("\\n", "\n")

DB_PATH = _get("DB_PATH", os.path.join(os.path.dirname(__file__), "bot.db"))


def validate() -> None:
    missing = [n for n in ("BOT_TOKEN", "XUI_BASE_URL", "XUI_USERNAME",
                           "XUI_PASSWORD", "SERVER_IP") if not globals()[n]]
    if missing:
        raise SystemExit(f"Не заданы переменные окружения: {', '.join(missing)}. "
                         f"Скопируй .env.example в .env и заполни.")
    if not ADMIN_IDS:
        raise SystemExit("ADMIN_IDS пуст — укажи свой Telegram id.")
