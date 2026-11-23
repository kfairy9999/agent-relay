import tempfile
import unittest
from pathlib import Path

from agent_relay.ledger import DuplicateSendError, SendLedger, fingerprint
from agent_relay.store import RelayStore


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = SendLedger(RelayStore(Path(self.tmp.name)))

    def tearDown(self):
        self.tmp.cleanup()

    def _record(self, body="please send the batch", outreach_key=None, recipient="kai"):
        return self.ledger.record(
            channel="email",
            recipient=recipient,
            task_id="RY-36",
            body=body,
            message_id="msg-1",
            subject="[RELAY RY-36] send",
            recorded_at="2026-11-22T00:00:00Z",
            outreach_key=outreach_key,
        )

    def test_blocks_same_body(self):
        self._record("Please send the batch")
        with self.assertRaises(DuplicateSendError):
            self._record("please   send the BATCH")

    def test_allows_different_body(self):
        self._record("first version of the ask")
        second = self._record("a clearly different ask")
        self.assertNotEqual(second.key, fingerprint("email", "kai", "RY-36", "first version of the ask"))

    def test_outreach_key_wins(self):
        self._record("wording A", outreach_key="london-boston-batch")
        with self.assertRaises(DuplicateSendError):
            self.ledger.record(
                channel="email",
                recipient="kai",
                task_id="RY-36",
                body="wording B",
                message_id="msg-2",
                subject="x",
                recorded_at="2026-11-22T01:00:00Z",
                outreach_key="London-Boston-Batch",
            )

    def test_same_key_different_recipient_is_ok(self):
        self._record("same ask", outreach_key="batch-1", recipient="kai")
        rec = self._record("same ask", outreach_key="batch-1", recipient="other")
        self.assertEqual(rec.recipient, "other")
        self.assertEqual(len(self.ledger.all()), 2)


if __name__ == "__main__":
    unittest.main()
