# ОБРАБОТКА СОСТОЯНИЙ (когда бот ждет ответ)

import asyncio
from telethon import Button

class StatesMixin:
    """Миксин для обработки состояний (ожидание ввода)"""
    
    async def _handle_states(self, event, text):
        """Обработка всех состояний (логин, смена текста, рассылка и т.д.)"""
        user_id = event.sender_id
        state = self.auth_states.get(user_id, {})
        step = state.get('step')
        msg_id = state.get('main_msg_id')
        chat_id = state.get('chat_id', event.chat_id)
        
        # ========== ОТМЕНА В ЛЮБОМ СОСТОЯНИИ ==========
        if text == "❌ Отмена":
            # Очищаем состояние
            if user_id in self.auth_states:
                self.auth_states[user_id] = {}
            # Показываем главное меню
            await self._get_or_create_message(event, "❌ Действие отменено. Главное меню.", self.admin_menu)
            return
        
        # ========== СОСТОЯНИЕ: СМЕНА ТЕКСТА ==========
        if step == 'awaiting_new_text':
            self.broadcaster.set_message_text(text)
            try:
                await self.bot.edit_message(chat_id, msg_id, f"✅ Текст изменён!\n\n{text}", buttons=self.admin_menu)
            except:
                await self._get_or_create_message(event, f"✅ Текст изменён!\n\n{text}", self.admin_menu)
            self.auth_states[user_id] = {}
        
        # ========== СОСТОЯНИЕ: ЛОГИН - ВВОД ТЕЛЕФОНА ==========
        elif step == 'awaiting_phone' and text.startswith('+'):
            phone = text
            state['phone'] = phone
            state['step'] = 'awaiting_code'
            
            success, msg, _ = await self.auth_handler.start_login(user_id, phone)
            if success:
                try:
                    await self.bot.edit_message(chat_id, msg_id, "🔑 Введите код из Telegram:", buttons=[[Button.text("❌ Отмена")]])
                except:
                    await self._get_or_create_message(event, "🔑 Введите код из Telegram:", [[Button.text("❌ Отмена")]])
            else:
                try:
                    await self.bot.edit_message(chat_id, msg_id, f"❌ {msg}", buttons=self.admin_menu)
                except:
                    await self._get_or_create_message(event, f"❌ {msg}", self.admin_menu)
                self.auth_states[user_id] = {}
        
        # ========== СОСТОЯНИЕ: ЛОГИН - ВВОД КОДА ==========
        elif step == 'awaiting_code' and text.isdigit():
            success, msg, session_name = await self.auth_handler.complete_login(user_id, text)
            if success:
                await self.session_manager.switch_to_session(session_name)
                self.broadcaster.set_client(self.session_manager.user_client)
                try:
                    await self.bot.edit_message(chat_id, msg_id, f"✅ {msg}", buttons=self.admin_menu)
                except:
                    await self._get_or_create_message(event, f"✅ {msg}", self.admin_menu)
            else:
                try:
                    await self.bot.edit_message(chat_id, msg_id, f"❌ {msg}", buttons=self.admin_menu)
                except:
                    await self._get_or_create_message(event, f"❌ {msg}", self.admin_menu)
            self.auth_states[user_id] = {}
        
        # ========== СОСТОЯНИЕ: РАССЫЛКА ПОЛЬЗОВАТЕЛЯМ ==========
        elif step == 'broadcast_to_users':
            users = self.data_manager.load_users()
            success = 0
            fail = 0
            
            status_msg = await self._get_or_create_message(event, f"🚀 Рассылка {len(users)} пользователям...")
            
            for uid in users:
                try:
                    await self.bot.send_message(int(uid), text)
                    success += 1
                except:
                    fail += 1
                await asyncio.sleep(0.3)
            
            await status_msg.edit(f"✅ Рассылка завершена!\n✅ {success}\n❌ {fail}")
            self.data_manager.update_stats(success)
            self.auth_states[user_id] = {}
        
        # ========== СОСТОЯНИЕ: КОНВЕРТАЦИЯ ССЫЛОК ==========
        elif step == 'awaiting_chat_links':
            links = [l.strip() for l in text.split('\n') if l.strip()]
            results, dups = await self.chat_manager.convert_links_to_ids(self.session_manager.user_client, links)
            
            ok = [r for r in results if r['success']]
            if ok:
                ids = [r['id'] for r in ok]
                self.chat_manager.save_chat_ids(ids)
                try:
                    await self.bot.edit_message(chat_id, msg_id, f"✅ Сохранено {len(ok)} чатов", buttons=self.admin_menu)
                except:
                    await self._get_or_create_message(event, f"✅ Сохранено {len(ok)} чатов", self.admin_menu)
            else:
                try:
                    await self.bot.edit_message(chat_id, msg_id, "❌ Ошибка обработки ссылок", buttons=self.admin_menu)
                except:
                    await self._get_or_create_message(event, "❌ Ошибка обработки ссылок", self.admin_menu)
            
            self.auth_states[user_id] = {}
        
        # ========== СОСТОЯНИЕ: ДОБАВЛЕНИЕ АДМИНА ==========
        elif step == 'adding_admin':
            try:
                new_id = int(text.strip())
                success, msg = self.data_manager.add_admin(new_id, user_id)
                await self._get_or_create_message(event, f"✅ {msg}" if success else f"❌ {msg}", self.admin_menu)
            except:
                await self._get_or_create_message(event, "❌ Неверный ID", self.admin_menu)
            self.auth_states[user_id] = {}
        
        # ========== СОСТОЯНИЕ: УДАЛЕНИЕ АДМИНА ==========
        elif step == 'removing_admin':
            try:
                admin_id = int(text.strip())
                success, msg = self.data_manager.remove_admin(admin_id)
                await self._get_or_create_message(event, f"✅ {msg}" if success else f"❌ {msg}", self.admin_menu)
            except:
                await self._get_or_create_message(event, "❌ Неверный ID", self.admin_menu)
            self.auth_states[user_id] = {}