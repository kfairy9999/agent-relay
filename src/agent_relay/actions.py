"""High-level operations: approve a message, queue a send to the outbox."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .board import TaskBoard
from .email_bridge import EmailBridge, subject_for
from .gate import approve, require_approval
from .ledger import SendLedger, SendRecord
from .models import Envelope, _utcnow
from .store import RelayStore


@dataclass
class QueuedSend:
    record: SendRecord
    outbox_path: Path
    subject: str


def approve_message(store: RelayStore, message_id: str, by: str) -> Envelope:
    env = store.get_message(message_id)
    approve(env, by=by)
    TaskBoard(store).apply_approval(env)
    return env


def queue_send(store: RelayStore, message_id: str) -> QueuedSend:
    """Write an .eml to the outbox only if approved and not a duplicate.

    This never talks to an SMTP server. A human (or a later tool they run)
    is what actually delivers the file.
    """
    env = store.get_message(message_id)
    require_approval(env)
    agents = store.load_agents()
    bridge = EmailBridge(agents=agents)
    message = bridge.render(env)
    raw = message.as_string()
    body = env.ask
    ledger = SendLedger(store)
    record = ledger.record(
        channel="email",
        recipient=env.to,
        task_id=env.task_id,
        body=body,
        message_id=env.id,
        subject=subject_for(env),
        recorded_at=_utcnow(),
        outreach_key=env.outreach_key,
    )
    path = store.write_outbox(env.id, raw)
    return QueuedSend(record=record, outbox_path=path, subject=message["Subject"] or "")
