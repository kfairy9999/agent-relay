"""Command-line interface for Agent Relay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .actions import approve_message, queue_send
from .board import TaskBoard
from .digest import render_digest
from .email_bridge import EmailBridge
from .gate import ApprovalError
from .ledger import DuplicateSendError, SendLedger
from .models import Artifact, Envelope, ValidationError
from .store import RelayStore

DEFAULT_DATA = Path("relay-data")


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    data = Path(args.data) if getattr(args, "data", None) else DEFAULT_DATA
    try:
        return args.func(args, data)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ApprovalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except DuplicateSendError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-relay",
        description="Shared task board and email protocol for AI agents.",
    )
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="data directory (default: ./relay-data)")
    parser.add_argument("--version", action="version", version=f"agent-relay {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create the data directory")
    p_init.set_defaults(func=cmd_init)

    p_new = sub.add_parser("message", help="create or show a message")
    msg_sub = p_new.add_subparsers(dest="message_cmd", required=True)
    p_msg_new = msg_sub.add_parser("new", help="post a new envelope to the board")
    p_msg_new.add_argument("--from", dest="from_agent", required=True)
    p_msg_new.add_argument("--to", required=True)
    p_msg_new.add_argument("--task-id", required=True)
    p_msg_new.add_argument("--ask", required=True)
    p_msg_new.add_argument("--status", default="open")
    p_msg_new.add_argument("--due", default=None, help="YYYY-MM-DD")
    p_msg_new.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="name=uri (repeatable)",
    )
    p_msg_new.add_argument("--notes", default="")
    p_msg_new.add_argument("--outreach-key", default=None)
    p_msg_new.set_defaults(func=cmd_message_new)

    p_msg_show = msg_sub.add_parser("show", help="print one message as JSON")
    p_msg_show.add_argument("message_id")
    p_msg_show.set_defaults(func=cmd_message_show)

    p_board = sub.add_parser("board", help="list tasks on the board")
    p_board.add_argument("--status", default=None)
    p_board.add_argument("--json", action="store_true", dest="as_json")
    p_board.set_defaults(func=cmd_board)

    p_approve = sub.add_parser("approve", help="human-approve a message so it can be sent")
    p_approve.add_argument("message_id")
    p_approve.add_argument("--by", required=True, help="name of the human approver")
    p_approve.set_defaults(func=cmd_approve)

    p_email = sub.add_parser("email", help="render or parse relay email")
    email_sub = p_email.add_subparsers(dest="email_cmd", required=True)
    p_render = email_sub.add_parser("render", help="write a .eml (does not send)")
    p_render.add_argument("message_id")
    p_render.add_argument("--out", default=None, help="output path (default: stdout)")
    p_render.set_defaults(func=cmd_email_render)
    p_parse = email_sub.add_parser("parse", help="parse a .eml or text file")
    p_parse.add_argument("path")
    p_parse.set_defaults(func=cmd_email_parse)

    p_send = sub.add_parser(
        "send",
        help="queue an approved message to the outbox (never SMTP; blocked if unapproved or duplicate)",
    )
    p_send.add_argument("message_id")
    p_send.set_defaults(func=cmd_send)

    p_digest = sub.add_parser("digest", help="print a status digest")
    p_digest.add_argument("--no-done", action="store_true")
    p_digest.set_defaults(func=cmd_digest)

    p_ledger = sub.add_parser("ledger", help="show the no-repeat send ledger")
    p_ledger.set_defaults(func=cmd_ledger)

    return parser


def cmd_init(args: argparse.Namespace, data: Path) -> int:
    store = RelayStore(data)
    store.init()
    print(f"initialized {data.resolve()}")
    return 0


def cmd_message_new(args: argparse.Namespace, data: Path) -> int:
    store = RelayStore(data)
    store.init()
    artifacts = [_parse_artifact(item) for item in args.artifact]
    env = Envelope(
        from_agent=args.from_agent,
        to=args.to,
        task_id=args.task_id,
        ask=args.ask,
        status=args.status,
        due=args.due,
        artifacts=artifacts,
        notes=args.notes,
        outreach_key=args.outreach_key,
    )
    task = TaskBoard(store).post(env)
    print(f"posted {env.id}  task {task.task_id}  status {task.status}")
    return 0


def cmd_message_show(args: argparse.Namespace, data: Path) -> int:
    env = RelayStore(data).get_message(args.message_id)
    print(json.dumps(env.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_board(args: argparse.Namespace, data: Path) -> int:
    tasks = TaskBoard(RelayStore(data)).list(status=args.status)
    if args.as_json:
        print(json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False))
        return 0
    if not tasks:
        print("board is empty")
        return 0
    width = max(len(t.task_id) for t in tasks)
    for task in tasks:
        due = task.due or "-"
        flag = " approved" if task.approved else ""
        print(
            f"{task.task_id.ljust(width)}  {task.status:<14}  {task.from_agent} → {task.to}  due {due}{flag}"
        )
        print(f"  { ' '.join(task.ask.split())[:120]}")
    return 0


def cmd_approve(args: argparse.Namespace, data: Path) -> int:
    env = approve_message(RelayStore(data), args.message_id, by=args.by)
    print(f"approved {env.id}  task {env.task_id}  by {env.approved_by}  at {env.approved_at}")
    return 0


def cmd_email_render(args: argparse.Namespace, data: Path) -> int:
    store = RelayStore(data)
    env = store.get_message(args.message_id)
    raw = EmailBridge(agents=store.load_agents()).render(env).as_string()
    if args.out:
        Path(args.out).write_text(raw, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(raw, end="" if raw.endswith("\n") else "\n")
    return 0


def cmd_email_parse(args: argparse.Namespace, data: Path) -> int:
    raw = Path(args.path).read_text(encoding="utf-8")
    parsed = EmailBridge().parse(raw)
    print(f"# parsed via {parsed.source}  subject: {parsed.subject}")
    print(json.dumps(parsed.envelope.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_send(args: argparse.Namespace, data: Path) -> int:
    queued = queue_send(RelayStore(data), args.message_id)
    print(
        f"queued {queued.record.message_id}  task {queued.record.task_id}  "
        f"to {queued.record.recipient}  outbox {queued.outbox_path}"
    )
    print(f"subject: {queued.subject}")
    return 0


def cmd_digest(args: argparse.Namespace, data: Path) -> int:
    text = render_digest(TaskBoard(RelayStore(data)), include_done=not args.no_done)
    print(text, end="")
    return 0


def cmd_ledger(args: argparse.Namespace, data: Path) -> int:
    records = SendLedger(RelayStore(data)).all()
    if not records:
        print("ledger is empty")
        return 0
    for rec in records:
        key = rec.outreach_key or rec.key[:12]
        print(
            f"{rec.recorded_at}  {rec.task_id}  {rec.recipient}  "
            f"msg {rec.message_id}  key {key}"
        )
    return 0


def _parse_artifact(spec: str) -> Artifact:
    if "=" in spec:
        name, uri = spec.split("=", 1)
    elif ":" in spec and not spec.startswith("http"):
        name, uri = spec.split(":", 1)
    else:
        name, uri = spec, ""
    name, uri = name.strip(), uri.strip()
    kind = "link" if "://" in uri else ("path" if uri else "note")
    return Artifact(name=name, uri=uri, kind=kind)
