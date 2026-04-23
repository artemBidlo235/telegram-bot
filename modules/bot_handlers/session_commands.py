# УПРАВЛЕНИЕ СЕССИЯМИ

from telethon import Button

class SessionCommandsMixin:
    """Миксин с командами управления сессиями"""
    
    async def _show_status(self, event):
        """Показать статус (какой аккаунт активен)"""
        if self.session_manager.user_client and self.session_manager.user_client.is_connected():
            try:
                me = await self.session_manager.user_client.get_me()
                acc = f"✅ {me.first_name}"
            except:
                acc = "❌ Ошибка"
        else:
            acc = "❌ Не авторизован"
        
        chat_ids = self.chat_manager.load_chat_ids()
        text = f"📊 **Статус**\n\n👤 Аккаунт: {acc}\n📁 Сессия: {self.session_manager.get_current_session_name() or 'Нет'}\n📝 Текст: {self.broadcaster.current_text[:50]}\n📋 Чатов: {len(chat_ids)}"
        
        await self._get_or_create_message(event, text, self.admin_menu)
    
    async def _session_management(self, event):
        """Показать список сессий"""
        sessions = self.session_manager.get_session_files()
        current = self.session_manager.get_current_session_name()
        buttons = []
        
        # Создаем кнопки для каждой сессии
        for s in sessions:
            if s == current:
                buttons.append([Button.text(f"✅ {s}")])  # Активная сессия
            else:
                buttons.append([Button.text(f"🔑 {s}"), Button.text(f"🗑️ {s}")])  # Переключить и удалить
        
        # Если нет сессий
        if not sessions:
            await self._get_or_create_message(
                event, 
                "📁 Сессии не найдены\n\n💡 Чтобы создать сессию, используйте 🔑 Логин", 
                [[Button.text("◀️ Назад")]]
            )
            return
        
        # Кнопка "Назад"
        buttons.append([Button.text("◀️ Назад")])
        
        text = f"📁 **Управление сессиями**\n\n📌 Текущая: {current or 'Нет'}\n📂 Всего сессий: {len(sessions)}\n\n🔑 - переключиться\n🗑️ - удалить\n✅ - активная"
        
        await self._get_or_create_message(event, text, buttons)
    
    async def _show_users(self, event):
        """Показать список зарегистрированных пользователей"""
        users = self.data_manager.load_users()
        
        if not users:
            await self._get_or_create_message(event, "📭 Нет зарегистрированных пользователей", self.admin_menu)
            return
        
        user_list = "👥 **Пользователи:**\n\n"
        # Показываем первых 20 пользователей
        for uid, data in list(users.items())[:20]:
            user_list += f"🆔 ID: `{uid}`\n👤 {data.get('first_name', '?')}\n📅 {data.get('joined_at', '?')[:10]}\n\n"
        
        if len(users) > 20:
            user_list += f"\n... и ещё {len(users) - 20} пользователей"
        
        await self._get_or_create_message(event, user_list, self.admin_menu)
    
    async def _show_full_stats(self, event):
        """Показать полную статистику бота"""
        stats = self.data_manager.get_stats()
        users_count = len(self.data_manager.load_users())
        admins_count = len(self.data_manager.get_admins_list())
        
        text = f"""
📊 **СТАТИСТИКА БОТА**

👥 Пользователей: {users_count}
👑 Администраторов: {admins_count}
📨 Отправлено сообщений: {stats.get('messages_sent', 0)}
📢 Проведено рассылок: {stats.get('broadcasts', 0)}

📁 Активная сессия: {self.session_manager.get_current_session_name() or 'Нет'}
✅ Бот работает стабильно
"""
        await self._get_or_create_message(event, text, self.admin_menu)