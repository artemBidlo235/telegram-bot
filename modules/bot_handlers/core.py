from __future__ import annotations

import asyncio
from typing import Dict, Any, List, Optional

from telethon import events, Button
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest


class BotHandlers:
    def __init__(self, bot, data_manager, session_manager, chat_manager, broadcaster, auth_handler, timing_settings):
        self.bot = bot
        self.data_manager = data_manager
        self.session_manager = session_manager
        self.chat_manager = chat_manager
        self.broadcaster = broadcaster
        self.auth_handler = auth_handler
        self.timing_settings = timing_settings

        self.user_states: Dict[int, Dict[str, Any]] = {}
        self.join_stop_flags: Dict[int, bool] = {}

        self._register_handlers()

    # ==================== MENUS ====================
    def _main_menu_buttons(self, is_admin: bool):
        if is_admin:
            return [
                [Button.inline("⚙️ Настройки софта", b"menu_settings")],
                [Button.inline("📣 Рассылка", b"menu_broadcast")],
                [Button.inline("👑 Admin панель", b"menu_admin")],
            ]
        return [
            [Button.inline("📊 Статус", b"status")],
            [Button.inline("ℹ️ О боте", b"about")],
        ]

    def _settings_menu_buttons(self):
        return [
            [Button.inline("🗂 Настройка базы чатов", b"chat_lists_menu")],
            [Button.inline("📝 Редактирование текста", b"change_text")],
            [Button.inline("👤 Управление аккаунтами", b"menu_accounts")],
            [Button.inline("🚪 Вход в чаты", b"join_chats_menu")],
            [Button.inline("⏱ Настройка тайминга", b"timing_menu")],
            [Button.inline("◀️ Назад", b"back")],
        ]

    def _accounts_menu_buttons(self):
        return [
            [Button.inline("🔑 Авторизация", b"login")],
            [Button.inline("📁 Управление сессиями", b"sessions")],
            [Button.inline("◀️ Назад", b"menu_settings")],
        ]

    def _broadcast_menu_buttons(self):
        return [
            [Button.inline("▶️ Запуск", b"broadcast_chats")],
            [Button.inline("⏹️ Стоп", b"stop")],
            [Button.inline("📊 Статус", b"status")],
            [Button.inline("◀️ Назад", b"back")],
        ]

    def _admin_panel_buttons(self):
        return [
            [Button.inline("👑 Управление админами", b"admins")],
            [Button.inline("👥 Пользователи", b"users")],
            [Button.inline("📈 Статистика бота", b"stats")],
            [Button.inline("📢 Рассылка пользователям", b"broadcast_users")],
            [Button.inline("◀️ Назад", b"back")],
        ]

    def _chat_lists_menu_buttons(self):
        return [
            [Button.inline("✅ Выбрать", b"chat_lists_select")],
            [Button.inline("✏️ Редактировать", b"chat_lists_edit")],
            [Button.inline("➕ Создать", b"chat_lists_create")],
            [Button.inline("◀️ Назад", b"menu_settings")],
        ]

    # ==================== REGISTRATION ====================
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

    # ==================== GENERAL ====================
    async def _handle_start(self, event):
        sender = await event.get_sender()
        self.data_manager.add_user(sender.id, getattr(sender, "first_name", "Пользователь"), getattr(sender, "username", None))
        self._clear_state(sender.id)

        is_admin = self.data_manager.is_admin(sender.id)
        text = "🤖 Бот запущен и готов к работе. Выберите раздел."
        await event.respond(text, buttons=self._main_menu_buttons(is_admin))

    async def _handle_callback(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        data = event.data.decode("utf-8", errors="ignore")
        print("Нажата кнопка:", data)

        public_callbacks = {"status", "about", "back"}
        owner_only_callbacks = {"menu_admin", "admins", "add_admin", "users", "stats", "broadcast_users"}

        if not self.data_manager.is_admin(user_id) and data not in public_callbacks:
            await event.answer("Недостаточно прав", alert=True)
            return

        if (data in owner_only_callbacks or data.startswith("remove_admin:")) and not self.data_manager.is_owner(user_id):
            await event.answer("Этот раздел доступен только владельцу бота", alert=True)
            return

        if data == "back":
            await self._show_menu(event)
        elif data == "menu_settings":
            await self._show_settings_menu(event)
        elif data == "menu_accounts":
            await self._show_accounts_menu(event)
        elif data == "menu_broadcast":
            await self._show_broadcast_menu(event)
        elif data == "menu_admin":
            await self._show_admin_panel(event)
        elif data == "status":
            await self._show_status(event)
        elif data == "about":
            await self._show_about(event)
        elif data == "change_text":
            await self._start_change_text(event)
        elif data == "confirm_change_text":
            await self._confirm_change_text(event)
        elif data == "save_new_text":
            await self._save_new_text(event)
        elif data == "cancel_change_text":
            await self._cancel_change_text(event)
        elif data == "broadcast_chats":
            await self._broadcast_to_chats(event)
        elif data == "stop":
            self.broadcaster.stop()
            await event.answer("Остановлено")
            await event.edit("⏹️ Рассылка остановлена.", buttons=self._broadcast_menu_buttons())
        elif data == "broadcast_users":
            await self._start_broadcast_users(event)
        elif data == "login":
            await self._start_login(event)
        elif data == "cancel_login":
            await self._cancel_login(event)
        elif data == "cancel_chat_lists":
            await self._cancel_chat_lists(event)
        elif data == "chat_lists_offer_create":
            await self._start_create_chat_list(event)
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
        elif data == "chat_lists_menu":
            await self._show_chat_lists_menu(event)
        elif data == "chat_lists_select":
            await self._show_selectable_chat_lists(event)
        elif data == "chat_lists_edit":
            await self._show_editable_chat_lists(event)
        elif data == "chat_lists_create":
            await self._start_create_chat_list(event)
        elif data.startswith("chat_choose:"):
            await self._show_choose_list_actions(event, data.split(":", 1)[1])
        elif data.startswith("chat_confirm_select:"):
            await self._confirm_select_chat_list(event, data.split(":", 1)[1])
        elif data.startswith("chat_view_menu:"):
            _, name, back_action = data.split(":", 2)
            await self._show_chat_list_view_menu(event, name, back_action)
        elif data.startswith("chat_view_ids:"):
            _, name, back_action = data.split(":", 2)
            await self._view_chat_list(event, name, back_action, view_mode="ids")
        elif data.startswith("chat_view_links:"):
            _, name, back_action = data.split(":", 2)
            await self._view_chat_list(event, name, back_action, view_mode="links")
        elif data.startswith("chat_edit_item:"):
            await self._show_edit_list_actions(event, data.split(":", 1)[1])
        elif data.startswith("chat_add_links:"):
            await self._start_add_links_to_list(event, data.split(":", 1)[1])
        elif data.startswith("chat_replace_links:"):
            await self._start_replace_links_in_list(event, data.split(":", 1)[1])
        elif data == "chat_lists_back_select":
            await self._show_selectable_chat_lists(event)
        elif data == "chat_lists_back_edit":
            await self._show_editable_chat_lists(event)
        elif data == "timing_menu":
            await self._show_timing_menu(event)
        elif data == "timing_broadcast":
            await self._start_set_timing(event, "timing_broadcast_delay")
        elif data == "timing_join":
            await self._start_set_timing(event, "timing_join_delay")
        elif data == "timing_limit":
            await self._start_set_timing(event, "timing_account_limit")
        elif data == "timing_back":
            await self._show_timing_menu(event)
        elif data == "join_chats_menu":
            await self._show_join_chats_menu(event)
        elif data == "join_chats_choose_accounts":
            await self._show_join_accounts_selector(event)
        elif data == "join_chats_choose_lists":
            await self._show_join_chat_lists_selector(event)
        elif data.startswith("join_toggle:"):
            await self._toggle_join_account(event, int(data.split(":", 1)[1]))
        elif data == "join_accounts_done":
            await self._show_join_chats_menu(event)
        elif data.startswith("join_list_pick:"):
            await self._pick_join_chat_list(event, data.split(":", 1)[1])
        elif data == "join_chatlist_confirm":
            await self._confirm_join_chat_list(event)
        elif data == "join_continue":
            await self._show_join_launch_confirmation(event)
        elif data == "join_launch":
            await self._launch_join_process(event)
        elif data == "join_stop":
            await self._stop_join_process(event)
        elif data == "join_cancel":
            await self._cancel_join_chats(event)
        elif data == "show_manual_chats":
            await self._show_manual_chats(event)
        elif data == "show_request_chats":
            await self._show_request_chats(event)
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
            prompt_id = state.get("prompt_message_id")
            state["prompt_message_id"] = await self._edit_or_send(
                event.chat_id,
                prompt_id,
                f"📝 Новый текст для рассылки:\n\n{text}\n\nПодтвердить изменение?",
                buttons=[
                    [Button.inline("✅ Подтвердить изменение", b"save_new_text")],
                    [Button.inline("❌ Отмена", b"cancel_change_text")],
                ],
            )
            state["prompt_chat_id"] = event.chat_id
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
            prompt_id = state.get("prompt_message_id")
            await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=prompt_id, chat_id=event.chat_id)
            self._clear_state(user_id)
            await self._edit_or_send(event.chat_id, prompt_id, f"✅ Рассылка завершена.\n\nУспешно: {success}\nОшибок: {failed}", buttons=self._admin_panel_buttons())
            return

        if mode == "awaiting_phone":
            await self._safe_delete(event)
            state["mode"] = "starting_login"
            prompt_message_id = state.get("prompt_message_id")
            waiting_message_id = await self._edit_or_send(
                event.chat_id,
                prompt_message_id,
                "⏳ Ожидайте, пока система начнёт вход в аккаунт...",
                buttons=[[Button.inline("❌ Отмена", b"cancel_login")]],
            )
            state["prompt_message_id"] = waiting_message_id
            state["prompt_chat_id"] = event.chat_id

            result = await self.auth_handler.start_login(user_id, text)
            ok = bool(result[0]) if isinstance(result, tuple) and len(result) >= 1 else False
            msg = result[1] if isinstance(result, tuple) and len(result) >= 2 else "Не удалось начать авторизацию"

            if ok:
                state["mode"] = "awaiting_code"
                state["phone"] = text
                state["prompt_message_id"] = await self._edit_or_send(
                    event.chat_id,
                    waiting_message_id,
                    "📩 Пришлите код с аккаунта.",
                    buttons=[[Button.inline("❌ Отмена", b"cancel_login")]],
                )
            else:
                await self._edit_or_send(event.chat_id, waiting_message_id, f"❌ {msg}", buttons=self._accounts_menu_buttons())
                await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=waiting_message_id, chat_id=event.chat_id)
                self._clear_state(user_id)
            return

        if mode == "starting_login":
            await self._safe_delete(event)
            return

        if mode == "awaiting_code":
            await self._safe_delete(event)
            result = await self.auth_handler.complete_login(user_id, text)
            ok = bool(result[0]) if isinstance(result, tuple) and len(result) >= 1 else False
            msg = result[1] if isinstance(result, tuple) and len(result) >= 2 else "Не удалось завершить авторизацию"
            prompt_id = state.get("prompt_message_id")
            await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=prompt_id, chat_id=event.chat_id)
            self._clear_state(user_id)
            if ok:
                self.broadcaster.set_client(self.session_manager.user_client)
                await self._edit_or_send(event.chat_id, prompt_id, msg, buttons=self._accounts_menu_buttons())
            else:
                await self._edit_or_send(event.chat_id, prompt_id, f"❌ {msg}", buttons=self._accounts_menu_buttons())
            return

        if mode in {"timing_broadcast_delay", "timing_join_delay", "timing_account_limit"}:
            await self._safe_delete(event)
            prompt_id = state.get("prompt_message_id")
            try:
                value = int(text)
                if value < 0:
                    raise ValueError
            except ValueError:
                state["prompt_message_id"] = await self._edit_or_send(
                    event.chat_id,
                    prompt_id,
                    "❌ Введите целое число 0 или больше." if mode != "timing_account_limit" else "❌ Введите целое число 1 или больше.",
                    buttons=[[Button.inline("❌ Отмена", b"timing_back")]],
                )
                return
            if mode == "timing_account_limit" and value < 1:
                state["prompt_message_id"] = await self._edit_or_send(
                    event.chat_id, prompt_id, "❌ Введите целое число 1 или больше.", buttons=[[Button.inline("❌ Отмена", b"timing_back")]]
                )
                return
            if mode == "timing_broadcast_delay":
                self.timing_settings.set_broadcast_delay(value)
                msg = f"✅ Тайминг рассылки сохранён: {value} сек."
            elif mode == "timing_join_delay":
                self.timing_settings.set_join_delay(value)
                msg = f"✅ Тайминг вступления сохранён: {value} сек."
            else:
                self.timing_settings.set_account_message_limit(value)
                msg = f"✅ Лимит сообщений на аккаунт сохранён: {value}"
            self._clear_state(user_id)
            await self._edit_or_send(event.chat_id, prompt_id, msg, buttons=self._timing_menu_buttons())
            return

        if mode == "awaiting_admin_id":
            await self._safe_delete(event)
            prompt_id = state.get("prompt_message_id")
            try:
                admin_id = int(text)
            except ValueError:
                state["prompt_message_id"] = await self._edit_or_send(
                    event.chat_id,
                    prompt_id,
                    "❌ ID должен быть числом.\n\nОтправьте ID пользователя, которого нужно сделать админом.",
                    buttons=[[Button.inline("❌ Отмена", b"menu_admin")]],
                )
                return
            ok, msg = self.data_manager.add_admin(admin_id, user_id)
            await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=prompt_id, chat_id=event.chat_id)
            self._clear_state(user_id)
            await self._edit_or_send(event.chat_id, prompt_id, ("✅ " if ok else "❌ ") + msg, buttons=self._admin_panel_buttons())
            return

        if mode == "awaiting_chat_list_name":
            await self._safe_delete(event)
            prompt_id = state.get("prompt_message_id")
            if not text:
                state["prompt_message_id"] = await self._edit_or_send(
                    event.chat_id,
                    prompt_id,
                    "❌ Название списка не может быть пустым.\n\nОтправьте название нового списка чатов одним сообщением.",
                    buttons=[[Button.inline("❌ Отмена", b"cancel_chat_lists")]],
                )
                return
            if self.chat_manager.get_chat_list(text):
                state["prompt_message_id"] = await self._edit_or_send(
                    event.chat_id,
                    prompt_id,
                    "❌ Список с таким названием уже существует.\n\nОтправьте другое название.",
                    buttons=[[Button.inline("❌ Отмена", b"cancel_chat_lists")]],
                )
                return
            state["pending_list_name"] = text
            state["mode"] = "awaiting_chat_list_create_links"
            state["prompt_message_id"] = await self._edit_or_send(
                event.chat_id,
                prompt_id,
                f"🆕 Название списка: {text}\n\nТеперь отправьте ссылки на чаты или каналы одним большим сообщением. Можно через пробелы, переносы строк или запятые.",
                buttons=[[Button.inline("❌ Отмена", b"cancel_chat_lists")]],
            )
            state["prompt_chat_id"] = event.chat_id
            return

        if mode in {"awaiting_chat_list_create_links", "awaiting_chat_list_add_links", "awaiting_chat_list_replace_links"}:
            await self._safe_delete(event)
            await self._process_chat_links_message(event, state, text)
            return

    # ==================== MENU VIEWS ====================
    async def _show_menu(self, event):
        sender = await event.get_sender()
        is_admin = self.data_manager.is_admin(sender.id)
        await event.edit("🤖 Главное меню", buttons=self._main_menu_buttons(is_admin))

    async def _show_settings_menu(self, event):
        await event.edit("⚙️ Настройки софта", buttons=self._settings_menu_buttons())

    async def _show_accounts_menu(self, event):
        await event.edit("👤 Управление аккаунтами", buttons=self._accounts_menu_buttons())

    async def _show_broadcast_menu(self, event):
        await event.edit("📣 Раздел рассылки", buttons=self._broadcast_menu_buttons())

    async def _show_admin_panel(self, event):
        await event.edit("👑 Admin панель", buttons=self._admin_panel_buttons())

    async def _show_status(self, event):
        active = self.session_manager.get_current_session_name() or "не выбрана"
        chats = len(self.chat_manager.load_chat_ids())
        active_list_name = self.chat_manager.get_active_list_name() or "не выбран"
        text = (
            "📊 Статус бота\n\n"
            f"• Пользовательская сессия: {active}\n"
            f"• Активный список чатов: {active_list_name}\n"
            f"• Чатов в активной базе: {chats}\n"
            f"• Идёт рассылка: {'да' if self.broadcaster.is_broadcasting else 'нет'}\n"
            f"• Текущий текст: {self.broadcaster.current_text[:100]}"
        )
        sender = await event.get_sender()
        buttons = self._broadcast_menu_buttons() if self.data_manager.is_admin(sender.id) else self._main_menu_buttons(False)
        await event.edit(text, buttons=buttons)

    async def _show_about(self, event):
        await event.edit("ℹ️ Бот для управления пользовательской сессией и рассылками.", buttons=self._main_menu_buttons(False))

    def _timing_menu_buttons(self):
        settings = self.timing_settings.load()
        return [
            [Button.inline(f"💬 Спам чаты: {settings.get('broadcast_delay', 5)}с", b"timing_broadcast")],
            [Button.inline(f"🚪 Чаты вступление: {settings.get('join_delay', 1)}с", b"timing_join")],
            [Button.inline(f"🔢 Лимит сообщений: {settings.get('account_message_limit', 50)}", b"timing_limit")],
            [Button.inline("◀️ Назад", b"menu_settings")],
        ]

    async def _show_timing_menu(self, event):
        settings = self.timing_settings.load()
        text = (
            "⏱ Настройка тайминга\n\n"
            f"• Пауза между сообщениями: {settings.get('broadcast_delay', 5)} сек.\n"
            f"• Пауза между вступлениями: {settings.get('join_delay', 1)} сек.\n"
            f"• Лимит сообщений на аккаунт: {settings.get('account_message_limit', 50)}"
        )
        await event.edit(text, buttons=self._timing_menu_buttons())

    async def _start_set_timing(self, event, mode: str):
        sender = await event.get_sender()
        user_id = sender.id
        settings = self.timing_settings.load()
        messages = {
            "timing_broadcast_delay": f"💬 Отправьте паузу между сообщениями в чатах в секундах.\nТекущее значение: {settings.get('broadcast_delay', 5)}",
            "timing_join_delay": f"🚪 Отправьте паузу между вступлениями в чаты в секундах.\nТекущее значение: {settings.get('join_delay', 1)}",
            "timing_account_limit": f"🔢 Отправьте лимит сообщений на один аккаунт.\nТекущее значение: {settings.get('account_message_limit', 50)}",
        }
        self.user_states[user_id] = {
            "mode": mode,
            "messages_to_delete": [],
            "prompt_chat_id": event.chat_id,
            "prompt_message_id": event.message_id,
        }
        await event.edit(messages[mode], buttons=[[Button.inline("❌ Отмена", b"timing_back")]])


    # ==================== TEXT EDIT ====================
    async def _start_change_text(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        self.user_states[user_id] = {
            "mode": "change_text_confirm",
            "messages_to_delete": [],
            "prompt_chat_id": event.chat_id,
            "prompt_message_id": event.message_id,
        }
        await event.edit(
            f"❗ Вы уверены, что хотите заменить текст под рассылку?\n\n📝 Предыдущий текст:\n{self.broadcaster.current_text}",
            buttons=[[Button.inline("▶️ Продолжить", b"confirm_change_text"), Button.inline("❌ Отмена", b"cancel_change_text")]],
        )

    async def _confirm_change_text(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {"messages_to_delete": []})
        state["mode"] = "awaiting_new_text"
        state["prompt_chat_id"] = event.chat_id
        state["prompt_message_id"] = event.message_id
        await event.edit(
            f"📝 Текущий текст:\n{self.broadcaster.current_text}\n\nОтправьте новый текст одним сообщением.",
            buttons=[[Button.inline("❌ Отмена", b"cancel_change_text")]],
        )

    async def _save_new_text(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.get(user_id, {})
        draft_text = (state.get("draft_text") or "").strip()
        if not draft_text:
            await event.answer("Сначала отправьте новый текст", alert=True)
            return
        self.broadcaster.set_message_text(draft_text)
        await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=event.message_id, chat_id=event.chat_id)
        self._clear_state(user_id)
        await event.edit(f"✅ Текст обновлён.\n\nНовый текст:\n{draft_text}", buttons=self._settings_menu_buttons())

    async def _cancel_change_text(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=event.message_id, chat_id=event.chat_id)
        self._clear_state(user_id)
        await event.edit("❌ Действие отменено.", buttons=self._settings_menu_buttons())

    # ==================== BROADCAST ====================
    async def _start_broadcast_users(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        users_count = len(self.data_manager.load_users())
        self.user_states[user_id] = {
            "mode": "awaiting_broadcast_users",
            "messages_to_delete": [],
            "prompt_chat_id": event.chat_id,
            "prompt_message_id": event.message_id,
        }
        await event.edit(
            f"📣 Отправьте сообщение для рассылки {users_count} пользователям.",
            buttons=[[Button.inline("❌ Отмена", b"menu_admin")]],
        )

    async def _broadcast_to_chats(self, event):
        if not self.session_manager.user_client:
            await event.edit("❌ Нет активной пользовательской сессии. Откройте «Управление аккаунтами → Авторизация».", buttons=self._broadcast_menu_buttons())
            return
        chat_ids = self.chat_manager.load_chat_ids()
        if not chat_ids:
            await event.edit("❌ Активная база чатов пуста. Сначала выберите или создайте список чатов.", buttons=self._broadcast_menu_buttons())
            return
        await event.edit(f"⏳ Начинаю рассылку по {len(chat_ids)} чатам...", buttons=self._broadcast_menu_buttons())
        success, fail, _ = await self.broadcaster.send_to_chats(chat_ids)
        self.data_manager.update_stats(success)
        await self.bot.send_message(event.chat_id, f"✅ Рассылка завершена.\n\nУспешно: {success}\nОшибок: {fail}", buttons=self._broadcast_menu_buttons())

    # ==================== CHAT LISTS ====================
    async def _show_chat_lists_menu(self, event):
        active = self.chat_manager.get_active_list_name() or "не выбран"
        total = len(self.chat_manager.get_chat_lists_names())
        text = (
            "🗂 Настройка базы чатов\n\n"
            f"• Сохранённых списков: {total}\n"
            f"• Активный список: {active}"
        )
        await event.edit(text, buttons=self._chat_lists_menu_buttons())

    async def _show_no_chat_bases(self, event):
        await event.edit(
            "📭 У вас нет ни одной базы чатов. Сначала создайте её.",
            buttons=[
                [Button.inline("➕ Создать базу", b"chat_lists_offer_create")],
                [Button.inline("❌ Отмена", b"cancel_chat_lists")],
            ],
        )

    async def _cancel_chat_lists(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=event.message_id, chat_id=event.chat_id)
        self._clear_state(user_id)
        await self._show_chat_lists_menu(event)

    async def _show_selectable_chat_lists(self, event):
        names = self.chat_manager.get_chat_lists_names()
        if not names:
            await self._show_no_chat_bases(event)
            return
        buttons = [[Button.inline(name, f"chat_choose:{name}".encode())] for name in names]
        buttons.append([Button.inline("◀️ Назад", b"chat_lists_menu")])
        await event.edit("✅ Выберите список чатов:", buttons=buttons)

    async def _show_editable_chat_lists(self, event):
        names = self.chat_manager.get_chat_lists_names()
        if not names:
            await self._show_no_chat_bases(event)
            return
        buttons = [[Button.inline(name, f"chat_edit_item:{name}".encode())] for name in names]
        buttons.append([Button.inline("◀️ Назад", b"chat_lists_menu")])
        await event.edit("✏️ Выберите список для редактирования:", buttons=buttons)

    async def _start_create_chat_list(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        self.user_states[user_id] = {
            "mode": "awaiting_chat_list_name",
            "messages_to_delete": [],
            "prompt_chat_id": event.chat_id,
            "prompt_message_id": event.message_id,
        }
        await event.edit(
            "➕ Отправьте название нового списка чатов одним сообщением.",
            buttons=[[Button.inline("❌ Отмена", b"cancel_chat_lists")]],
        )

    async def _show_choose_list_actions(self, event, name: str):
        item = self.chat_manager.get_chat_list(name)
        if not item:
            await event.answer("Список не найден", alert=True)
            await self._show_selectable_chat_lists(event)
            return
        text = (
            f"📋 Список: {name}\n\n"
            f"• Чатов: {len(item.get('chat_ids', []))}\n"
            f"• Ссылок: {len(item.get('links', []))}\n\n"
            "Выберите действие:"
        )
        await event.edit(
            text,
            buttons=[
                [Button.inline("✅ Подтвердить", f"chat_confirm_select:{name}".encode())],
                [Button.inline("👁 Просмотреть список", f"chat_view_menu:{name}:chat_lists_back_select".encode())],
                [Button.inline("◀️ Назад", b"chat_lists_back_select")],
            ],
        )

    async def _confirm_select_chat_list(self, event, name: str):
        item = self.chat_manager.get_chat_list(name) or {"chat_ids": [], "links": []}
        chat_ids = item.get("chat_ids", [])
        links = item.get("links", [])

        if not chat_ids and links and self.session_manager.user_client:
            results, _ = await self.chat_manager.convert_links_to_ids(self.session_manager.user_client, links)
            resolved_ids = [int(entry["id"]) for entry in results if entry.get("success")]
            if resolved_ids:
                self.chat_manager.replace_chat_list(name, links, resolved_ids)
                item = self.chat_manager.get_chat_list(name) or item
                chat_ids = item.get("chat_ids", [])

        if not chat_ids:
            if links and not self.session_manager.user_client:
                await event.edit(
                    f"❌ Для выбора списка «{name}» нужна авторизация аккаунта, потому что ID чатов ещё не сохранены.\n\nСначала откройте «Управление аккаунтами → Авторизация», затем повторите выбор.",
                    buttons=[[Button.inline("◀️ Назад", b"chat_lists_back_select")]],
                )
                return
            await event.edit(
                f"❌ В списке «{name}» пока нет пригодных чатов для выбора.",
                buttons=[[Button.inline("◀️ Назад", b"chat_lists_back_select")]],
            )
            return

        ok, msg = self.chat_manager.set_active_chat_list(name)
        prefix = "✅" if ok else "❌"
        await event.edit(
            f"{prefix} {msg}.\n\nАктивный список: {name}\nЧатов в нём: {len(chat_ids)}",
            buttons=self._chat_lists_menu_buttons(),
        )

    async def _show_chat_list_view_menu(self, event, name: str, back_action: str):
        await event.edit(
            f"👁 Просмотр списка: {name}\n\nКак показать список?",
            buttons=[
                [Button.inline("🆔 В формате ID", f"chat_view_ids:{name}:{back_action}".encode())],
                [Button.inline("🔗 В формате ссылок", f"chat_view_links:{name}:{back_action}".encode())],
                [Button.inline("◀️ Назад", back_action.encode())],
            ],
        )

    async def _view_chat_list(self, event, name: str, back_action: str, view_mode: str):
        item = self.chat_manager.get_chat_list(name)
        if not item:
            await event.answer("Список не найден", alert=True)
            return
        entries = item.get("chat_ids", []) if view_mode == "ids" else item.get("links", [])
        title = "ID" if view_mode == "ids" else "ссылки"
        body = "\n".join(str(x) for x in entries[:80]) if entries else "Список пуст"
        if len(entries) > 80:
            body += f"\n\n... и ещё {len(entries) - 80}"
        await event.edit(
            f"👁 {name} — просмотр через {title}:\n\n{body}",
            buttons=[[Button.inline("◀️ Назад", f"chat_view_menu:{name}:{back_action}".encode())]],
        )

    async def _show_edit_list_actions(self, event, name: str):
        item = self.chat_manager.get_chat_list(name)
        if not item:
            await event.answer("Список не найден", alert=True)
            await self._show_editable_chat_lists(event)
            return
        await event.edit(
            f"✏️ Редактирование списка: {name}\n\n• Чатов: {len(item.get('chat_ids', []))}\n• Ссылок: {len(item.get('links', []))}",
            buttons=[
                [Button.inline("👁 Просмотреть список", f"chat_view_menu:{name}:chat_lists_back_edit".encode())],
                [Button.inline("➕ Добавить ссылки", f"chat_add_links:{name}".encode())],
                [Button.inline("♻️ Перезаписать", f"chat_replace_links:{name}".encode())],
                [Button.inline("◀️ Назад", b"chat_lists_back_edit")],
            ],
        )

    async def _start_add_links_to_list(self, event, name: str):
        sender = await event.get_sender()
        user_id = sender.id
        self.user_states[user_id] = {
            "mode": "awaiting_chat_list_add_links",
            "messages_to_delete": [],
            "target_list_name": name,
            "prompt_chat_id": event.chat_id,
            "prompt_message_id": event.message_id,
        }
        await event.edit(
            f"➕ Отправьте новые ссылки для списка «{name}» одним большим сообщением. Можно через пробелы, переносы строк или запятые.",
            buttons=[[Button.inline("❌ Отмена", b"cancel_chat_lists")]],
        )

    async def _start_replace_links_in_list(self, event, name: str):
        sender = await event.get_sender()
        user_id = sender.id
        self.user_states[user_id] = {
            "mode": "awaiting_chat_list_replace_links",
            "messages_to_delete": [],
            "target_list_name": name,
            "prompt_chat_id": event.chat_id,
            "prompt_message_id": event.message_id,
        }
        await event.edit(
            f"♻️ Отправьте новый список ссылок для «{name}» одним большим сообщением. Старое содержимое будет полностью заменено.",
            buttons=[[Button.inline("❌ Отмена", b"cancel_chat_lists")]],
        )

    async def _process_chat_links_message(self, event, state: Dict[str, Any], text: str):
        sender = await event.get_sender()
        user_id = sender.id

        links = self.chat_manager.parse_links_input(text)
        prompt_id = state.get("prompt_message_id")
        if not links:
            state["prompt_message_id"] = await self._edit_or_send(
                event.chat_id,
                prompt_id,
                "❌ Список ссылок пуст.\n\nОтправьте ссылки одним большим сообщением или несколькими строками.",
                buttons=[[Button.inline("❌ Отмена", b"cancel_chat_lists")]],
            )
            return

        ok_ids: List[int] = []
        ok_links: List[str] = []
        failed_items: List[str] = []
        duplicates: List[str] = []

        if self.session_manager.user_client:
            results, duplicates = await self.chat_manager.convert_links_to_ids(self.session_manager.user_client, links)
            for item in results:
                if item.get("success"):
                    ok_ids.append(int(item["id"]))
                    ok_links.append(item["link"])
                else:
                    failed_items.append(f"• {item['link']} — {item.get('error', 'ошибка')}")
        else:
            ok_links = list(dict.fromkeys(links))
            duplicates = [link for i, link in enumerate(links) if link in links[:i]]

        mode = state.get("mode")
        name = state.get("pending_list_name") or state.get("target_list_name")

        if mode == "awaiting_chat_list_create_links":
            ok, msg = self.chat_manager.create_chat_list(name, ok_links, ok_ids)
            buttons = self._chat_lists_menu_buttons()
        elif mode == "awaiting_chat_list_add_links":
            ok, msg, added = self.chat_manager.append_to_chat_list(name, ok_links, ok_ids)
            msg = f"{msg}. Добавлено новых чатов: {added}" if ok else msg
            buttons = [[Button.inline("◀️ К спискам", b"chat_lists_menu")]]
        else:
            ok, msg = self.chat_manager.replace_chat_list(name, ok_links, ok_ids)
            buttons = [[Button.inline("◀️ К спискам", b"chat_lists_menu")]]

        prompt_id = state.get("prompt_message_id")
        await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=prompt_id, chat_id=event.chat_id)
        self._clear_state(user_id)

        status = "✅" if ok else "❌"
        summary = [f"{status} {msg}", f"\nСписок: {name}", f"Успешно обработано: {len(ok_ids)}"]
        if duplicates:
            summary.append(f"Повторы в сообщении: {len(duplicates)}")
        if failed_items:
            summary.append("\nНе удалось обработать:\n" + "\n".join(failed_items[:10]))
        await self._edit_or_send(event.chat_id, prompt_id, "\n".join(summary), buttons=buttons)

    # ==================== JOIN CHATS ====================
    async def _show_join_chats_menu(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {})

        selected_list = state.get("join_selected_chat_list") or self.chat_manager.get_active_list_name()
        selected_sessions = state.get("join_selected_sessions", [])
        available_sessions = self.session_manager.get_session_files()
        chat_list = self.chat_manager.get_chat_list(selected_list) if selected_list else None
        links_count = len((chat_list or {}).get("links", []))

        state["mode"] = "join_menu"
        state["prompt_chat_id"] = event.chat_id
        state["prompt_message_id"] = event.message_id

        if selected_sessions:
            accounts_text = f"{len(selected_sessions)} шт."
        elif available_sessions:
            accounts_text = "не выбраны"
        else:
            accounts_text = "нет авторизованных"

        text = (
            "🚪 Вход в чаты\n\n"
            f"Выбранная база: {selected_list or 'не выбрана'}\n"
            f"Чатов в базе: {links_count}\n"
            f"Выбранные аккаунты: {accounts_text}\n"
            f"Всего авторизованных аккаунтов: {len(available_sessions)}\n\n"
            "Сначала выберите аккаунты и базу чатов, затем нажмите «Продолжить»."
        )
        await event.edit(
            text,
            buttons=[
                [Button.inline("☑️ Выбрать аккаунты", b"join_chats_choose_accounts")],
                [Button.inline("🗂 Выбрать чаты", b"join_chats_choose_lists")],
                [Button.inline("▶️ Продолжить", b"join_continue")],
                [Button.inline("❌ Отмена", b"menu_settings")],
            ],
        )

    async def _show_join_accounts_selector(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        sessions = self.session_manager.get_session_files()
        state = self.user_states.setdefault(user_id, {})
        state["prompt_chat_id"] = event.chat_id
        state["prompt_message_id"] = event.message_id

        if not sessions:
            await event.edit(
                "🚪 Нет авторизованных аккаунтов. Сначала авторизуйте хотя бы один аккаунт.",
                buttons=[
                    [Button.inline("🔑 Авторизация", b"login")],
                    [Button.inline("◀️ Назад", b"join_chats_menu")],
                ],
            )
            return

        selected = set(state.get("join_selected_sessions", []))
        state["join_available_sessions"] = sessions
        state["join_selected_sessions"] = list(selected)
        state["mode"] = "join_select_accounts"

        buttons = []
        for idx, session_name in enumerate(sessions):
            mark = "✅" if session_name in selected else "⬜"
            title = self._short_session_label(session_name)
            buttons.append([Button.inline(f"{mark} {title}", f"join_toggle:{idx}".encode())])
        buttons.append([Button.inline("✅ Подтвердить", b"join_accounts_done")])
        buttons.append([Button.inline("❌ Отмена", b"join_chats_menu")])

        await event.edit(
            f"☑️ Выбор аккаунтов\n\nВыбрано аккаунтов: {len(selected)}",
            buttons=buttons,
        )

    async def _toggle_join_account(self, event, index: int):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {})
        sessions = state.get("join_available_sessions") or self.session_manager.get_session_files()
        if index < 0 or index >= len(sessions):
            await event.answer("Аккаунт не найден", alert=True)
            return
        selected = set(state.get("join_selected_sessions", []))
        session_name = sessions[index]
        if session_name in selected:
            selected.remove(session_name)
        else:
            selected.add(session_name)
        state["join_available_sessions"] = sessions
        state["join_selected_sessions"] = list(selected)
        await self._show_join_accounts_selector(event)

    async def _show_join_chat_lists_selector(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {})
        names = self.chat_manager.get_chat_lists_names()
        state["prompt_chat_id"] = event.chat_id
        state["prompt_message_id"] = event.message_id

        if not names:
            await event.edit(
                "🗂 У вас пока нет ни одной базы чатов. Сначала создайте её в разделе «Настройка базы чатов».",
                buttons=[
                    [Button.inline("➕ Создать базу", b"chat_lists_create")],
                    [Button.inline("◀️ Назад", b"join_chats_menu")],
                ],
            )
            return

        selected_name = state.get("join_selected_chat_list") or self.chat_manager.get_active_list_name()
        candidate_name = state.get("join_selected_chat_list_candidate", selected_name)
        buttons = []
        for name in names:
            mark = "✅" if name == candidate_name else "⬜"
            buttons.append([Button.inline(f"{mark} {name}", f"join_list_pick:{name}".encode())])
        buttons.append([Button.inline("✅ Подтвердить", b"join_chatlist_confirm")])
        buttons.append([Button.inline("❌ Отмена", b"join_chats_menu")])

        await event.edit(
            f"🗂 Выбор базы чатов\n\nВыбрана: {candidate_name or 'не выбрана'}",
            buttons=buttons,
        )

    async def _pick_join_chat_list(self, event, name: str):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {})
        state["join_selected_chat_list_candidate"] = name
        await self._show_join_chat_lists_selector(event)

    async def _confirm_join_chat_list(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {})
        name = state.get("join_selected_chat_list_candidate") or state.get("join_selected_chat_list") or self.chat_manager.get_active_list_name()
        if not name:
            await event.answer("Сначала выберите базу", alert=True)
            return
        ok, msg = self.chat_manager.set_active_chat_list(name)
        if not ok:
            await event.answer(msg, alert=True)
            return
        state["join_selected_chat_list"] = name
        state.pop("join_selected_chat_list_candidate", None)
        await self._show_join_chats_menu(event)

    async def _show_join_launch_confirmation(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {})
        selected_sessions = state.get("join_selected_sessions", [])
        selected_list = state.get("join_selected_chat_list") or self.chat_manager.get_active_list_name()
        sessions_exist = self.session_manager.get_session_files()
        chat_list = self.chat_manager.get_chat_list(selected_list) if selected_list else None
        links = (chat_list or {}).get("links", [])

        warnings = []
        if not sessions_exist:
            warnings.append("• Вы не авторизовали ни одного аккаунта.")
        elif not selected_sessions:
            warnings.append("• Вы не выбрали аккаунты для входа в чаты.")
        if not selected_list:
            warnings.append("• Вы не выбрали базу чатов.")
        elif not links:
            warnings.append("• В выбранной базе нет ссылок на чаты.")

        if warnings:
            await event.edit(
                "⚠️ Перепроверьте заполнение данных перед запуском.\n\n" + "\n".join(warnings),
                buttons=[
                    [Button.inline("◀️ Вернуться", b"join_chats_menu")],
                    [Button.inline("⏹️ Остановить", b"join_stop")],
                ],
            )
            return

        await event.edit(
            "⚠️ Перепроверьте данные перед запуском.\n\n"
            f"База чатов: {selected_list}\n"
            f"Чатов в базе: {len(links)}\n"
            f"Выбрано аккаунтов: {len(selected_sessions)}\n\n"
            "Если всё заполнено верно, нажмите «Запустить».",
            buttons=[
                [Button.inline("🚀 Запустить", b"join_launch")],
                [Button.inline("⏹️ Остановить", b"join_stop")],
            ],
        )

    async def _launch_join_process(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        state = self.user_states.setdefault(user_id, {})
        sessions = list(state.get("join_selected_sessions", []))
        list_name = state.get("join_selected_chat_list") or self.chat_manager.get_active_list_name()
        chat_list = self.chat_manager.get_chat_list(list_name) if list_name else None
        links = list((chat_list or {}).get("links", []))

        if not sessions or not list_name or not links:
            await self._show_join_launch_confirmation(event)
            return

        self.join_stop_flags[user_id] = False
        state["mode"] = "join_running"
        state["prompt_chat_id"] = event.chat_id
        state["prompt_message_id"] = event.message_id
        state["join_running_list"] = list_name
        state["join_running_sessions"] = sessions

        await event.edit(
            "⏳ Подождите, пока осуществляется этап запуска...",
            buttons=[[Button.inline("⏹️ Остановить", b"join_stop")]],
        )
        await self._run_join_chats(event, user_id, sessions, links)

    async def _stop_join_process(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        self.join_stop_flags[user_id] = True
        state = self.user_states.get(user_id, {})
        if state.get("mode") == "join_running":
            await event.answer("Остановка запрошена")
            try:
                await event.edit(
                    "⏹️ Останавливаем процесс входа в чаты...",
                    buttons=[[Button.inline("◀️ Назад", b"menu_settings")]],
                )
            except Exception:
                pass
        else:
            self._clear_state(user_id)
            await event.edit("⏹️ Вход в чаты остановлен.", buttons=self._settings_menu_buttons())

    async def _cancel_join_chats(self, event):
        sender = await event.get_sender()
        self.join_stop_flags.pop(sender.id, None)
        self._clear_state(sender.id)
        await event.edit("🚪 Вход в чаты отменён.", buttons=self._settings_menu_buttons())

    async def _run_join_chats(self, event, user_id: int, sessions: List[str], links: List[str]):
        total_accounts = len(sessions)
        total_chats = len(links)
        overall_ok = 0
        overall_fail = 0
        stopped = False

        success_chats = []
        request_chats = []
        manual_chats = []

        for account_index, session_name in enumerate(sessions, start=1):
            if self.join_stop_flags.get(user_id):
                stopped = True
                break

            label = self._short_session_label(session_name)
            remaining_accounts = total_accounts - account_index
            client = None

            try:
                ok, client, display_name = await self.session_manager.open_session_client(session_name)
                if ok and display_name:
                    label = display_name

                if not ok or client is None:
                    overall_fail += total_chats
                    await event.edit(
                        f"⚠️ Не удалось открыть аккаунт: {label}\n"
                        f"Осталось аккаунтов: {remaining_accounts}",
                        buttons=[[Button.inline("⏹️ Остановить", b"join_stop")]],
                    )
                    await asyncio.sleep(1)
                    continue

                for chat_index, link in enumerate(links, start=1):
                    if self.join_stop_flags.get(user_id):
                        stopped = True
                        break

                    await event.edit(
                        f"🚀 Процесс входа начался\n\n"
                        f"{chat_index}/{total_chats} чатов\n"
                        f"Аккаунт: {label}\n"
                        f"Осталось аккаунтов: {remaining_accounts}",
                        buttons=[[Button.inline("⏹️ Остановить", b"join_stop")]],
                    )

                    try:
                        await self._join_single_chat(client, link)
                        overall_ok += 1
                        success_chats.append(link)

                    except Exception as e:
                        overall_fail += 1
                        error = str(e).lower()

                        if "request" in error or "approve" in error:
                            request_chats.append(link)
                        elif "verify" in error or "confirm" in error or "join" in error:
                            manual_chats.append(link)
                        else:
                            manual_chats.append(link)

                    await asyncio.sleep(1)

                if stopped:
                    break

            finally:
                if client:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass

        manual_chats = list(dict.fromkeys(manual_chats))
        request_chats = list(dict.fromkeys(request_chats))
        success_chats = list(dict.fromkeys(success_chats))

        self.join_stop_flags.pop(user_id, None)

        if stopped:
            self._clear_state(user_id)
            await event.edit(
                f"⏹️ Процесс входа остановлен.\n\n"
                f"✅ Успешно: {len(success_chats)}\n"
                f"🟡 Заявка отправлена: {len(request_chats)}\n"
                f"🔴 Требует ручного входа: {len(manual_chats)}",
                buttons=[[Button.inline("◀️ Назад", b"menu_settings")]],
            )
            return

        self.user_states[user_id] = {
            "manual_chats": manual_chats,
            "request_chats": request_chats,
            "success_chats": success_chats,
        }

        await event.edit(
            f"📊 Вход в чаты завершён\n\n"
            f"✅ Успешно: {len(success_chats)}\n"
            f"🟡 Заявка отправлена: {len(request_chats)}\n"
            f"🔴 Требует ручного входа: {len(manual_chats)}\n\n"
            f"Всего чатов: {total_chats}",
            buttons=[
                [Button.inline("📋 Ручной вход", b"show_manual_chats")],
                [Button.inline("🟡 Заявки", b"show_request_chats")],
                [Button.inline("◀️ Назад", b"menu_settings")],
            ],
        )

    async def _join_single_chat(self, client, target: str):
        target = str(target).strip()
        if not target:
            raise ValueError("Пустая ссылка")

        normalized = target.replace("https://", "").replace("http://", "")
        if normalized.startswith("t.me/"):
            normalized = normalized[5:]
        normalized = normalized.strip("/")

        if normalized.startswith("+"):
            invite_hash = normalized[1:]
            await client(ImportChatInviteRequest(invite_hash))
            return
        if normalized.startswith("joinchat/"):
            invite_hash = normalized.split("joinchat/", 1)[1]
            await client(ImportChatInviteRequest(invite_hash))
            return
        if target.startswith("@"):
            entity = await client.get_entity(target)
            await client(JoinChannelRequest(entity))
            return
        if normalized.isdigit() or (normalized.startswith("-") and normalized[1:].isdigit()):
            entity = await client.get_entity(int(normalized))
            await client(JoinChannelRequest(entity))
            return

        username = normalized.split("/")[0]
        entity = await client.get_entity(username)
        await client(JoinChannelRequest(entity))

    # ==================== AUTH / SESSIONS ====================
    async def _start_login(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        self.user_states[user_id] = {
            "mode": "awaiting_phone",
            "messages_to_delete": [],
            "prompt_chat_id": event.chat_id,
            "prompt_message_id": event.message_id,
        }
        await event.edit(
            "🔑 Отправьте номер телефона в международном формате.\nПример: +79991234567",
            buttons=[[Button.inline("❌ Отмена", b"cancel_login")]],
        )

    async def _cancel_login(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        try:
            await self.auth_handler.cancel_auth(user_id)
        except Exception:
            pass
        await self._cleanup_tracked_messages(user_id, keep_current=True, current_message_id=event.message_id, chat_id=event.chat_id)
        self._clear_state(user_id)
        await event.edit("❌ Авторизация отменена.", buttons=self._accounts_menu_buttons())

    async def _show_sessions(self, event):
        sessions = self.session_manager.get_session_files()
        current = self.session_manager.get_current_session_name()
        if not sessions:
            await event.edit(
                "📁 Активных сессий нет.\n\nХотите авторизовать аккаунт?",
                buttons=[
                    [Button.inline("🔑 Авторизация", b"login")],
                    [Button.inline("❌ Отмена", b"menu_accounts")],
                ],
            )
            return
        buttons = []
        for session_name in sessions:
            mark = "✅ " if session_name == current else ""
            buttons.append([
                Button.inline(f"{mark}Использовать {session_name}", f"use_session:{session_name}".encode()),
                Button.inline("🗑", f"delete_session:{session_name}".encode()),
            ])
        buttons.append([Button.inline("◀️ Назад", b"menu_accounts")])
        await event.edit("📁 Управление сессиями:", buttons=buttons)

    async def _switch_session(self, event, session_name: str):
        ok, msg = await self.session_manager.switch_to_session(session_name)
        if ok:
            self.broadcaster.set_client(self.session_manager.user_client)
        await event.edit(msg, buttons=self._accounts_menu_buttons())

    async def _delete_session(self, event, session_name: str):
        ok, msg = await self.session_manager.delete_session(session_name)
        await event.edit(msg, buttons=self._accounts_menu_buttons())

    # ==================== ADMIN ====================
    async def _show_users(self, event):
        users = self.data_manager.load_users()
        await event.edit(f"👥 Пользователей: {len(users)}", buttons=self._admin_panel_buttons())

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
        buttons.append([Button.inline("◀️ Назад", b"menu_admin")])
        await event.edit("\n".join(text), buttons=buttons)

    async def _start_add_admin(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        if not self.data_manager.is_owner(user_id):
            await event.answer("Только владелец может добавлять админов", alert=True)
            return
        self.user_states[user_id] = {
            "mode": "awaiting_admin_id",
            "messages_to_delete": [],
            "prompt_chat_id": event.chat_id,
            "prompt_message_id": event.message_id,
        }
        await event.edit(
            "👑 Отправьте ID пользователя, которого нужно сделать админом.",
            buttons=[[Button.inline("❌ Отмена", b"menu_admin")]],
        )

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
        await event.edit(("✅ " if ok else "❌ ") + msg, buttons=self._admin_panel_buttons())

    async def _show_stats(self, event):
        stats = self.data_manager.get_stats()
        users = len(self.data_manager.load_users())
        admins = len(self.data_manager.load_admins())
        chats = len(self.chat_manager.load_chat_ids())
        text = (
            "📈 Статистика\n\n"
            f"• Пользователей: {users}\n"
            f"• Админов: {admins}\n"
            f"• Чатов в активной базе: {chats}\n"
            f"• Отправлено сообщений: {stats.get('messages_sent', 0)}\n"
            f"• Рассылок: {stats.get('broadcasts', 0)}"
        )
        await event.edit(text, buttons=self._admin_panel_buttons())

    # ==================== HELPERS ====================
    def _track_message(self, user_id: int, message_id: int):
        state = self.user_states.setdefault(user_id, {"messages_to_delete": []})
        state.setdefault("messages_to_delete", []).append(message_id)

    async def _delete_prompt_message(self, user_id: int, chat_id: Optional[int] = None):
        state = self.user_states.get(user_id) or {}
        prompt_message_id = state.get("prompt_message_id")
        target_chat = chat_id or state.get("prompt_chat_id") or user_id
        if prompt_message_id:
            try:
                await self.bot.delete_messages(target_chat, [prompt_message_id])
            except Exception:
                pass
            if prompt_message_id in state.get("messages_to_delete", []):
                state["messages_to_delete"].remove(prompt_message_id)

    async def _cleanup_tracked_messages(self, user_id: int, keep_current: bool = False, current_message_id: Optional[int] = None, chat_id: Optional[int] = None):
        state = self.user_states.get(user_id) or {}
        ids = list(dict.fromkeys(state.get("messages_to_delete", [])))
        if keep_current and current_message_id:
            ids = [mid for mid in ids if mid != current_message_id]
        if ids:
            target_chat = chat_id or state.get("prompt_chat_id") or user_id
            try:
                await self.bot.delete_messages(target_chat, ids)
            except Exception:
                pass
        state["messages_to_delete"] = []

    async def _edit_or_send(self, chat_id: int, message_id: Optional[int], text: str, buttons=None):
        if message_id:
            try:
                await self.bot.edit_message(chat_id, message_id, text, buttons=buttons)
                return message_id
            except Exception:
                pass
        msg = await self.bot.send_message(chat_id, text, buttons=buttons)
        return msg.id

    async def _safe_delete(self, event):
        try:
            await event.delete()
        except Exception:
            pass

    async def _show_manual_chats(self, event):
        sender = await event.get_sender()
        user_id = sender.id

        chats = self.user_states.get(user_id, {}).get("manual_chats", [])

        if not chats:
            await event.answer("Нет чатов для ручного входа", alert=True)
            return

        text = "🔴 Чаты для ручного входа:\n\n" + "\n".join(chats[:100])
        await self.bot.send_message(
            event.chat_id,
            text,
            buttons=[[Button.inline("◀️ Назад", b"menu_settings")]],
        )

    async def _show_request_chats(self, event):
        sender = await event.get_sender()
        user_id = sender.id

        chats = self.user_states.get(user_id, {}).get("request_chats", [])

        if not chats:
            await event.answer("Нет чатов с заявкой", alert=True)
            return

        text = "🟡 Чаты, где отправлена заявка:\n\n" + "\n".join(chats[:100])
        await self.bot.send_message(
            event.chat_id,
            text,
            buttons=[[Button.inline("◀️ Назад", b"menu_settings")]],
        )

    def _clear_state(self, user_id: int):
        self.user_states.pop(user_id, None)
