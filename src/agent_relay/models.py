"""Structured message envelope and task records.

The on-the-wire JSON uses ``from`` (not ``from_agent``) to match the
protocol: from, to, task_id, status, ask, due, artifacts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

STATUSES = (
    "open",
    "in_progress",
    "blocked",
    "need_approval",
    "approved",
    "done",
    "cancelled",
)

TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AGENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]*$")


class ValidationError(ValueError):
    """Envelope or task failed schema checks."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_message_id() -> str:
    return f"msg-{uuid4().hex[:12]}"


@dataclass
class Artifact:
    name: str
    uri: str = ""
    kind: str = "link"  # link | path | note

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "uri": self.uri, "kind": self.kind}

    @classmethod
    def from_dict(cls, data: Any) -> Artifact:
        if not isinstance(data, dict):
            raise ValidationError("artifact must be an object")
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValidationError("artifact.name is required")
        kind = str(data.get("kind") or "link").strip() or "link"
        if kind not in {"link", "path", "note"}:
            raise ValidationError(f"artifact.kind must be link, path, or note, got {kind!r}")
        uri = str(data.get("uri") or data.get("url") or "").strip()
        return cls(name=name, uri=uri, kind=kind)


@dataclass
class Envelope:
    """One agent-to-agent message."""

    from_agent: str
    to: str
    task_id: str
    ask: str
    status: str = "open"
    due: Optional[str] = None
    artifacts: list[Artifact] = field(default_factory=list)
    id: str = field(default_factory=new_message_id)
    created_at: str = field(default_factory=_utcnow)
    approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    notes: str = ""
    outreach_key: Optional[str] = None

    def validate(self) -> None:
        if not self.from_agent or not AGENT_RE.match(self.from_agent):
            raise ValidationError("from is required and must be a simple agent id")
        if not self.to or not AGENT_RE.match(self.to):
            raise ValidationError("to is required and must be a simple agent id")
        if not self.task_id or not TASK_ID_RE.match(self.task_id):
            raise ValidationError("task_id is required (letters, numbers, dot, underscore, hyphen)")
        if not (self.ask or "").strip():
            raise ValidationError("ask is required")
        if self.status not in STATUSES:
            raise ValidationError(f"status must be one of {', '.join(STATUSES)}")
        if self.due is not None and not DUE_RE.match(self.due):
            raise ValidationError("due must be YYYY-MM-DD")
        if not self.id:
            raise ValidationError("id is required")
        if self.approved and not (self.approved_by or "").strip():
            raise ValidationError("approved messages must name approved_by")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        data: dict[str, Any] = {
            "id": self.id,
            "from": self.from_agent,
            "to": self.to,
            "task_id": self.task_id,
            "status": self.status,
            "ask": self.ask.strip(),
            "due": self.due,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "created_at": self.created_at,
            "approved": self.approved,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "notes": self.notes,
            "outreach_key": self.outreach_key,
        }
        return data

    @classmethod
    def from_dict(cls, data: Any) -> Envelope:
        if not isinstance(data, dict):
            raise ValidationError("envelope must be a JSON object")
        artifacts_raw = data.get("artifacts") or []
        if not isinstance(artifacts_raw, list):
            raise ValidationError("artifacts must be a list")
        approved = data.get("approved", False)
        if not isinstance(approved, bool):
            raise ValidationError("approved must be a boolean")
        due = data.get("due")
        if due == "":
            due = None
        env = cls(
            from_agent=str(data.get("from") or data.get("from_agent") or "").strip(),
            to=str(data.get("to") or "").strip(),
            task_id=str(data.get("task_id") or "").strip(),
            ask=str(data.get("ask") or "").strip(),
            status=str(data.get("status") or "open").strip(),
            due=str(due) if due is not None else None,
            artifacts=[Artifact.from_dict(item) for item in artifacts_raw],
            id=str(data.get("id") or new_message_id()).strip(),
            created_at=str(data.get("created_at") or _utcnow()),
            approved=approved,
            approved_by=(str(data["approved_by"]).strip() if data.get("approved_by") else None),
            approved_at=(str(data["approved_at"]).strip() if data.get("approved_at") else None),
            notes=str(data.get("notes") or ""),
            outreach_key=(str(data["outreach_key"]).strip() if data.get("outreach_key") else None),
        )
        env.validate()
        return env


@dataclass
class Task:
    """Rolled-up view of a task on the shared board."""

    task_id: str
    status: str
    ask: str
    from_agent: str
    to: str
    due: Optional[str] = None
    artifacts: list[Artifact] = field(default_factory=list)
    updated_at: str = field(default_factory=_utcnow)
    message_ids: list[str] = field(default_factory=list)
    approved: bool = False
    approved_by: Optional[str] = None
    outreach_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "ask": self.ask,
            "from": self.from_agent,
            "to": self.to,
            "due": self.due,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "updated_at": self.updated_at,
            "message_ids": list(self.message_ids),
            "approved": self.approved,
            "approved_by": self.approved_by,
            "outreach_key": self.outreach_key,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Task:
        if not isinstance(data, dict):
            raise ValidationError("task must be a JSON object")
        artifacts_raw = data.get("artifacts") or []
        if not isinstance(artifacts_raw, list):
            raise ValidationError("artifacts must be a list")
        return cls(
            task_id=str(data.get("task_id") or "").strip(),
            status=str(data.get("status") or "open").strip(),
            ask=str(data.get("ask") or "").strip(),
            from_agent=str(data.get("from") or data.get("from_agent") or "").strip(),
            to=str(data.get("to") or "").strip(),
            due=data.get("due"),
            artifacts=[Artifact.from_dict(item) for item in artifacts_raw],
            updated_at=str(data.get("updated_at") or _utcnow()),
            message_ids=[str(x) for x in (data.get("message_ids") or [])],
            approved=bool(data.get("approved", False)),
            approved_by=(str(data["approved_by"]).strip() if data.get("approved_by") else None),
            outreach_key=(str(data["outreach_key"]).strip() if data.get("outreach_key") else None),
        )

    @classmethod
    def from_envelope(cls, env: Envelope) -> Task:
        return cls(
            task_id=env.task_id,
            status=env.status,
            ask=env.ask,
            from_agent=env.from_agent,
            to=env.to,
            due=env.due,
            artifacts=list(env.artifacts),
            updated_at=env.created_at,
            message_ids=[env.id],
            approved=env.approved,
            approved_by=env.approved_by,
            outreach_key=env.outreach_key,
        )
