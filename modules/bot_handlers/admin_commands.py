# ОСНОВНЫЕ КОМАНДЫ АДМИНИСТРАТОРА
from telethon import Button

class AdminCommandsMixin:
    """Миксин с основными командами админа"""
    
    async def _admin_commands(self, event, text):
        """Обработка основных команд админа"""
        user_id = event.sender_id
        
        # Если пользователь в процессе ввода (например, ждет код)
        if user_id in self.auth_states and 'step' in self.auth_states[user_id]:
            await self._handle_states(event, text)
            return
        
        # КНОПКА "НАЗАД"
        if text == "◀️ Назад":
            await self._get_or_create_message(event, "🔙 Главное меню", self.admin_menu)
        
        # КНОПКА "СМЕНИТЬ ТЕКСТ"
        elif text == "📝 Сменить текст":
            self.auth_states[user_id] = {'step': 'awaiting_new_text'}
            msg = await self._get_or_create_message(  # ✅ Исправлено: event.respond -> self._get_or_create_message
                event,
                f"📝 Текущий текст:\n{self.broadcaster.current_text}\n\nОтправьте новый текст:",
                [[Button.text("❌ Отмена")]]
            )
            self.auth_states[user_id]['main_msg_id'] = msg.id
        
        # КНОПКА "ОСТАНОВИТЬ"
        elif text == "⏹️ Остановить":
            if self.broadcaster.is_broadcasting:
                self.broadcaster.stop()
                await self._get_or_create_message(event, "⏸️ Рассылка остановлена", self.admin_menu)
            else:
                await self._get_or_create_message(event, "ℹ️ Рассылка не активна", self.admin_menu)
        
        # КНОПКА "СТАТУС"
        elif text == "📊 Статус":
            await self._show_status(event)
        
        # КНОПКА "ЛОГИН"
        elif text == "🔑 Логин":
            self.auth_states[user_id] = {'step': 'awaiting_phone'}
            msg = await self._get_or_create_message(  # ✅ Исправлено: event.respond -> self._get_or_create_message
                event,
                "📱 Введите номер телефона (пример: +79123456789):",
                [[Button.text("❌ Отмена")]]
            )
            self.auth_states[user_id]['main_msg_id'] = msg.id
        
        # КНОПКА "УПРАВЛЕНИЕ СЕССИЯМИ"
        elif text == "📁 Управление сессиями":
            await self._session_management(event)
        
        # КНОПКА "ПОЛЬЗОВАТЕЛИ"
        elif text == "👥 Пользователи":
            await self._show_users(event)
        
        # КНОПКА "СТАТИСТИКА"
        elif text == "📈 Статистика":
            await self._show_full_stats(event)
        
        # КНОПКА "УПРАВЛЕНИЕ АДМИНАМИ"
        elif text == "👑 Управление админами":
            await self._admin_management(event)
        
        # КНОПКА "ЗАПУСТИТЬ РАССЫЛКУ (ПО ЧАТАМ)"
        elif text == "📋 Запустить рассылку (по чатам)":
            await self._broadcast_chats(event)
        
        # КНОПКА "РАССЫЛКА ПОЛЬЗОВАТЕЛЯМ"
        elif text == "📢 Рассылка пользователям":
            await self._broadcast_users(event)
        
        # КНОПКА "ПОМЕНЯТЬ БАЗУ ЧАТОВ"
        elif text == "🔄 Поменять базу чатов":
            await self._change_chat_base(event)
        
        # КНОПКА "ОТМЕНА"
        elif text == "❌ Отмена":
            if user_id in self.auth_states:
                # Очищаем все состояния
                self.auth_states[user_id] = {}
            # Возвращаем в главное меню
            await self._get_or_create_message(event, "❌ Отменено. Возврат в главное меню", self.admin_menu)
        
        # ВЫБОР СЕССИИ (кнопки 🔑 и 🗑️)
        elif text.startswith("🔑 "):
            session_name = text[2:]
            success, msg = await self.session_manager.switch_to_session(session_name)
            await self._get_or_create_message(event, msg, self.admin_menu)
            if success:
                self.broadcaster.set_client(self.session_manager.user_client)
        
        elif text.startswith("🗑️ "):
            session_name = text[2:]
            success, msg = await self.session_manager.delete_session(session_name)
            await self._get_or_create_message(event, msg, self.admin_menu)