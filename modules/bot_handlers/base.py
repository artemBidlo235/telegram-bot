# ОСНОВА БОТА - тут хранятся общие вещи

from telethon import events, Button

class BotHandlersBase:
    def __init__(self, bot, data_manager, session_manager, chat_manager, broadcaster, auth_handler):
        # Сохраняем все переданные объекты
        self.bot = bot
        self.data_manager = data_manager
        self.session_manager = session_manager
        self.chat_manager = chat_manager
        self.broadcaster = broadcaster
        self.auth_handler = auth_handler
        
        # Хранилище для временных данных пользователей
        self.auth_states = {}
        
        # КНОПКИ МЕНЮ ДЛЯ ОБЫЧНОГО ПОЛЬЗОВАТЕЛЯ
        self.user_menu = [
            [Button.inline("📊 Статус", b"status")],
            [Button.inline("ℹ️ О боте", b"about")]
        ]
        
        # КНОПКИ МЕНЮ ДЛЯ АДМИНИСТРАТОРА (полная версия)
        self.admin_menu = [
            [Button.inline("📋 Запустить рассылку (по чатам)", b"start_broadcast")],
            [Button.inline("📢 Рассылка пользователям", b"user_broadcast")],
            [Button.inline("🔄 Поменять базу чатов", b"change_chat_db")],
            [Button.inline("📝 Сменить текст", b"change_text"), Button.inline("⏹️ Остановить", b"stop")],
            [Button.inline("📊 Статус", b"status"), Button.inline("🔑 Логин", b"login")],
            [Button.inline("📁 Управление сессиями", b"sessions"), Button.inline("👥 Пользователи", b"users")],
            [Button.inline("👑 Управление админами", b"admins"), Button.inline("📈 Статистика", b"stats")],
            [Button.inline("◀️ Назад", b"back")]
        ]
        
        # Регистрируем команды бота
        self._register_handlers()
    
    def _register_handlers(self):
        # Команда /start
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await self._handle_start(event)
        
        # Обработка всех остальных сообщений
        @self.bot.on(events.NewMessage)
        async def message_handler(event):
            await self._handle_message(event)

        # 🔥 ВОТ ОН — ОБРАБОТЧИК КНОПОК (добавлено)
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            data = event.data.decode()
            user_id = event.sender_id

            print("Нажата кнопка:", data)

            # Пример обработки
            if data == "status":
                await event.edit(
                    "📊 Статус бота:\n\n✅ Работает",
                    buttons=self.admin_menu if self.data_manager.is_admin(user_id) else self.user_menu
                )

            elif data == "about":
                await event.edit(
                    "ℹ️ Это твой бот",
                    buttons=self.user_menu
                )

            elif data == "back":
                await event.edit(
                    "🔙 Главное меню",
                    buttons=self.admin_menu
                )

            # ⚠️ остальные кнопки пока просто логируются
            else:
                await event.edit(
                    f"⚙️ Нажата кнопка: {data}",
                    buttons=self.admin_menu if self.data_manager.is_admin(user_id) else self.user_menu
                )
    
    async def _safe_edit(self, chat_id, msg_id, text, buttons=None):
        """Безопасное редактирование - если не получится, не падаем"""
        try:
            if buttons:
                await self.bot.edit_message(chat_id, msg_id, text, buttons=buttons)
            else:
                await self.bot.edit_message(chat_id, msg_id, text)
            return True, msg_id
        except Exception as e:
            print(f"Ошибка редактирования: {e}")
            return False, msg_id
    
    async def _get_or_create_message(self, event, text, buttons):
        """Найти главное сообщение пользователя или создать новое"""
        user_id = event.sender_id
        state = self.auth_states.get(user_id, {})
        msg_id = state.get('main_msg_id')
        chat_id = state.get('chat_id')
        
        # Пробуем отредактировать существующее
        if msg_id and chat_id:
            success, _ = await self._safe_edit(chat_id, msg_id, text, buttons)
            if success:
                return msg_id, chat_id
        
        # 🚨 ЛОГ (добавил)
        print("!!! СОЗДАЁТСЯ НОВОЕ СООБЩЕНИЕ !!!")

        # Создаем новое сообщение
        msg = await event.respond(text, buttons=buttons)
        self.auth_states[user_id] = {'main_msg_id': msg.id, 'chat_id': event.chat_id}
        return msg.id, event.chat_id
    
    async def _handle_start(self, event):
        """Что происходит когда пользователь пишет /start"""
        user_id = event.sender_id
        first_name = event.sender.first_name
        username = event.sender.username
        
        self.data_manager.add_user(user_id, first_name, username)
        
        if self.data_manager.is_admin(user_id):
            role = "Владелец" if self.data_manager.is_owner(user_id) else "Администратор"
            msg = await event.respond(
                f"👋 Привет, {first_name}!\n\n👑 Ваша роль: {role}\n\n✅ Вам доступны все функции бота.",
                buttons=self.admin_menu
            )
            self.auth_states[user_id] = {'main_msg_id': msg.id, 'chat_id': event.chat_id}
        else:
            msg = await event.respond(
                f"👋 Привет, {first_name}!\n\n✅ Вы зарегистрированы как пользователь.",
                buttons=self.user_menu
            )
            self.auth_states[user_id] = {'main_msg_id': msg.id, 'chat_id': event.chat_id}
    
    async def _handle_message(self, event):
        """Обработка всех сообщений"""
        user_id = event.sender_id
        text = event.raw_text
        
        if not text.startswith('/'):
            self.data_manager.add_user(user_id, event.sender.first_name, event.sender.username)
        
        if not self.data_manager.is_admin(user_id):
            await self._user_commands(event, text)
            return
        
        await self._admin_commands(event, text)
    
    async def _cancel_and_back(self, event):
        """Отмена текущего действия и возврат в главное меню"""
        user_id = event.sender_id
        
        if user_id in self.auth_states:
            self.auth_states[user_id] = {}
        
        await self._get_or_create_message(event, "❌ Отменено. Главное меню.", self.admin_menu)