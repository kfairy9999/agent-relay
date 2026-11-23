"""Agent Relay: a shared task board and message protocol for AI agents."""

from .models import (
    STATUSES,
    Artifact,
    Envelope,
    Task,
    ValidationError,
)
from .store import RelayStore
from .board import TaskBoard
from .ledger import DuplicateSendError, SendLedger, SendRecord
from .email_bridge import EmailBridge, ParsedEmail, render_email, parse_email
from .digest import render_digest
from .gate import ApprovalError, approve, require_approval

__version__ = "0.1.0"

__all__ = [
    "STATUSES",
    "Artifact",
    "Envelope",
    "Task",
    "ValidationError",
    "RelayStore",
    "TaskBoard",
    "DuplicateSendError",
    "SendLedger",
    "SendRecord",
    "EmailBridge",
    "ParsedEmail",
    "render_email",
    "parse_email",
    "render_digest",
    "ApprovalError",
    "approve",
    "require_approval",
    "__version__",
]
