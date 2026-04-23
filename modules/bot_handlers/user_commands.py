# КОМАНДЫ ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ

class UserCommandsMixin:
    """Миксин с командами для обычных пользователей"""
    
    async def _user_commands(self, event, text):
        """Обработка команд от обычного пользователя"""
        
        # Кнопка "Статус"
        if text == "📊 Статус" or text == "/status":
            stats = self.data_manager.get_stats()
            users_count = len(self.data_manager.load_users())
            await self._get_or_create_message(
                event,
                f"📊 Статус бота\n👥 Пользователей: {users_count}\n📨 Отправлено: {stats.get('messages_sent', 0)}",
                self.user_menu
            )
        
        # Кнопка "О боте"
        elif text == "ℹ️ О боте":
            await self._get_or_create_message(
                event,
                "🤖 Бот для управления рассылками\nВерсия: 3.0 (полная)",
                self.user_menu
            )