# АУТЕНТИФИКАЦИЯ - ПОЛНАЯ ВЕРСИЯ
import asyncio
from pathlib import Path
from telethon import TelegramClient

class AuthHandler:
    def __init__(self, sessions_dir: Path, api_id: int, api_hash: int):
        self.sessions_dir = sessions_dir
        self.api_id = api_id
        self.api_hash = api_hash
        self.temp_clients = {}
        self.auth_states = {}
    
    async def start_login(self, user_id: int, phone: str):
        try:
            temp_path = self.sessions_dir / f'temp_{user_id}'
            temp_client = TelegramClient(str(temp_path), self.api_id, self.api_hash)
            await temp_client.connect()
            
            result = await temp_client.send_code_request(phone)
            
            self.temp_clients[user_id] = temp_client
            self.auth_states[user_id] = {
                'phone': phone,
                'hash': result.phone_code_hash,
                'step': 'awaiting_code'
            }
            return True, "Код отправлен", temp_client
        except Exception as e:
            return False, str(e), None
    
    async def complete_login(self, user_id: int, code: str):
        if user_id not in self.temp_clients:
            return False, "Сессия не найдена", None
        
        temp_client = self.temp_clients[user_id]
        state = self.auth_states[user_id]
        
        try:
            await temp_client.sign_in(phone=state['phone'], code=code, phone_code_hash=state['hash'])
            
            me = await temp_client.get_me()
            session_name = f"{me.first_name}_{state['phone'][-5:]}.session"
            
            await temp_client.disconnect()
            await asyncio.sleep(0.5)
            
            temp_path = self.sessions_dir / f'temp_{user_id}.session'
            session_path = self.sessions_dir / session_name
            if temp_path.exists():
                temp_path.rename(session_path)
            
            del self.temp_clients[user_id]
            del self.auth_states[user_id]
            
            return True, f"✅ Авторизован: {me.first_name}", session_name
        except Exception as e:
            return False, str(e), None
    
    def cancel_auth(self, user_id: int):
        if user_id in self.temp_clients:
            asyncio.create_task(self.temp_clients[user_id].disconnect())
            del self.temp_clients[user_id]
        if user_id in self.auth_states:
            del self.auth_states[user_id]