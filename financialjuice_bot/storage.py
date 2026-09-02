import json
import os
import tempfile
import time
from typing import Any, Dict


DEFAULT_STATE = {
    "version": 1,
    "sent": {},
    "calendar": {},
}


class StateStore:
    def __init__(self, path: str):
        self.path = path
        self.state: Dict[str, Any] = self._load()
        self.changed = False

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return json.loads(json.dumps(DEFAULT_STATE))
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("State root must be an object")
            data.setdefault("version", 1)
            data.setdefault("sent", {})
            data.setdefault("calendar", {})
            return data
        except (OSError, ValueError, json.JSONDecodeError):
            return json.loads(json.dumps(DEFAULT_STATE))

    def sent(self, key: str) -> bool:
        return key in self.state["sent"]

    def mark_sent(self, key: str) -> None:
        self.state["sent"][key] = int(time.time())
        self.changed = True

    def calendar_entry(self, event_id: str) -> Dict[str, Any]:
        entry = self.state["calendar"].setdefault(
            event_id,
            {"fingerprint": "", "actual_sent": False, "last_seen": 0},
        )
        return entry

    def update_calendar_seen(self, event_id: str, fingerprint: str) -> None:
        entry = self.calendar_entry(event_id)
        if entry.get("fingerprint") != fingerprint or not entry.get("last_seen"):
            entry["fingerprint"] = fingerprint
            entry["last_seen"] = int(time.time())
            self.changed = True

    def actual_sent(self, event_id: str) -> bool:
        return bool(self.calendar_entry(event_id).get("actual_sent"))

    def mark_actual_sent(self, event_id: str) -> None:
        entry = self.calendar_entry(event_id)
        if not entry.get("actual_sent"):
            entry["actual_sent"] = True
            self.changed = True

    def prune(self, retention_days: int) -> None:
        cutoff = int(time.time()) - retention_days * 86400
        old_sent = [k for k, v in self.state["sent"].items() if int(v) < cutoff]
        for k in old_sent:
            del self.state["sent"][k]
            self.changed = True
        old_cal = [
            k
            for k, v in self.state["calendar"].items()
            if int(v.get("last_seen", 0)) < cutoff
        ]
        for k in old_cal:
            del self.state["calendar"][k]
            self.changed = True

    def save(self) -> None:
        if not self.changed:
            return
        parent = os.path.dirname(self.path) or "."
        os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="state-", suffix=".json", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, ensure_ascii=False, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
            self.changed = False
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
