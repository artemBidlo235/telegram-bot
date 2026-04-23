# УПРАВЛЕНИЕ ДАННЫМИ - ПОЛНАЯ ВЕРСИЯ
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class DataManager:
    def __init__(self, admins_file, users_file, stats_file):
        self.admins_file = admins_file
        self.users_file = users_file
        self.stats_file = stats_file
    
    # ========== АДМИНЫ ==========
    def load_admins(self) -> Dict:
        try:
            with open(self.admins_file, 'r', encoding='utf-8') as f:
                return {int(k): v for k, v in json.load(f).items()}
        except FileNotFoundError:
            default = {1031953955: {"role": "owner", "added_by": "system", "added_at": datetime.now().isoformat()}}
            self.save_admins(default)
            return default
        except:
            return {}
    
    def save_admins(self, admins: Dict) -> bool:
        try:
            with open(self.admins_file, 'w', encoding='utf-8') as f:
                json.dump(admins, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False
    
    def is_admin(self, user_id: int) -> bool:
        return user_id in self.load_admins()
    
    def is_owner(self, user_id: int) -> bool:
        admins = self.load_admins()
        return user_id in admins and admins[user_id].get("role") == "owner"
    
    def add_admin(self, admin_id: int, added_by: int, username: str = None) -> Tuple[bool, str]:
        admins = self.load_admins()
        if admin_id in admins:
            return False, "Пользователь уже является админом"
        
        admins[admin_id] = {
            "role": "admin",
            "added_by": added_by,
            "added_at": datetime.now().isoformat(),
            "username": username
        }
        self.save_admins(admins)
        return True, "Админ добавлен"
    
    def remove_admin(self, admin_id: int) -> Tuple[bool, str]:
        admins = self.load_admins()
        if admin_id not in admins:
            return False, "Пользователь не является админом"
        if admins[admin_id].get("role") == "owner":
            return False, "Нельзя удалить владельца"
        
        del admins[admin_id]
        self.save_admins(admins)
        return True, "Админ удалён"
    
    def get_admins_list(self) -> List[Dict]:
        admins = self.load_admins()
        return [{"id": uid, "role": data.get("role", "admin"), "added_by": data.get("added_by"), "added_at": data.get("added_at"), "username": data.get("username")} for uid, data in admins.items()]
    
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    def load_users(self) -> Dict:
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def save_users(self, users: Dict) -> bool:
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False
    
    def add_user(self, user_id: int, first_name: str, username: str = None) -> bool:
        users = self.load_users()
        if str(user_id) not in users:
            users[str(user_id)] = {"first_name": first_name, "username": username, "joined_at": datetime.now().isoformat(), "last_active": datetime.now().isoformat()}
            self.save_users(users)
            return True
        else:
            users[str(user_id)]["last_active"] = datetime.now().isoformat()
            self.save_users(users)
            return False
    
    # ========== СТАТИСТИКА ==========
    def get_stats(self) -> Dict:
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"messages_sent": 0, "broadcasts": 0}
    
    def update_stats(self, messages_count: int = 0) -> None:
        stats = self.get_stats()
        stats["messages_sent"] += messages_count
        if messages_count > 0:
            stats["broadcasts"] += 1
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
        except:
            pass