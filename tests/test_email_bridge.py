import unittest

from agent_relay.email_bridge import EmailBridge, parse_email, render_email, subject_for
from agent_relay.models import Artifact, Envelope, ValidationError


def sample(**kwargs):
    data = dict(
        from_agent="zion",
        to="kai",
        task_id="RY-36",
        ask="Send the London and Boston agency emails.",
        status="need_approval",
        due="2026-11-23",
        artifacts=[Artifact(name="drafts", uri="https://example.com/drafts", kind="link")],
    )
    data.update(kwargs)
    return Envelope(**data)


class EmailBridgeTests(unittest.TestCase):
    def test_subject_tag(self):
        self.assertIn("[RELAY RY-36][NEED_APPROVAL]", subject_for(sample()))
        open_env = sample(status="open")
        self.assertTrue(subject_for(open_env).startswith("[RELAY RY-36] "))
        self.assertNotIn("[OPEN]", subject_for(open_env))
        long_ask = sample(status="open", ask="Send the emails. Then file the ledger.")
        self.assertEqual(subject_for(long_ask), "[RELAY RY-36] Send the emails.")

    def test_json_block_round_trip(self):
        env = sample()
        raw = render_email(env).as_string()
        parsed = parse_email(raw)
        self.assertEqual(parsed.source, "json_block")
        self.assertEqual(parsed.envelope.task_id, "RY-36")
        self.assertEqual(parsed.envelope.from_agent, "zion")
        self.assertEqual(parsed.envelope.ask, env.ask)
        self.assertEqual(parsed.envelope.artifacts[0].name, "drafts")

    def test_plain_fields_without_json(self):
        raw = (
            "Subject: [RELAY RY-36][IN_PROGRESS] Checking drafts\n"
            "\n"
            "From: zion\n"
            "To: kai\n"
            "Task: RY-36\n"
            "Status: in_progress\n"
            "Due: 2026-11-23\n"
            "Approved: no\n"
            "\n"
            "Ask:\n"
            "Need the Drive link before I can send.\n"
        )
        parsed = parse_email(raw)
        self.assertEqual(parsed.source, "fields")
        self.assertEqual(parsed.envelope.task_id, "RY-36")
        self.assertEqual(parsed.envelope.status, "in_progress")
        self.assertIn("Drive link", parsed.envelope.ask)
        self.assertFalse(parsed.envelope.approved)

    def test_fenced_json(self):
        import json

        env = sample(status="open")
        raw = "Subject: [RELAY RY-36] hello\n\n```json\n" + json.dumps(env.to_dict()) + "\n```\n"
        parsed = parse_email(raw)
        self.assertEqual(parsed.source, "fenced_json")
        self.assertEqual(parsed.envelope.id, env.id)

    def test_resolves_agent_addresses(self):
        agents = {
            "zion": {"name": "ZION", "email": "zion@example.com"},
            "kai": {"name": "Kai", "email": "kai@example.com"},
        }
        msg = EmailBridge(agents=agents).render(sample())
        self.assertIn("zion@example.com", msg["From"])
        self.assertIn("kai@example.com", msg["To"])
        self.assertEqual(msg["X-Agent-Relay-Task"], "RY-36")

    def test_approved_yes_from_fields(self):
        raw = (
            "Subject: [RELAY RY-36][APPROVED] go ahead\n\n"
            "From: kevin\nTo: kai\nTask: RY-36\nApproved: yes\nApproved-By: Kevin Fairley\n\n"
            "Ask:\nSend it.\n"
        )
        env = parse_email(raw).envelope
        self.assertTrue(env.approved)
        self.assertEqual(env.approved_by, "Kevin Fairley")

    def test_empty_rejected(self):
        with self.assertRaises(ValidationError):
            parse_email("hello there, no structure at all")


if __name__ == "__main__":
    unittest.main()
