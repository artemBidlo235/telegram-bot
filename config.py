# КОНФИГУРАЦИЯ БОТА - ПОЛНАЯ ВЕРСИЯ
import os
from pathlib import Path

# Базовые пути
BASE_DIR = Path(__file__).parent
SESSIONS_DIR = BASE_DIR / "sessions"
DATA_DIR = BASE_DIR / "data"

# Файлы данных
USERS_FILE = DATA_DIR / "users.json"
ADMINS_FILE = DATA_DIR / "admins.json"
STATS_FILE = DATA_DIR / "stats.json"
ACTIVE_SESSION_FILE = SESSIONS_DIR / "active_session.txt"
CHAT_FILE = BASE_DIR / "chat.txt"
TIMING_SETTINGS_FILE = DATA_DIR / "timing_settings.json"

# Telegram API данные
def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value

API_ID = int(_require_env("API_ID"))
API_HASH = _require_env("API_HASH")
BOT_TOKEN = _require_env("BOT_TOKEN")

# Настройки рассылки
DEFAULT_MESSAGE_TEXT = "qwerty"
DELAY_BETWEEN_MESSAGES = 5

# Настройки веб-сервера
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 8080))

# Создаем папки
SESSIONS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)