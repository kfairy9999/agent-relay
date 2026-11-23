"""Shared task board: one row per task_id, updated by each envelope."""

from __future__ import annotations

from typing import Optional

from .models import Envelope, Task, _utcnow
from .store import RelayStore


class TaskBoard:
    def __init__(self, store: RelayStore):
        self.store = store

    def post(self, env: Envelope) -> Task:
        """Validate, persist the envelope, and roll it into the board."""
        env.validate()
        self.store.append_message(env)
        tasks = self.store.load_tasks()
        existing = tasks.get(env.task_id)
        if existing is None:
            task = Task.from_envelope(env)
        else:
            task = self._merge(existing, env)
        tasks[env.task_id] = task
        self.store.save_tasks(tasks)
        return task

    def get(self, task_id: str) -> Task:
        tasks = self.store.load_tasks()
        if task_id not in tasks:
            raise KeyError(f"unknown task: {task_id}")
        return tasks[task_id]

    def list(self, status: Optional[str] = None) -> list[Task]:
        tasks = list(self.store.load_tasks().values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: (t.due or "9999-99-99", t.task_id))
        return tasks

    def apply_approval(self, env: Envelope) -> Task:
        """Rewrite a message after approval and sync the board row."""
        env.validate()
        self.store.update_message(env)
        tasks = self.store.load_tasks()
        existing = tasks.get(env.task_id)
        if existing is None:
            task = Task.from_envelope(env)
        else:
            task = self._merge(existing, env)
        tasks[env.task_id] = task
        self.store.save_tasks(tasks)
        return task

    @staticmethod
    def _merge(existing: Task, env: Envelope) -> Task:
        message_ids = list(existing.message_ids)
        if env.id not in message_ids:
            message_ids.append(env.id)
        return Task(
            task_id=env.task_id,
            status=env.status,
            ask=env.ask or existing.ask,
            from_agent=env.from_agent,
            to=env.to,
            due=env.due if env.due is not None else existing.due,
            artifacts=list(env.artifacts) if env.artifacts else list(existing.artifacts),
            updated_at=_utcnow(),
            message_ids=message_ids,
            approved=env.approved,
            approved_by=env.approved_by or existing.approved_by,
            outreach_key=env.outreach_key or existing.outreach_key,
        )
