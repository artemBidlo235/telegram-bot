# main.py - ИСПРАВЛЕННЫЙ
import asyncio
import sys
from pathlib import Path

# Импортируем ВСЕ переменные из config
from config import (
    API_ID, API_HASH, BOT_TOKEN,
    SESSIONS_DIR, DATA_DIR,
    ADMINS_FILE, USERS_FILE, STATS_FILE, CHAT_FILE,
    DEFAULT_MESSAGE_TEXT, DELAY_BETWEEN_MESSAGES,
    WEB_HOST, WEB_PORT, TIMING_SETTINGS_FILE
)

from telethon import TelegramClient
from modules.data_manager import DataManager
from modules.session_manager import SessionManager
from modules.chat_manager import ChatManager
from modules.broadcaster import Broadcaster
from modules.auth_handler import AuthHandler
from modules.bot_handlers import BotHandlers
from modules.web_server import WebServer
from modules.timing_settings import TimingSettings

async def main():
    print("🚀 ЗАПУСК БОТА...")

    # Создаем папки если их нет
    SESSIONS_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    # Создаем менеджеры
    data_manager = DataManager(ADMINS_FILE, USERS_FILE, STATS_FILE)
    session_manager = SessionManager(SESSIONS_DIR, API_ID, API_HASH)
    chat_manager = ChatManager(CHAT_FILE)
    timing_settings = TimingSettings(TIMING_SETTINGS_FILE)
    broadcaster = Broadcaster(DELAY_BETWEEN_MESSAGES, session_manager=session_manager, timing_settings=timing_settings)
    broadcaster.set_message_text(DEFAULT_MESSAGE_TEXT)
    auth_handler = AuthHandler(SESSIONS_DIR, API_ID, API_HASH)

    # Запускаем веб-сервер
    web_server = WebServer(data_manager, host=WEB_HOST, port=WEB_PORT)
    web_server.start_in_thread()
    print(f"🌐 Веб-сервер запущен на http://{WEB_HOST}:{WEB_PORT}")

    # Создаем клиент бота
    bot_client = await TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    print("✅ Telethon загружен")
    print("✅ БОТ ЗАПУЩЕН!")

    # Загружаем последнюю сессию
    last_session = session_manager.load_active_session()
    if last_session:
        print(f"📁 Загружаем сессию: {last_session}")
        success, msg = await session_manager.switch_to_session(last_session)
        print(msg)
        if success:
            broadcaster.set_client(session_manager.user_client)

    # Инициализация BotHandlers
    handlers = BotHandlers(
        bot_client,
        data_manager,
        session_manager,
        chat_manager,
        broadcaster,
        auth_handler,
        timing_settings
    )

    print("🟢 БОТ ГОТОВ К РАБОТЕ!")
    print("👋 Нажмите Ctrl+C для остановки")
    
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()