"""Human-approval gate. Nothing is queued for send without an approve flag."""

from __future__ import annotations

from .models import Envelope, ValidationError, _utcnow


class ApprovalError(Exception):
    """A send was attempted without a human approval flag."""


def require_approval(env: Envelope) -> None:
    env.validate()
    if not env.approved:
        raise ApprovalError(
            f"message {env.id} (task {env.task_id}) is not approved; "
            "a human must set the approve flag before it can be sent"
        )
    if not (env.approved_by or "").strip():
        raise ApprovalError(f"message {env.id} is marked approved but has no approved_by")


def approve(env: Envelope, by: str, at: str | None = None) -> Envelope:
    who = (by or "").strip()
    if not who:
        raise ValidationError("approved_by is required")
    env.approved = True
    env.approved_by = who
    env.approved_at = at or _utcnow()
    if env.status in {"open", "in_progress", "need_approval"}:
        env.status = "approved"
    env.validate()
    return env
