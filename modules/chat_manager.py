from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re


class ChatManager:
    def __init__(self, chat_file: Path):
        self.chat_file = Path(chat_file)
        self.chat_lists_file = self.chat_file.with_name("chat_lists.json")

    def load_chat_ids(self) -> List[int]:
        chat_ids: List[int] = []
        try:
            with open(self.chat_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            chat_ids.append(int(line))
                        except Exception:
                            pass
        except FileNotFoundError:
            pass
        return chat_ids

    def save_chat_ids(self, chat_ids: List[int]) -> bool:
        try:
            with open(self.chat_file, 'w', encoding='utf-8') as f:
                for chat_id in chat_ids:
                    f.write(f"{chat_id}\n")
            return True
        except Exception:
            return False

    def _load_chat_lists_store(self) -> Dict:
        try:
            with open(self.chat_lists_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {"active_list": None, "lists": {}}
                data.setdefault("active_list", None)
                data.setdefault("lists", {})
                return data
        except FileNotFoundError:
            return {"active_list": None, "lists": {}}
        except Exception:
            return {"active_list": None, "lists": {}}

    def _save_chat_lists_store(self, data: Dict) -> bool:
        try:
            with open(self.chat_lists_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get_active_list_name(self) -> Optional[str]:
        return self._load_chat_lists_store().get("active_list")

    def get_chat_lists_names(self) -> List[str]:
        store = self._load_chat_lists_store()
        return sorted(store.get("lists", {}).keys(), key=lambda x: x.lower())

    def get_chat_list(self, name: str) -> Optional[Dict]:
        store = self._load_chat_lists_store()
        item = store.get("lists", {}).get(name)
        if not item:
            return None
        return {
            "name": name,
            "links": item.get("links", []),
            "chat_ids": item.get("chat_ids", []),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }

    def create_chat_list(self, name: str, links: List[str], chat_ids: List[int]) -> Tuple[bool, str]:
        store = self._load_chat_lists_store()
        lists = store.setdefault("lists", {})
        if name in lists:
            return False, "Список с таким названием уже существует"
        now = datetime.now().isoformat()
        lists[name] = {
            "links": list(dict.fromkeys(links)),
            "chat_ids": list(dict.fromkeys(chat_ids)),
            "created_at": now,
            "updated_at": now,
        }
        self._save_chat_lists_store(store)
        return True, "Список создан"

    def append_to_chat_list(self, name: str, links: List[str], chat_ids: List[int]) -> Tuple[bool, str, int]:
        store = self._load_chat_lists_store()
        item = store.setdefault("lists", {}).get(name)
        if not item:
            return False, "Список не найден", 0
        old_ids = item.get("chat_ids", [])
        old_links = item.get("links", [])
        before = len(old_ids)
        item["chat_ids"] = list(dict.fromkeys(old_ids + chat_ids))
        item["links"] = list(dict.fromkeys(old_links + links))
        item["updated_at"] = datetime.now().isoformat()
        self._save_chat_lists_store(store)
        return True, "Список обновлён", len(item["chat_ids"]) - before

    def replace_chat_list(self, name: str, links: List[str], chat_ids: List[int]) -> Tuple[bool, str]:
        store = self._load_chat_lists_store()
        item = store.setdefault("lists", {}).get(name)
        if not item:
            return False, "Список не найден"
        item["links"] = list(dict.fromkeys(links))
        item["chat_ids"] = list(dict.fromkeys(chat_ids))
        item["updated_at"] = datetime.now().isoformat()
        self._save_chat_lists_store(store)
        return True, "Список перезаписан"

    def set_active_chat_list(self, name: str) -> Tuple[bool, str]:
        store = self._load_chat_lists_store()
        item = store.get("lists", {}).get(name)
        if not item:
            return False, "Список не найден"
        ok = self.save_chat_ids(item.get("chat_ids", []))
        if not ok:
            return False, "Не удалось сохранить активную базу чатов"
        store["active_list"] = name
        self._save_chat_lists_store(store)
        return True, "Активный список выбран"

    def clear_active_chat_ids(self) -> bool:
        return self.save_chat_ids([])

    def parse_links_input(self, raw_text: str) -> List[str]:
        if not raw_text:
            return []
        normalized = raw_text.replace(",", " ").replace(";", " ")
        tokens = re.split(r"\s+", normalized)
        links: List[str] = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if token.startswith(("https://", "http://", "t.me/", "@")):
                links.append(token)
        return links

    async def convert_links_to_ids(self, client, links: List[str]) -> Tuple[List[Dict], List[str]]:
        results = []
        seen_links = []
        duplicates = []
        seen_set = set()

        for raw_link in links:
            link = raw_link.strip()
            if not link:
                continue
            if link in seen_set:
                duplicates.append(link)
            else:
                seen_set.add(link)
                seen_links.append(link)

        for link in seen_links:
            try:
                entity = await client.get_entity(link)
                results.append({
                    'link': link,
                    'id': entity.id,
                    'title': getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Без названия'),
                    'success': True
                })
            except Exception as e:
                results.append({'link': link, 'error': str(e), 'success': False})

        return results, duplicates
