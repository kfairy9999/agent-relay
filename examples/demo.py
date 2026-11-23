#!/usr/bin/env python3
"""Walk through a ZION ↔ Kai handoff, Kevin's approval, and a blocked repeat send."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_relay.actions import approve_message, queue_send  # noqa: E402
from agent_relay.board import TaskBoard  # noqa: E402
from agent_relay.digest import render_digest  # noqa: E402
from agent_relay.email_bridge import EmailBridge, parse_email  # noqa: E402
from agent_relay.gate import ApprovalError  # noqa: E402
from agent_relay.ledger import DuplicateSendError  # noqa: E402
from agent_relay.models import Artifact, Envelope  # noqa: E402
from agent_relay.store import RelayStore  # noqa: E402

AGENTS = {
    "zion": {"name": "ZION", "email": "kfairley9999-8h3zwh@mail.grokbot.com"},
    "kai": {"name": "Kai", "email": "info@turfprossolution.com"},
}


def main() -> int:
    data = ROOT / "relay-data" / "demo"
    if data.exists():
        for path in data.rglob("*"):
            if path.is_file():
                path.unlink()
    store = RelayStore(data)
    store.init()
    store.save_agents(AGENTS)
    board = TaskBoard(store)
    bridge = EmailBridge(agents=AGENTS)

    handoff = Envelope(
        from_agent="zion",
        to="kai",
        task_id="RY-36",
        ask=(
            "Please send the London and Boston agency emails. "
            "Use the drafts already prepared. Do not send until Kevin approves."
        ),
        status="need_approval",
        due="2026-11-23",
        artifacts=[Artifact(name="agency-drafts", uri="https://example.com/drafts", kind="link")],
        outreach_key="london-boston-batch",
    )
    board.post(handoff)
    print("1. ZION posted RY-36 to the board.")
    print()
    print(bridge.render(handoff).as_string())
    print()

    try:
        queue_send(store, handoff.id)
        print("ERROR: unapproved send should have failed")
        return 1
    except ApprovalError as exc:
        print(f"2. Send blocked (as designed): {exc}")

    approve_message(store, handoff.id, by="Kevin Fairley")
    queued = queue_send(store, handoff.id)
    print(f"3. Kevin approved. Queued to {queued.outbox_path}")
    print(f"   Subject: {queued.subject}")

    raw = queued.outbox_path.read_text(encoding="utf-8")
    parsed = parse_email(raw)
    print(f"4. Outbox email parses back via {parsed.source}: task {parsed.envelope.task_id}")

    retry = Envelope(
        from_agent="zion",
        to="kai",
        task_id="RY-36",
        ask="Resend the same London and Boston batch, slightly reworded.",
        status="need_approval",
        outreach_key="london-boston-batch",
    )
    board.post(retry)
    approve_message(store, retry.id, by="Kevin Fairley")
    try:
        queue_send(store, retry.id)
        print("ERROR: duplicate send should have failed")
        return 1
    except DuplicateSendError as exc:
        print(f"5. Repeat send blocked by the ledger: {exc}")

    print()
    print(render_digest(board))
    print("Demo complete. Nothing was delivered over the network.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
