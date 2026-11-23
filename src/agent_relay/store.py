"""File-backed store: board, messages, ledger, outbox. No secrets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .models import Envelope, Task, ValidationError


class RelayStore:
    """JSON / JSONL files under a single data directory."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.board_path = self.root / "board.json"
        self.messages_path = self.root / "messages.jsonl"
        self.ledger_path = self.root / "ledger.jsonl"
        self.outbox_dir = self.root / "outbox"
        self.agents_path = self.root / "agents.json"

    def init(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        if not self.board_path.exists():
            self._write_json(self.board_path, {"tasks": {}})
        if not self.messages_path.exists():
            self.messages_path.touch()
        if not self.ledger_path.exists():
            self.ledger_path.touch()
        if not self.agents_path.exists():
            self._write_json(self.agents_path, {"agents": {}})

    def load_tasks(self) -> dict[str, Task]:
        self.init()
        raw = self._read_json(self.board_path)
        tasks_raw = raw.get("tasks") or {}
        if not isinstance(tasks_raw, dict):
            raise ValidationError("board.json tasks must be an object")
        return {key: Task.from_dict(value) for key, value in tasks_raw.items()}

    def save_tasks(self, tasks: dict[str, Task]) -> None:
        self.init()
        payload = {"tasks": {key: task.to_dict() for key, task in tasks.items()}}
        self._write_json(self.board_path, payload)

    def append_message(self, env: Envelope) -> None:
        self.init()
        line = json.dumps(env.to_dict(), ensure_ascii=False, sort_keys=True)
        with self.messages_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def load_messages(self) -> list[Envelope]:
        self.init()
        messages: list[Envelope] = []
        text = self.messages_path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                messages.append(Envelope.from_dict(json.loads(line)))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValidationError(f"messages.jsonl line {lineno}: {exc}") from exc
        return messages

    def get_message(self, message_id: str) -> Envelope:
        for env in self.load_messages():
            if env.id == message_id:
                return env
        raise KeyError(f"unknown message: {message_id}")

    def rewrite_messages(self, messages: list[Envelope]) -> None:
        self.init()
        tmp = self.messages_path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for env in messages:
                handle.write(json.dumps(env.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        tmp.replace(self.messages_path)

    def update_message(self, env: Envelope) -> None:
        messages = self.load_messages()
        found = False
        for i, existing in enumerate(messages):
            if existing.id == env.id:
                messages[i] = env
                found = True
                break
        if not found:
            raise KeyError(f"unknown message: {env.id}")
        self.rewrite_messages(messages)

    def load_agents(self) -> dict[str, dict[str, str]]:
        self.init()
        raw = self._read_json(self.agents_path)
        agents = raw.get("agents") or {}
        if not isinstance(agents, dict):
            return {}
        return {str(k).lower(): {str(ik): str(iv) for ik, iv in v.items()} if isinstance(v, dict) else {} for k, v in agents.items()}

    def save_agents(self, agents: dict[str, dict[str, str]]) -> None:
        self.init()
        self._write_json(self.agents_path, {"agents": agents})

    def write_outbox(self, message_id: str, raw_email: str) -> Path:
        self.init()
        path = self.outbox_dir / f"{message_id}.eml"
        path.write_text(raw_email, encoding="utf-8")
        return path

    def append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        self.init()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        self.init()
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        if not isinstance(raw, dict):
            raise ValidationError(f"{path.name} must contain a JSON object")
        return raw

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
