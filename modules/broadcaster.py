from __future__ import annotations

import asyncio
from typing import Callable, Awaitable, Optional, Dict, Any, List

from telethon.errors import FloodWaitError


ProgressCb = Optional[Callable[[Dict[str, Any]], Awaitable[None]]]


class Broadcaster:
    def __init__(self, delay: int = 5, session_manager=None, timing_settings=None):
        self.delay = delay
        self.session_manager = session_manager
        self.timing_settings = timing_settings
        self.is_broadcasting = False
        self.current_client = None
        self.current_text = "qwerty"

    def set_client(self, client):
        self.current_client = client

    def set_message_text(self, text: str):
        self.current_text = text

    def stop(self):
        self.is_broadcasting = False

    def _get_delay(self) -> int:
        if self.timing_settings:
            return self.timing_settings.get_broadcast_delay()
        return self.delay

    def _get_limit(self) -> int:
        if self.timing_settings:
            return self.timing_settings.get_account_message_limit()
        return 50

    def _is_account_block_error(self, exc: Exception) -> bool:
        text = f"{exc}".lower()
        keys = [
            "deactivated", "banned", "restricted", "forbidden", "privacy", "write forbidden",
            "you can't write", "can\'t send", "send messages", "user is blocked", "auth key", "revoked"
        ]
        return any(k in text for k in keys)

    async def _emit(self, progress_cb: ProgressCb, **payload):
        if progress_cb:
            await progress_cb(payload)

    async def send_to_chats(self, chat_ids: List[int], progress_cb: ProgressCb = None) -> tuple:
        if self.is_broadcasting:
            return 0, 0, "⏳ Рассылка уже идёт"
        sessions = self.session_manager.get_session_files() if self.session_manager else []
        if not sessions and not self.current_client:
            return 0, 0, "❌ Не авторизован"

        self.is_broadcasting = True
        success = 0
        fail = 0
        index = 0
        total = len(chat_ids)
        sessions_queue = list(sessions)
        using_temp_clients = bool(sessions_queue)
        active_client = None if using_temp_clients else self.current_client
        active_label = "активная сессия"
        sent_on_current = 0
        account_pointer = -1

        async def next_client(reason: str = ""):
            nonlocal active_client, active_label, sent_on_current, account_pointer
            if using_temp_clients:
                if active_client:
                    try:
                        await active_client.disconnect()
                    except Exception:
                        pass
                    active_client = None
                account_pointer += 1
                while account_pointer < len(sessions_queue):
                    session_name = sessions_queue[account_pointer]
                    ok, client, display_name = await self.session_manager.open_session_client(session_name)
                    if ok and client:
                        active_client = client
                        active_label = display_name or session_name
                        sent_on_current = 0
                        await self._emit(progress_cb, stage="switch", account=active_label, reason=reason, remaining_accounts=max(0, len(sessions_queue)-account_pointer-1))
                        return True
                    account_pointer += 1
                return False
            else:
                return active_client is not None

        if not await next_client("start"):
            self.is_broadcasting = False
            return 0, total, "❌ Нет доступных аккаунтов"

        limit = self._get_limit()
        delay = self._get_delay()
        try:
            while index < total and self.is_broadcasting:
                chat_id = chat_ids[index]
                if sent_on_current >= limit:
                    await self._emit(progress_cb, stage="limit", account=active_label, chat_index=index + 1, total=total, remaining_accounts=max(0, len(sessions_queue)-account_pointer-1))
                    if not await next_client("limit"):
                        fail += (total - index)
                        break
                    continue
                try:
                    entity = await active_client.get_entity(chat_id)
                    await self._emit(progress_cb, stage="sending", chat_index=index + 1, total=total, account=active_label, remaining_accounts=max(0, len(sessions_queue)-account_pointer-1), status="Отправка")
                    await active_client.send_message(entity, self.current_text)
                    success += 1
                    sent_on_current += 1
                    await self._emit(progress_cb, stage="sent", chat_index=index + 1, total=total, account=active_label, remaining_accounts=max(0, len(sessions_queue)-account_pointer-1), status="Отправлено")
                    index += 1
                    if index < total and self.is_broadcasting:
                        await asyncio.sleep(delay)
                except FloodWaitError as e:
                    await self._emit(progress_cb, stage="blocked", chat_index=index + 1, total=total, account=active_label, remaining_accounts=max(0, len(sessions_queue)-account_pointer-1), status=f"FloodWait {e.seconds}с")
                    if not await next_client("blocked"):
                        fail += (total - index)
                        break
                except Exception as e:
                    if self._is_account_block_error(e):
                        await self._emit(progress_cb, stage="blocked", chat_index=index + 1, total=total, account=active_label, remaining_accounts=max(0, len(sessions_queue)-account_pointer-1), status="Аккаунт ограничен")
                        if not await next_client("blocked"):
                            fail += (total - index)
                            break
                        continue
                    fail += 1
                    await self._emit(progress_cb, stage="failed", chat_index=index + 1, total=total, account=active_label, remaining_accounts=max(0, len(sessions_queue)-account_pointer-1), status=f"Не отправлено: {e}")
                    index += 1
                    if index < total and self.is_broadcasting:
                        await asyncio.sleep(delay)
        finally:
            if using_temp_clients and active_client:
                try:
                    await active_client.disconnect()
                except Exception:
                    pass
            self.is_broadcasting = False
        return success, fail, "✅ Завершено"
