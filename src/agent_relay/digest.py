"""Plain-text status digest of the shared task board."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from .board import TaskBoard
from .models import Task

PACIFIC = ZoneInfo("America/Los_Angeles")
STATUS_ORDER = (
    "need_approval",
    "blocked",
    "in_progress",
    "open",
    "approved",
    "done",
    "cancelled",
)


def render_digest(
    board: TaskBoard,
    *,
    as_of: Optional[datetime] = None,
    include_done: bool = True,
) -> str:
    now = as_of or datetime.now(PACIFIC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=PACIFIC)
    else:
        now = now.astimezone(PACIFIC)
    today = now.date()
    tasks = board.list()
    counts = Counter(t.status for t in tasks)
    stamp = now.strftime("%Y-%m-%d %H:%M") + " PT"

    lines = [
        f"# Agent Relay digest — {stamp}",
        "",
        _count_line(counts, len(tasks)),
        "",
    ]
    overdue = [t for t in tasks if _is_overdue(t, today)]
    if overdue:
        lines.append("## Overdue")
        for task in overdue:
            lines.extend(_task_lines(task, overdue_note=True))
        lines.append("")

    for status in STATUS_ORDER:
        group = [t for t in tasks if t.status == status]
        if status == "done" and not include_done:
            continue
        if not group:
            continue
        title = status.replace("_", " ").capitalize()
        lines.append(f"## {title}")
        for task in group:
            lines.extend(_task_lines(task))
        lines.append("")

    if not tasks:
        lines.append("No tasks on the board.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _count_line(counts: Counter, total: int) -> str:
    if total == 0:
        return "0 tasks"
    parts = [f"{counts[s]} {s.replace('_', ' ')}" for s in STATUS_ORDER if counts[s]]
    return f"{total} task{'s' if total != 1 else ''}: " + " · ".join(parts)


def _is_overdue(task: Task, today: date) -> bool:
    if not task.due or task.status in {"done", "cancelled"}:
        return False
    try:
        return date.fromisoformat(task.due) < today
    except ValueError:
        return False


def _task_lines(task: Task, overdue_note: bool = False) -> list[str]:
    due = f"  due {task.due}" if task.due else ""
    flag = "  OVERDUE" if overdue_note else ""
    approved = "  approved" if task.approved else ""
    lines = [
        f"- {task.task_id}  {task.from_agent} → {task.to}{due}{flag}{approved}",
        f"  Ask: {_one_line(task.ask)}",
    ]
    if task.artifacts:
        names = ", ".join(a.name for a in task.artifacts)
        lines.append(f"  Artifacts: {names}")
    return lines


def _one_line(text: str) -> str:
    line = " ".join((text or "").split())
    if len(line) > 160:
        return line[:157] + "..."
    return line
