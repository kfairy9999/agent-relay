import tempfile
import unittest
from pathlib import Path

from agent_relay.board import TaskBoard
from agent_relay.models import Envelope
from agent_relay.store import RelayStore


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = RelayStore(Path(self.tmp.name))
        self.board = TaskBoard(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_post_creates_and_merges(self):
        first = Envelope(from_agent="zion", to="kai", task_id="RY-36", ask="Draft the emails", due="2026-11-23")
        self.board.post(first)
        second = Envelope(
            from_agent="kai",
            to="zion",
            task_id="RY-36",
            ask="Drafts are ready for review",
            status="need_approval",
        )
        task = self.board.post(second)
        self.assertEqual(task.status, "need_approval")
        self.assertEqual(task.to, "zion")
        self.assertEqual(task.due, "2026-11-23")
        self.assertEqual(task.message_ids, [first.id, second.id])
        self.assertEqual(len(self.board.list()), 1)
        self.assertEqual(self.board.list(status="need_approval")[0].task_id, "RY-36")

    def test_unknown_task(self):
        with self.assertRaises(KeyError):
            self.board.get("NOPE")


if __name__ == "__main__":
    unittest.main()
