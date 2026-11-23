import unittest

from agent_relay.models import Artifact, Envelope, ValidationError


class EnvelopeTests(unittest.TestCase):
    def test_round_trip_uses_from_key(self):
        env = Envelope(
            from_agent="zion",
            to="kai",
            task_id="RY-36",
            ask="Send the London and Boston agency emails.",
            status="need_approval",
            due="2026-11-23",
            artifacts=[Artifact(name="drafts", uri="https://example.com/d", kind="link")],
        )
        data = env.to_dict()
        self.assertEqual(data["from"], "zion")
        self.assertNotIn("from_agent", data)
        self.assertEqual(data["task_id"], "RY-36")
        again = Envelope.from_dict(data)
        self.assertEqual(again.from_agent, "zion")
        self.assertEqual(again.artifacts[0].uri, "https://example.com/d")

    def test_accepts_url_alias_on_artifact(self):
        env = Envelope.from_dict(
            {
                "from": "zion",
                "to": "kai",
                "task_id": "RY-1",
                "ask": "Review the doc",
                "artifacts": [{"name": "doc", "url": "https://example.com/doc"}],
            }
        )
        self.assertEqual(env.artifacts[0].uri, "https://example.com/doc")

    def test_rejects_bad_status_and_empty_ask(self):
        with self.assertRaises(ValidationError):
            Envelope(from_agent="zion", to="kai", task_id="RY-1", ask="ok", status="later").validate()
        with self.assertRaises(ValidationError):
            Envelope(from_agent="zion", to="kai", task_id="RY-1", ask="   ").validate()

    def test_rejects_bad_task_id_and_due(self):
        with self.assertRaises(ValidationError):
            Envelope(from_agent="zion", to="kai", task_id="RY 36", ask="x").validate()
        with self.assertRaises(ValidationError):
            Envelope(from_agent="zion", to="kai", task_id="RY-36", ask="x", due="11/23/2026").validate()

    def test_approved_requires_approver(self):
        env = Envelope(from_agent="zion", to="kai", task_id="RY-1", ask="x", approved=True)
        with self.assertRaises(ValidationError):
            env.validate()


if __name__ == "__main__":
    unittest.main()
