import os
import glob
import asyncio
from pathlib import Path
from typing import Optional, Tuple, List

from telethon import TelegramClient


class SessionManager:
    def __init__(self, sessions_dir: Path, api_id: int, api_hash: str):
        self.sessions_dir = sessions_dir
        self.api_id = api_id
        self.api_hash = api_hash
        self.user_client: Optional[TelegramClient] = None
        self.active_session_file = sessions_dir / "active_session.txt"

    def save_active_session(self, session_name: str) -> bool:
        try:
            with open(self.active_session_file, "w", encoding="utf-8") as f:
                f.write(session_name)
            return True
        except Exception:
            return False

    def load_active_session(self) -> Optional[str]:
        try:
            with open(self.active_session_file, "r", encoding="utf-8") as f:
                session_name = f.read().strip()
            session_path = self.sessions_dir / session_name
            if session_name and session_path.exists():
                return session_name
        except Exception:
            pass
        return None

    def get_session_files(self) -> List[str]:
        session_files = glob.glob(str(self.sessions_dir / "*.session"))
        sessions = []
        for f in session_files:
            basename = os.path.basename(f)
            if not basename.startswith("bot_session") and not basename.startswith("temp_"):
                sessions.append(basename)
        return sorted(sessions)

    def get_session_path(self, session_name: str) -> Path:
        return self.sessions_dir / session_name

    def get_current_session_name(self) -> Optional[str]:
        if self.user_client and hasattr(self.user_client, "session"):
            try:
                return os.path.basename(str(self.user_client.session.filename))
            except Exception:
                pass
        return None

    async def force_close_current_session(self) -> None:
        if self.user_client:
            try:
                if self.user_client.is_connected():
                    await self.user_client.disconnect()
            except Exception:
                pass
            self.user_client = None
            await asyncio.sleep(0.2)

    async def switch_to_session(self, session_name: str) -> Tuple[bool, str]:
        await self.force_close_current_session()
        session_path = self.sessions_dir / session_name
        try:
            new_client = TelegramClient(str(session_path), self.api_id, self.api_hash)
            await new_client.connect()
            if await new_client.is_user_authorized():
                self.user_client = new_client
                self.save_active_session(session_name)
                me = await self.user_client.get_me()
                title = getattr(me, "username", None) or getattr(me, "first_name", None) or session_name
                return True, f"✅ Переключено на: {title}"
            await new_client.disconnect()
            return False, f"❌ Сессия {session_name} не авторизована"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"

    async def open_session_client(self, session_name: str):
        session_path = self.sessions_dir / session_name
        client = None
        try:
            client = TelegramClient(str(session_path), self.api_id, self.api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, None, None
            me = await client.get_me()
            display_name = getattr(me, "username", None) or getattr(me, "first_name", None) or session_name
            return True, client, display_name
        except Exception:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            return False, None, None

    async def delete_session(self, session_name: str) -> Tuple[bool, str]:
        current = self.get_current_session_name()
        if current == session_name:
            return False, "⚠️ Нельзя удалить активную сессию"

        session_path = self.sessions_dir / session_name
        try:
            os.remove(session_path)
            for ext in [".json", ".lock", ".journal"]:
                f = str(session_path) + ext
                if os.path.exists(f):
                    os.remove(f)
            return True, f"✅ Сессия {session_name} удалена"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"
