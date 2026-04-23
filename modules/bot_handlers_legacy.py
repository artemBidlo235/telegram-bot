from __future__ import annotations

import asyncio
from typing import Dict, Any, List, Optional

from telethon import events, Button


class BotHandlers:
    def __init__(self, bot, data_manager, session_manager, chat_manager, broadcaster, auth_handler):
        self.bot = bot
        self.data_manager = data_manager
        self.session_manager = session_manager
        self.chat_manager = chat_manager
        self.broadcaster = broadcaster
        self.auth_handler = auth_handler

        # user_id -> state dict
        self.user_states: Dict[int, Dict[str, Any]] = {}

        self.user_menu = [
            [Button.inline("📊 Статус", b"status"), Button.inline("ℹ️ О боте", b"about")],
        ]
        self.admin_menu = [
            [Button.inline("📋 Запустить рассылку (по чатам)", b"broadcast_chats")],
            [Button.inline("📢 Рассылка пользователям", b"broadcast_users")],
            [Button.inline("🔄 Поменять базу чатов", b"change_chats")],
            [Button.inline("📝 Сменить текст", b"change_text"), Button.inline("⏹️ Остановить", b"stop")],
            [Button.inline("📊 Статус", b"status"), Button.inline("🔑 Логин", b"login")],
            [Button.inline("📁 Управление сессиями", b"sessions"), Button.inline("👥 Пользователи", b"users")],
            [Button.inline("👑 Управление админами", b"admins"), Button.inline("📈 Статистика", b"stats")],
            [Button.inline("◀️ Назад", b"back")],
        ]

        self._register_handlers()

    def _register_handlers(self):
        @self.bot.on(events.NewMessage(pattern="/start"))
        async def start_handler(event):
            await self._handle_start(event)

        @self.bot.on(events.CallbackQuery())
        async def callback_handler(event):
            await self._handle_callback(event)

        @self.bot.on(events.NewMessage())
        async def message_handler(event):
            if event.raw_text and event.raw_text.startswith("/"):
                return
            await self._handle_message(event)

    async def _handle_start(self, event):
        sender = await event.get_sender()
        self.data_manager.add_user(sender.id, getattr(sender, "first_name", "Пользователь"), getattr(sender, "username", None))
        self._clear_state(sender.id)

        text = "🤖 Бот запущен и готов к работе."
        buttons = self.admin_menu if self.data_manager.is_admin(sender.id) else self.user_menu
        await event.respond(text, buttons=buttons)

    async def _handle_callback(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        data = event.data.decode("utf-8", errors="ignore")
        print("Нажата кнопка:", data)

        if not self.data_manager.is_admin(user_id) and data not in {"status", "about", "back"}:
            await event.answer("Недостаточно прав", alert=True)
            return

        if data == "status":
            await self._show_status(event)
        elif data == "about":
            await self._show_about(event)
        elif data == "back":
            await self._show_menu(event)
        elif data == "change_text":
            await self._start_change_text(event)
        elif data == "confirm_change_text":
            await self._confirm_change_text(event)
        elif data == "save_new_text":
            await self._save_new_text(event)
        elif data == "cancel_change_text":
            await self._cancel_change_text(event)
        elif data == "broadcast_users":
            await self._start_broadcast_users(event)
        elif data == "broadcast_chats":
            await self._broadcast_to_chats(event)
        elif data == "change_chats":
            await self._start_change_chats(event)
        elif data == "clear_chats":
            await self._clear_chats(event)
        elif data == "stop":
            self.broadcaster.stop()
            await event.answer("Остановлено")
            await event.edit("⏹️ Рассылка остановлена.", buttons=self.admin_menu)
        elif data == "login":
            await self._start_login(event)
        elif data == "cancel_login":
            await self._cancel_login(event)
        elif data == "sessions":
            await self._show_sessions(event)
        elif data.startswith("use_session:"):
            await self._switch_session(event, data.split(":", 1)[1])
        elif data.startswith("delete_session:"):
            await self._delete_session(event, data.split(":", 1)[1])
        elif data == "users":
            await self._show_users(event)
        elif data == "admins":
            await self._show_admins(event)
        elif data == "add_admin":
            await self._start_add_admin(event)
        elif data.startswith("remove_admin:"):
            await self._remove_admin(event, data.split(":", 1)[1])
        elif data == "stats":
            await self._show_stats(event)
        else:
            await event.answer("Функция пока не настроена", alert=True)

    async def _handle_message(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        self.data_manager.add_user(user_id, getattr(sender, "first_name", "Пользователь"), getattr(sender, "username", None))
        state = self.user_states.get(user_id)
        if not state:
            return

        mode = state.get("mode")
        text = (event.raw_text or "").strip()

        if mode == "awaiting_new_text":
            state["draft_text"] = text
            await self._safe_delete(event)
            preview = await self.bot.send_message(
                event.chat_id,
                f"📝 Новый текст для рассылки:\n\n{text}\n\nПодтвердить изменение?",
                buttons=[
                    [Button.inline("✅ Подтвердить изменение", b"save_new_text")],
                    [Button.inline("❌ Отмена", b"cancel_change_text")],
                ],
            )
            self._track_message(user_id, preview.id)
            await self._delete_prompt_message(user_id)
            state["prompt_message_id"] = preview.id
            return

        if mode == "awaiting_broadcast_users":
            await self._safe_delete(event)
            users = self.data_manager.load_users()
            success = 0
            failed = 0
            for user in users.keys():
                try:
                    await self.bot.send_message(int(user), text)
                    success += 1
                except Exception:
                    failed += 1
            self.data_manager.update_stats(success)
            await self._cleanup_tracked_messages(user_id)
            self._clear_state(user_id)
            await self.bot.send_message(event.chat_id, f"✅ Рассылка завершена.\n\nУспешно: {success}\nОшибок: {failed}", buttons=self.admin_menu)
            return

        if mode == "awaiting_chat_links":
            await self._safe_delete(event)
            if not self.session_manager.user_client:
                await self._cleanup_tracked_messages(user_id)
                self._clear_state(user_id)
                await self.bot.send_message(event.chat_id, "❌ Сначала авторизуйте пользовательскую сессию через кнопку «🔑 Логин».", buttons=self.admin_menu)
                return

            links = [line.strip() for line in text.splitlines() if line.strip()]
            results, duplicates = await self.chat_manager.convert_links_to_ids(self.session_manager.user_client, links)
            ok_ids = self.chat_manager.load_chat_ids()
            known = set(ok_ids)
            added = 0
            failed_items: List[str] = []
            for item in results:
                if item.get("success"):
                    chat_id = int(item["id"])
                    if chat_id not in known:
                        ok_ids.append(chat_id)
                        known.add(chat_id)
                        added += 1
                else:
                    failed_items.append(f"• {item['link']} — {item.get('error', 'ошибка')}")
            self.chat_manager.save_chat_ids(ok_ids)
            await self._cleanup_tracked_messages(user_id)
            self._clear_state(user_id)
            msg = f"✅ Добавлено чатов: {added}\n📦 Всего в базе: {len(ok_ids)}"
            if duplicates:
                msg += f"\n\nПовторы: {len(duplicates)}"
            if failed_items:
                msg += "\n\nНе удалось обработать:\n" + "\n".join(failed_items[:10])
            await self.bot.send_message(event.chat_id, msg, buttons=self.admin_menu)
            return

        if mode == "awaiting_phone":
            await self._safe_delete(event)
            ok, msg = await self.auth_handler.start_login(user_id, text)
            if ok:
                state["mode"] = "awaiting_code"
                state["phone"] = text
                reply = await self.bot.send_message(event.chat_id, "📩 Код отправлен.\nОтправьте код одним сообщением.", buttons=[[Button.inline("❌ Отмена", b"cancel_login")]])
                self._track_message(user_id, reply.id)
                await self._delete_prompt_message(user_id)
                state["prompt_message_id"] = reply.id
            else:
                await self.bot.send_message(event.chat_id, f"❌ {msg}", buttons=self.admin_menu)
                await self._cleanup_tracked_messages(user_id)
                self._clear_state(user_id)
            return

        if mode == "awaiting_code":
            await self._safe_delete(event)
            ok, msg = await self.auth_handler.complete_login(user_id, text)
            await self._cleanup_tracked_messages(user_id)
            self._clear_state(user_id)
            if ok:
                self.broadcaster.set_client(self.session_manager.user_client)
                await self.bot.send_message(event.chat_id, msg, buttons=self.admin_menu)
            else:
                await self.bot.send_message(event.chat_id, f"❌ {msg}", buttons=self.admin_menu)
            return

        if mode == "awaiting_admin_id":
            await self._safe_delete(event)
            try:
                admin_id = int(text)
            except ValueError:
                await self.bot.send_message(event.chat_id, "❌ ID должен быть числом.", buttons=self.admin_menu)
                return
            ok, msg = self.data_manager.add_admin(admin_id, user_id)
            await self._cleanup_tracked_messages(user_id)
            self._clear_state(user_id)
            await self.bot.send_message(event.chat_id, ("✅ " if ok else "❌ ") + msg, buttons=self.admin_menu)
            return

    async def _show_menu(self, event):
        sender = await event.get_sender()
        buttons = self.admin_menu if self.data_manager.is_admin(sender.id) else self.user_menu
        await event.edit("🤖 Главное меню", buttons=buttons)

    async def _show_status(self, event):
        active = self.session_manager.get_current_session_name() or "не выбрана"
        chats = len(self.chat_manager.load_chat_ids())
        text = (
            "📊 Статус бота\n\n"
            f"• Пользовательская сессия: {active}\n"
            f"• Чатов в базе: {chats}\n"
            f"• Идёт рассылка: {'да' if self.broadcaster.is_broadcasting else 'нет'}\n"
            f"• Текущий текст: {self.broadcaster.current_text[:100]}"
        )
        await event.edit(text, buttons=self.admin_menu if self.data_manager.is_admin((await event.get_sender()).id) else self.user_menu)

    async def _show_about(self, event):
        await event.edit("ℹ️ Бот для управления пользовательской сессией и рассылками.", buttons=self.admin_menu if self.data_manager.is_admin((await event.get_sender()).id) else self.user_menu)

    async def _start_change_text(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        await self._cleanup_tracked_messages(user_id)
        self.user_states[user_id] = {"mode": "change_text_confirm", "messages_to_delete": []}
        prompt = await self.bot.send_message(
            event.chat_id,
            f"📝 Текущий текст:\n{self.broadcaster.current_text}\n\nВы точно хотите изменить текст?",
            buttons=[
                [Button.inline("✅ Подтвердить", b"confirm_change_text")],
                [Button.inline("❌ Отмена", b"cancel_change_text")],
            ],
        )
        self._track_message(user_id, prompt.id)
        self.user_states[user_id]["prompt_message_id"] = prompt.id
        await event.answer("Подтвердите изменение")

    async def _confirm_change_text(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {"messages_to_delete": []})
        state["mode"] = "awaiting_new_text"
        prompt_message_id = state.get("prompt_message_id")
        if prompt_message_id:
            try:
                await self.bot.delete_messages(event.chat_id, [prompt_message_id])
            except Exception:
                pass
        prompt = await self.bot.send_message(
            event.chat_id,
            f"📝 Текущий текст:\n{self.broadcaster.current_text}\n\nОтправьте новый текст одним сообщением.",
            buttons=[[Button.inline("❌ Отмена", b"cancel_change_text")]],
        )
        self._track_message(user_id, prompt.id)
        self.user_states[user_id]["prompt_message_id"] = prompt.id
        await event.answer("Отправьте новый текст")

    async def _save_new_text(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.get(user_id, {})
        draft_text = (state.get("draft_text") or "").strip()
        if not draft_text:
            await event.answer("Сначала отправьте новый текст", alert=True)
            return
        self.broadcaster.set_message_text(draft_text)
        await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=event.message_id)
        self._clear_state(user_id)
        await event.edit(f"✅ Текст обновлён.\n\nНовый текст:\n{draft_text}", buttons=self.admin_menu)

    async def _cancel_change_text(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=event.message_id)
        self._clear_state(user_id)
        await event.edit("❌ Изменение текста отменено.", buttons=self.admin_menu)

    async def _start_broadcast_users(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        await self._cleanup_tracked_messages(user_id)
        self.user_states[user_id] = {"mode": "awaiting_broadcast_users", "messages_to_delete": []}
        users_count = len(self.data_manager.load_users())
        prompt = await self.bot.send_message(
            event.chat_id,
            f"📣 Отправьте сообщение для рассылки {users_count} пользователям.",
        )
        self._track_message(user_id, prompt.id)
        self.user_states[user_id]["prompt_message_id"] = prompt.id
        await event.answer("Жду текст рассылки")

    async def _broadcast_to_chats(self, event):
        if not self.session_manager.user_client:
            await event.edit("❌ Нет активной пользовательской сессии. Нажмите «🔑 Логин».", buttons=self.admin_menu)
            return
        chat_ids = self.chat_manager.load_chat_ids()
        if not chat_ids:
            await event.edit("❌ База чатов пуста. Сначала добавьте чаты.", buttons=self.admin_menu)
            return

        await event.edit(f"⏳ Начинаю рассылку по {len(chat_ids)} чатам...", buttons=self.admin_menu)
        success, fail, _ = await self.broadcaster.send_to_chats(chat_ids)
        self.data_manager.update_stats(success)
        await self.bot.send_message(event.chat_id, f"✅ Рассылка завершена.\n\nУспешно: {success}\nОшибок: {fail}", buttons=self.admin_menu)

    async def _start_change_chats(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        await self._cleanup_tracked_messages(user_id)
        self.user_states[user_id] = {"mode": "awaiting_chat_links", "messages_to_delete": []}
        prompt = await self.bot.send_message(
            event.chat_id,
            "🔄 Отправьте ссылки на чаты или каналы, каждый с новой строки.\n\nИспользуйте @username или полные ссылки.",
            buttons=[[Button.inline("🗑 Очистить базу чатов", b"clear_chats")], [Button.inline("◀️ Назад", b"back")]],
        )
        self._track_message(user_id, prompt.id)
        self.user_states[user_id]["prompt_message_id"] = prompt.id
        await event.answer("Жду список чатов")

    async def _clear_chats(self, event):
        self.chat_manager.save_chat_ids([])
        await event.edit("🗑 База чатов очищена.", buttons=self.admin_menu)

    async def _start_login(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        await self._cleanup_tracked_messages(user_id)
        self.user_states[user_id] = {"mode": "awaiting_phone", "messages_to_delete": []}
        prompt = await self.bot.send_message(
            event.chat_id,
            "🔑 Отправьте номер телефона в международном формате.\nПример: +79991234567",
            buttons=[[Button.inline("❌ Отмена", b"cancel_login")]],
        )
        self._track_message(user_id, prompt.id)
        self.user_states[user_id]["prompt_message_id"] = prompt.id
        await event.answer("Жду номер телефона")

    async def _cancel_login(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        try:
            await self.auth_handler.cancel_auth(user_id)
        except Exception:
            pass
        await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=event.message_id)
        self._clear_state(user_id)
        await event.edit("❌ Авторизация отменена.", buttons=self.admin_menu)

    async def _show_sessions(self, event):
        sessions = self.session_manager.get_session_files()
        current = self.session_manager.get_current_session_name()
        if not sessions:
            await event.edit("📁 Сессий пока нет.", buttons=self.admin_menu)
            return
        buttons = []
        for session_name in sessions:
            mark = "✅ " if session_name == current else ""
            buttons.append([
                Button.inline(f"{mark}Использовать {session_name}", f"use_session:{session_name}".encode()),
                Button.inline("🗑", f"delete_session:{session_name}".encode()),
            ])
        buttons.append([Button.inline("◀️ Назад", b"back")])
        await event.edit("📁 Управление сессиями:", buttons=buttons)

    async def _switch_session(self, event, session_name: str):
        ok, msg = await self.session_manager.switch_to_session(session_name)
        if ok:
            self.broadcaster.set_client(self.session_manager.user_client)
        await event.edit(msg, buttons=self.admin_menu)

    async def _delete_session(self, event, session_name: str):
        ok, msg = await self.session_manager.delete_session(session_name)
        await event.edit(msg, buttons=self.admin_menu)

    async def _show_users(self, event):
        users = self.data_manager.load_users()
        await event.edit(f"👥 Пользователей: {len(users)}", buttons=self.admin_menu)

    async def _show_admins(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        admins = self.data_manager.get_admins_list()
        text = ["👑 Администраторы:\n"]
        buttons = []
        for adm in admins:
            role = adm.get("role", "admin")
            username = f"@{adm['username']}" if adm.get("username") else "без username"
            text.append(f"• {adm['id']} — {role} — {username}")
            if role != "owner":
                buttons.append([Button.inline(f"Удалить {adm['id']}", f"remove_admin:{adm['id']}".encode())])
        if self.data_manager.is_owner(user_id):
            buttons.append([Button.inline("➕ Добавить админа", b"add_admin")])
        buttons.append([Button.inline("◀️ Назад", b"back")])
        await event.edit("\n".join(text), buttons=buttons)

    async def _start_add_admin(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        if not self.data_manager.is_owner(user_id):
            await event.answer("Только владелец может добавлять админов", alert=True)
            return
        await self._cleanup_tracked_messages(user_id)
        self.user_states[user_id] = {"mode": "awaiting_admin_id", "messages_to_delete": []}
        prompt = await self.bot.send_message(event.chat_id, "👑 Отправьте ID пользователя, которого нужно сделать админом.")
        self._track_message(user_id, prompt.id)
        self.user_states[user_id]["prompt_message_id"] = prompt.id
        await event.answer("Жду ID")

    async def _remove_admin(self, event, admin_id: str):
        sender = await event.get_sender()
        if not self.data_manager.is_owner(sender.id):
            await event.answer("Только владелец может удалять админов", alert=True)
            return
        try:
            admin_id_int = int(admin_id)
        except ValueError:
            await event.answer("Некорректный ID", alert=True)
            return
        ok, msg = self.data_manager.remove_admin(admin_id_int)
        await event.edit(("✅ " if ok else "❌ ") + msg, buttons=self.admin_menu)

    async def _show_stats(self, event):
        stats = self.data_manager.get_stats()
        users = len(self.data_manager.load_users())
        admins = len(self.data_manager.load_admins())
        chats = len(self.chat_manager.load_chat_ids())
        text = (
            "📈 Статистика\n\n"
            f"• Пользователей: {users}\n"
            f"• Админов: {admins}\n"
            f"• Чатов в базе: {chats}\n"
            f"• Отправлено сообщений: {stats.get('messages_sent', 0)}\n"
            f"• Рассылок: {stats.get('broadcasts', 0)}"
        )
        await event.edit(text, buttons=self.admin_menu)

    def _track_message(self, user_id: int, message_id: int):
        state = self.user_states.setdefault(user_id, {"messages_to_delete": []})
        state.setdefault("messages_to_delete", []).append(message_id)

    async def _delete_prompt_message(self, user_id: int):
        state = self.user_states.get(user_id) or {}
        prompt_message_id = state.get("prompt_message_id")
        if prompt_message_id:
            try:
                await self.bot.delete_messages(user_id, [prompt_message_id])
            except Exception:
                pass
            if prompt_message_id in state.get("messages_to_delete", []):
                state["messages_to_delete"].remove(prompt_message_id)

    async def _cleanup_tracked_messages(self, user_id: int, keep_current: bool = False, current_message_id: Optional[int] = None):
        state = self.user_states.get(user_id) or {}
        ids = list(dict.fromkeys(state.get("messages_to_delete", [])))
        if keep_current and current_message_id:
            ids = [mid for mid in ids if mid != current_message_id]
        if ids:
            try:
                await self.bot.delete_messages(user_id, ids)
            except Exception:
                pass
        state["messages_to_delete"] = []

    async def _safe_delete(self, event):
        try:
            await event.delete()
        except Exception:
            pass

    def _clear_state(self, user_id: int):
        self.user_states.pop(user_id, None)
