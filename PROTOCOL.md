# How ZION and Kai should use Agent Relay over email today

This is a one-page working agreement. Paste it into an email and keep it handy. No special software is required on either side: a clearly tagged email is enough. The `agent-relay` tool can also parse and produce the same format.

## Why this exists

ZION and Kai need a shared way to hand off work, avoid sending the same outreach twice, and make sure nothing goes out to a third party until Kevin approves it.

## Addresses

- ZION: kfairley9999-8h3zwh@mail.grokbot.com
- Kai: info@turfprossolution.com
- Approver: Kevin

## Subject line

Always start the subject with a task tag:

```
[RELAY RY-36] Send the London and Boston agency emails
```

If you are asking Kevin to approve a send:

```
[RELAY RY-36][NEED_APPROVAL] Draft ready: London and Boston emails
```

If the work is finished:

```
[RELAY RY-36][DONE] London and Boston emails sent
```

Reply in the same thread and keep the `[RELAY RY-36]` tag in the subject. Use the real task id in place of RY-36.

## Body format

Write in plain English, then include the labeled fields so either agent can parse the message. The JSON block is optional but preferred when the tool is available.

```
From: zion
To: kai
Task: RY-36
Status: need_approval
Due: 2026-11-23
Approved: no

Ask:
Please send the London and Boston agency emails. Use the drafts in the shared folder. Do not send until Kevin approves.

Artifacts:
- london-boston-drafts: https://example.com/drafts

---relay-json---
{ "from": "zion", "to": "kai", "task_id": "RY-36", "status": "need_approval", "ask": "Please send the London and Boston agency emails.", "due": "2026-11-23", "artifacts": [{"name": "london-boston-drafts", "uri": "https://example.com/drafts", "kind": "link"}], "approved": false }
---end-relay-json---
```

If you cannot produce the JSON block, the labeled fields alone are enough.

## Status words (use exactly one)

- `open` — new work, not started
- `in_progress` — someone is on it
- `blocked` — stuck; say why in Ask
- `need_approval` — a draft is ready, waiting for Kevin
- `approved` — Kevin said yes; it is OK to send
- `done` — finished
- `cancelled` — stopped on purpose

## Approval rule (non-negotiable)

Nothing is sent to a third party until Kevin has approved it.

- Agents may draft, review, and email each other freely.
- An outgoing send (for example agency outreach) needs `Approved: yes` and Kevin named as `Approved-By`.
- If a message is not approved, treat it as a draft only.
- After a send, reply in the same thread with `[RELAY RY-36][DONE]`, say what went out, and record it on the send ledger so the same outreach is not sent twice.

Kevin can approve by replying in the thread:

```
Approved: yes
Approved-By: Kevin Fairley
Status: approved
```

Or by running: `agent-relay approve msg-… --by "Kevin Fairley"`

## How a handoff works

1. ZION opens or updates a task (`[RELAY RY-36]`), states the Ask, the Due date, and links any Artifacts.
2. Kai replies in the same thread, keeps the tag, updates Status, and puts questions or results in Ask.
3. When a send is ready, Kai or ZION sets Status to `need_approval` and copies Kevin.
4. Kevin replies `Approved: yes` (or uses the approve command). Only then may the send go out.
5. The sender replies `[RELAY RY-36][DONE]`, notes what went out, and the ledger records it. Do not resend something already on the ledger.

## Do not

- Do not drop the `[RELAY …]` tag.
- Do not send outreach without Kevin's approval.
- Do not resend something already recorded on the ledger.
- Do not put passwords, tokens, keys, or other secrets in these emails.
