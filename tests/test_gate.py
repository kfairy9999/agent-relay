import tempfile
import unittest
from pathlib import Path

from agent_relay.actions import approve_message, queue_send
from agent_relay.board import TaskBoard
from agent_relay.gate import ApprovalError, approve, require_approval
from agent_relay.ledger import DuplicateSendError
from agent_relay.models import Envelope
from agent_relay.store import RelayStore


class GateTests(unittest.TestCase):
    def test_require_approval_blocks(self):
        env = Envelope(from_agent="zion", to="kai", task_id="RY-1", ask="send these")
        with self.assertRaises(ApprovalError):
            require_approval(env)

    def test_approve_sets_flag_and_status(self):
        env = Envelope(
            from_agent="zion",
            to="kai",
            task_id="RY-1",
            ask="send these",
            status="need_approval",
        )
        approve(env, by="Kevin Fairley")
        self.assertTrue(env.approved)
        self.assertEqual(env.approved_by, "Kevin Fairley")
        self.assertEqual(env.status, "approved")
        require_approval(env)

    def test_queue_send_requires_approval_and_blocks_duplicates(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = RelayStore(Path(tmp.name))
        env = Envelope(
            from_agent="zion",
            to="kai",
            task_id="RY-36",
            ask="Send the London and Boston agency emails.",
            status="need_approval",
            outreach_key="london-boston-batch",
        )
        TaskBoard(store).post(env)
        with self.assertRaises(ApprovalError):
            queue_send(store, env.id)
        self.assertEqual(list(store.outbox_dir.glob("*.eml")), [])

        approve_message(store, env.id, by="Kevin Fairley")
        queued = queue_send(store, env.id)
        self.assertTrue(queued.outbox_path.exists())
        self.assertIn("[RELAY RY-36]", queued.subject)

        # A second approved message with the same outreach key must not send again.
        env2 = Envelope(
            from_agent="zion",
            to="kai",
            task_id="RY-36",
            ask="Different wording, same outreach.",
            status="need_approval",
            outreach_key="london-boston-batch",
        )
        TaskBoard(store).post(env2)
        approve_message(store, env2.id, by="Kevin Fairley")
        with self.assertRaises(DuplicateSendError):
            queue_send(store, env2.id)
        self.assertEqual(len(list(store.outbox_dir.glob("*.eml"))), 1)


if __name__ == "__main__":
    unittest.main()
