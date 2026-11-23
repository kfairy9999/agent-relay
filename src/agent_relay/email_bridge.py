"""Turn envelopes into plain email and back.

Subject tags look like ``[RELAY RY-36]`` or ``[RELAY RY-36][NEED_APPROVAL]``.
The body is readable by a person and also carries a JSON envelope block.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from email.message import EmailMessage
from email.parser import Parser
from email.policy import default as email_policy
from typing import Optional

from .models import Artifact, Envelope, ValidationError

SUBJECT_RE = re.compile(
    r"\[RELAY\s+([A-Za-z0-9][A-Za-z0-9._-]*)\](?:\[([A-Za-z0-9_]+)\])?",
    re.IGNORECASE,
)
JSON_BLOCK_RE = re.compile(
    r"---relay-json---\s*(.*?)\s*---end-relay-json---",
    re.DOTALL | re.IGNORECASE,
)
FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL,
)
FIELD_RE = re.compile(
    r"^(From|To|Task|Status|Due|Approved|Approved-By|Approved-At|Outreach-Key|Notes):\s*(.*)$",
    re.IGNORECASE,
)


@dataclass
class ParsedEmail:
    envelope: Envelope
    subject: str
    source: str  # json_block | fenced_json | fields | subject_only


def subject_for(env: Envelope, title: Optional[str] = None) -> str:
    tag = f"[RELAY {env.task_id}]"
    if env.status and env.status != "open":
        tag += f"[{env.status.upper()}]"
    summary = (title or env.ask).strip().splitlines()[0]
    if not title:
        for sep in (". ", "? ", "! "):
            if sep in summary:
                summary = summary.split(sep, 1)[0] + sep.strip()
                break
    if len(summary) > 80:
        summary = summary[:77] + "..."
    return f"{tag} {summary}".strip()


def render_body(env: Envelope) -> str:
    data = env.to_dict()
    lines = [
        "Agent Relay message",
        "",
        f"From: {env.from_agent}",
        f"To: {env.to}",
        f"Task: {env.task_id}",
        f"Status: {env.status}",
        f"Due: {env.due or ''}",
        f"Approved: {'yes' if env.approved else 'no'}",
    ]
    if env.approved_by:
        lines.append(f"Approved-By: {env.approved_by}")
    if env.approved_at:
        lines.append(f"Approved-At: {env.approved_at}")
    if env.outreach_key:
        lines.append(f"Outreach-Key: {env.outreach_key}")
    lines.extend(["", "Ask:", env.ask.strip(), ""])
    if env.artifacts:
        lines.append("Artifacts:")
        for art in env.artifacts:
            extra = f": {art.uri}" if art.uri else ""
            lines.append(f"- {art.name}{extra}")
        lines.append("")
    if env.notes.strip():
        lines.extend(["Notes:", env.notes.strip(), ""])
    lines.extend(
        [
            "---relay-json---",
            json.dumps(data, indent=2, ensure_ascii=False),
            "---end-relay-json---",
            "",
        ]
    )
    return "\n".join(lines)


def render_email(
    env: Envelope,
    *,
    agents: Optional[dict[str, dict[str, str]]] = None,
    title: Optional[str] = None,
) -> EmailMessage:
    env.validate()
    agents = agents or {}
    msg = EmailMessage()
    msg["Subject"] = subject_for(env, title)
    from_addr = _address(env.from_agent, agents)
    to_addr = _address(env.to, agents)
    if from_addr:
        msg["From"] = from_addr
    if to_addr:
        msg["To"] = to_addr
    msg["X-Agent-Relay-Task"] = env.task_id
    msg["X-Agent-Relay-Message-Id"] = env.id
    msg["X-Agent-Relay-Approved"] = "yes" if env.approved else "no"
    msg.set_content(render_body(env))
    return msg


def parse_email(raw: str) -> ParsedEmail:
    """Parse a raw RFC 822 message or a bare body with a relay subject/fields."""
    if not (raw or "").strip():
        raise ValidationError("email is empty")
    parsed = Parser(policy=email_policy).parsestr(raw)
    subject = parsed.get("Subject") or ""
    body = _plain_body(parsed, raw)
    task_from_subject, status_from_subject = _subject_parts(subject)

    source = "fields"
    data: Optional[dict] = None
    block = JSON_BLOCK_RE.search(body)
    if block:
        data = _load_json(block.group(1))
        source = "json_block"
    else:
        fenced = FENCED_JSON_RE.search(body)
        if fenced:
            data = _load_json(fenced.group(1))
            source = "fenced_json"

    if data is not None:
        if task_from_subject and not data.get("task_id"):
            data["task_id"] = task_from_subject
        if status_from_subject and not data.get("status"):
            data["status"] = status_from_subject
        return ParsedEmail(envelope=Envelope.from_dict(data), subject=subject, source=source)

    fields = _parse_fields(body)
    if task_from_subject and "task_id" not in fields:
        fields["task_id"] = task_from_subject
    if status_from_subject and "status" not in fields:
        fields["status"] = status_from_subject
    if "ask" not in fields:
        ask = _ask_from_body(body)
        if ask:
            fields["ask"] = ask
    if fields.get("from") and fields.get("to") and fields.get("task_id") and fields.get("ask"):
        return ParsedEmail(envelope=Envelope.from_dict(fields), subject=subject, source="fields")

    raise ValidationError(
        "could not parse a relay envelope: need a ---relay-json--- block "
        "or From/To/Task/Ask fields (and a [RELAY TASK-ID] subject helps)"
    )


def _subject_parts(subject: str) -> tuple[Optional[str], Optional[str]]:
    match = SUBJECT_RE.search(subject or "")
    if not match:
        return None, None
    task_id = match.group(1)
    status = match.group(2)
    if status:
        status = status.lower()
    return task_id, status


def _address(agent_id: str, agents: dict[str, dict[str, str]]) -> str:
    info = agents.get(agent_id.lower()) or {}
    email = (info.get("email") or "").strip()
    name = (info.get("name") or agent_id).strip()
    if email:
        return f"{name} <{email}>"
    return ""


def _plain_body(parsed: EmailMessage, raw: str) -> str:
    if parsed.get_content_type() == "text/plain" or parsed.is_multipart() or parsed.get("Subject"):
        try:
            content = parsed.get_body(preferencelist=("plain", "html"))
            if content is not None:
                text = content.get_content()
                if content.get_content_type() == "text/html":
                    text = _strip_html(text)
                return text or ""
        except Exception:
            pass
        payload = parsed.get_payload()
        if isinstance(payload, str) and (parsed.get("Subject") or ":" in raw[:200]):
            # Might be a full message whose body is the payload.
            return payload
    # Bare body pasted without headers.
    return raw


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)</p>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"[ \t]+\n", "\n", text)


def _load_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"relay JSON is not valid: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError("relay JSON must be an object")
    return data


def _parse_yes_no(value: str) -> Optional[bool]:
    lowered = value.strip().lower()
    if lowered in {"yes", "true", "y", "1"}:
        return True
    if lowered in {"no", "false", "n", "0"}:
        return False
    return None


def _parse_fields(body: str) -> dict:
    fields: dict = {}
    artifacts: list[dict] = []
    mode = None
    ask_lines: list[str] = []
    notes_lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        match = FIELD_RE.match(line)
        if match:
            mode = None
            key = match.group(1).lower()
            value = match.group(2).strip()
            if key == "task":
                fields["task_id"] = value
            elif key == "from":
                fields["from"] = value
            elif key == "to":
                fields["to"] = value
            elif key == "status":
                fields["status"] = value.lower()
            elif key == "due":
                fields["due"] = value or None
            elif key == "approved":
                parsed = _parse_yes_no(value)
                if parsed is not None:
                    fields["approved"] = parsed
            elif key == "approved-by":
                fields["approved_by"] = value
            elif key == "approved-at":
                fields["approved_at"] = value
            elif key == "outreach-key":
                fields["outreach_key"] = value
            elif key == "notes":
                mode = "notes"
                if value:
                    notes_lines.append(value)
            continue
        if re.match(r"^Ask:\s*$", line, re.IGNORECASE):
            mode = "ask"
            continue
        if re.match(r"^Artifacts:\s*$", line, re.IGNORECASE):
            mode = "artifacts"
            continue
        if re.match(r"^Notes:\s*$", line, re.IGNORECASE):
            mode = "notes"
            continue
        if line.strip() in {"---relay-json---", "```", "```json"} or line.strip().startswith("---end"):
            mode = None
            continue
        if mode == "ask":
            ask_lines.append(line)
        elif mode == "notes":
            notes_lines.append(line)
        elif mode == "artifacts":
            art = _parse_artifact_line(line)
            if art:
                artifacts.append(art)

    # From/To may be "Name <email>"; prefer a leading bare token if it looks like an id.
    for key in ("from", "to"):
        if key in fields:
            fields[key] = _agent_token(fields[key])
    if ask_lines:
        fields["ask"] = "\n".join(ask_lines).strip()
    if notes_lines:
        fields["notes"] = "\n".join(notes_lines).strip()
    if artifacts:
        fields["artifacts"] = artifacts
    return fields


def _agent_token(value: str) -> str:
    value = (value or "").strip()
    if "<" in value and value.endswith(">"):
        name = value.split("<", 1)[0].strip()
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", name):
            return name
        email = value.split("<", 1)[1].rstrip(">")
        return email.split("@")[0]
    if re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", value):
        return value
    if "@" in value:
        return value.split("@")[0]
    return value.split()[0] if value.split() else value


def _parse_artifact_line(line: str) -> Optional[dict]:
    text = line.strip()
    if text.startswith(("- ", "* ")):
        text = text[2:].strip()
    if not text:
        return None
    if ":" in text:
        name, uri = text.split(":", 1)
        return {"name": name.strip(), "uri": uri.strip(), "kind": "link" if "://" in uri else "path"}
    return {"name": text, "uri": "", "kind": "note"}


def _ask_from_body(body: str) -> str:
    # Last-ditch: first non-header paragraph after a subject-like first line.
    lines = [ln.rstrip() for ln in body.splitlines()]
    useful = [ln for ln in lines if ln.strip() and not FIELD_RE.match(ln) and not ln.startswith("[RELAY")]
    return "\n".join(useful).strip()


class EmailBridge:
    """Parse and produce relay emails, optionally resolving agent addresses."""

    def __init__(self, agents: Optional[dict[str, dict[str, str]]] = None):
        self.agents = agents or {}

    def render(self, env: Envelope, title: Optional[str] = None) -> EmailMessage:
        return render_email(env, agents=self.agents, title=title)

    def parse(self, raw: str) -> ParsedEmail:
        return parse_email(raw)
