# УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ

from telethon import Button

class AdminManagementMixin:
    """Миксин с командами управления админами (только для владельца)"""
    
    async def _admin_management(self, event):
        """Показать список администраторов и кнопки управления"""
        # Только владелец может управлять админами
        if not self.data_manager.is_owner(event.sender_id):
            await self._get_or_create_message(event, "❌ Только владелец может управлять администраторами!", self.admin_menu)
            return
        
        # Получаем список админов
        admins = self.data_manager.get_admins_list()
        admin_list = "👑 **Администраторы:**\n\n"
        for a in admins:
            admin_list += f"🆔 {a['id']} - {a['role']}\n"
        
        # Кнопки для управления
        buttons = [
            [Button.text("➕ Добавить админа")],
            [Button.text("➖ Удалить админа")],
            [Button.text("◀️ Назад")]
        ]
        
        # ✅ ИСПРАВЛЕНО: добавил event первым параметром
        msg = await self._get_or_create_message(event, admin_list, buttons)
        self.auth_states[event.sender_id]['admin_msg_id'] = msg.id