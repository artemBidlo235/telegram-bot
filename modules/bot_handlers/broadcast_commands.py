# КОМАНДЫ ДЛЯ РАССЫЛКИ

class BroadcastCommandsMixin:
    """Миксин с командами рассылки"""
    
    async def _broadcast_chats(self, event):
        """Запустить рассылку по чатам из файла chat.txt"""
        # Проверяем, авторизован ли аккаунт
        if not self.session_manager.user_client or not self.session_manager.user_client.is_connected():
            await self._get_or_create_message(event, "❌ Сначала авторизуйтесь через 🔑 Логин", self.admin_menu)
            return
        
        # Загружаем список чатов
        chat_ids = self.chat_manager.load_chat_ids()
        if not chat_ids:
            await self._get_or_create_message(event, "❌ Нет чатов. Нажмите 🔄 Поменять базу", self.admin_menu)
            return
        
        # Отправляем статус и запускаем рассылку
        status_msg = await event.respond(f"🚀 Рассылка в {len(chat_ids)} чатов...")
        
        result = await self.broadcaster.send_to_chats(chat_ids)
        await status_msg.edit(f"✅ Завершено!\n✅ {result[0]}\n❌ {result[1]}")
        self.data_manager.update_stats(result[0])
    
    async def _broadcast_users(self, event):
        """Запустить рассылку всем зарегистрированным пользователям"""
        users = self.data_manager.load_users()
        
        if not users:
            await self._get_or_create_message(event, "❌ Нет зарегистрированных пользователей", self.admin_menu)
            return
        
        # Переводим в режим ожидания текста для рассылки
        self.auth_states[event.sender_id]['step'] = 'broadcast_to_users'
        msg = await self._get_or_create_message(  # ← ИСПРАВЛЕНО: event.respond → self._get_or_create_message
            event, 
            f"📢 Отправьте сообщение для рассылки {len(users)} пользователям:",
            buttons=[[Button.text("❌ Отмена")]]
        )
        self.auth_states[event.sender_id]['main_msg_id'] = msg.id
    
    async def _change_chat_base(self, event):
        """Поменять базу чатов (конвертировать ссылки в ID)"""
        # Проверяем, авторизован ли аккаунт
        if not self.session_manager.user_client or not self.session_manager.user_client.is_connected():
            await self._get_or_create_message(event, "❌ Сначала авторизуйтесь", self.admin_menu)
            return
        
        # Переводим в режим ожидания ссылок
        self.auth_states[event.sender_id]['step'] = 'awaiting_chat_links'
        msg = await self._get_or_create_message(  # ← ИСПРАВЛЕНО: event.respond → self._get_or_create_message
            event,
            "📋 Отправьте список ссылок (по одной на строку):\n\nПример:\n@chat1\nhttps://t.me/chat2",
            buttons=[[Button.text("❌ Отмена")]]
        )
        self.auth_states[event.sender_id]['main_msg_id'] = msg.id