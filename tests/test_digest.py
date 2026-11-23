import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agent_relay.board import TaskBoard
from agent_relay.digest import render_digest
from agent_relay.models import Envelope
from agent_relay.store import RelayStore

PT = ZoneInfo("America/Los_Angeles")


class DigestTests(unittest.TestCase):
    def test_groups_and_flags_overdue(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        board = TaskBoard(RelayStore(Path(tmp.name)))
        board.post(
            Envelope(
                from_agent="zion",
                to="kai",
                task_id="RY-10",
                ask="Old item still open",
                due="2026-11-01",
            )
        )
        board.post(
            Envelope(
                from_agent="zion",
                to="kai",
                task_id="RY-36",
                ask="Send London and Boston emails",
                status="need_approval",
                due="2026-11-23",
            )
        )
        text = render_digest(board, as_of=datetime(2026, 11, 22, 16, 20, tzinfo=PT))
        self.assertIn("2026-11-22 16:20 PT", text)
        self.assertIn("2 tasks", text)
        self.assertIn("## Overdue", text)
        self.assertIn("RY-10", text)
        self.assertIn("OVERDUE", text)
        self.assertIn("## Need approval", text)
        self.assertIn("RY-36", text)


if __name__ == "__main__":
    unittest.main()
