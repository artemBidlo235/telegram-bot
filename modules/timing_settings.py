from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


class TimingSettings:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)
        self.defaults = {
            "broadcast_delay": 5,
            "join_delay": 1,
            "account_message_limit": 50,
        }
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        except Exception:
            data = {}
        result = dict(self.defaults)
        result.update({k: v for k, v in data.items() if k in self.defaults})
        return result

    def save(self, data: Dict[str, Any]) -> bool:
        current = self.load()
        current.update(data)
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get_broadcast_delay(self) -> int:
        return max(0, int(self.load().get("broadcast_delay", self.defaults["broadcast_delay"])))

    def get_join_delay(self) -> int:
        return max(0, int(self.load().get("join_delay", self.defaults["join_delay"])))

    def get_account_message_limit(self) -> int:
        return max(1, int(self.load().get("account_message_limit", self.defaults["account_message_limit"])))

    def set_broadcast_delay(self, value: int) -> bool:
        return self.save({"broadcast_delay": max(0, int(value))})

    def set_join_delay(self, value: int) -> bool:
        return self.save({"join_delay": max(0, int(value))})

    def set_account_message_limit(self, value: int) -> bool:
        return self.save({"account_message_limit": max(1, int(value))})
