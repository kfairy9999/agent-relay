"""No-repeat send ledger. Same outreach cannot be queued twice."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from .store import RelayStore


class DuplicateSendError(Exception):
    """This outreach was already recorded on the ledger."""

    def __init__(self, record: "SendRecord"):
        self.record = record
        super().__init__(
            f"duplicate send blocked: task={record.task_id} recipient={record.recipient} "
            f"recorded_at={record.recorded_at} message_id={record.message_id}"
        )


@dataclass
class SendRecord:
    key: str
    channel: str
    recipient: str
    task_id: str
    message_id: str
    subject: str
    recorded_at: str
    outreach_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "channel": self.channel,
            "recipient": self.recipient,
            "task_id": self.task_id,
            "message_id": self.message_id,
            "subject": self.subject,
            "recorded_at": self.recorded_at,
            "outreach_key": self.outreach_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SendRecord:
        return cls(
            key=str(data["key"]),
            channel=str(data.get("channel") or "email"),
            recipient=str(data.get("recipient") or ""),
            task_id=str(data.get("task_id") or ""),
            message_id=str(data.get("message_id") or ""),
            subject=str(data.get("subject") or ""),
            recorded_at=str(data.get("recorded_at") or ""),
            outreach_key=(str(data["outreach_key"]) if data.get("outreach_key") else None),
        )


def normalize_body(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def fingerprint(
    channel: str,
    recipient: str,
    task_id: str,
    body: str,
    outreach_key: Optional[str] = None,
) -> str:
    """Stable key for a send. An explicit outreach_key wins over body text."""
    if outreach_key:
        material = "\n".join(
            [
                "outreach",
                channel.strip().lower(),
                recipient.strip().lower(),
                outreach_key.strip().lower(),
            ]
        )
    else:
        material = "\n".join(
            [
                channel.strip().lower(),
                recipient.strip().lower(),
                task_id.strip().upper(),
                normalize_body(body),
            ]
        )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class SendLedger:
    def __init__(self, store: RelayStore):
        self.store = store

    def all(self) -> list[SendRecord]:
        return [SendRecord.from_dict(row) for row in self.store.read_jsonl(self.store.ledger_path)]

    def find_duplicate(
        self,
        *,
        channel: str,
        recipient: str,
        task_id: str,
        body: str,
        outreach_key: Optional[str] = None,
    ) -> Optional[SendRecord]:
        key = fingerprint(channel, recipient, task_id, body, outreach_key)
        for record in self.all():
            if record.key == key:
                return record
            if outreach_key and record.outreach_key and record.outreach_key.lower() == outreach_key.lower():
                if record.recipient.lower() == recipient.strip().lower() and record.channel == channel:
                    return record
        return None

    def record(
        self,
        *,
        channel: str,
        recipient: str,
        task_id: str,
        body: str,
        message_id: str,
        subject: str,
        recorded_at: str,
        outreach_key: Optional[str] = None,
    ) -> SendRecord:
        existing = self.find_duplicate(
            channel=channel,
            recipient=recipient,
            task_id=task_id,
            body=body,
            outreach_key=outreach_key,
        )
        if existing:
            raise DuplicateSendError(existing)
        record = SendRecord(
            key=fingerprint(channel, recipient, task_id, body, outreach_key),
            channel=channel,
            recipient=recipient,
            task_id=task_id,
            message_id=message_id,
            subject=subject,
            recorded_at=recorded_at,
            outreach_key=outreach_key,
        )
        self.store.append_jsonl(self.store.ledger_path, record.to_dict())
        return record
