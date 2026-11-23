import tempfile
import unittest
from pathlib import Path

from agent_relay.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = str(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return main(["--data", self.data, *args])

    def test_full_flow(self):
        self.assertEqual(self.run_cli("init"), 0)
        self.assertEqual(
            self.run_cli(
                "message",
                "new",
                "--from",
                "zion",
                "--to",
                "kai",
                "--task-id",
                "RY-36",
                "--ask",
                "Send the London and Boston agency emails.",
                "--status",
                "need_approval",
                "--due",
                "2026-11-23",
                "--outreach-key",
                "london-boston-batch",
                "--artifact",
                "drafts=https://example.com/drafts",
            ),
            0,
        )
        board_out = Path(self.tmp.name)
        # recover message id from the store
        from agent_relay.store import RelayStore

        msg_id = RelayStore(board_out).load_messages()[0].id
        self.assertEqual(self.run_cli("board"), 0)
        self.assertEqual(self.run_cli("digest"), 0)
        self.assertEqual(self.run_cli("send", msg_id), 2)  # not approved
        self.assertEqual(self.run_cli("approve", msg_id, "--by", "Kevin Fairley"), 0)
        self.assertEqual(self.run_cli("send", msg_id), 0)
        self.assertEqual(self.run_cli("send", msg_id), 3)  # duplicate
        self.assertEqual(self.run_cli("ledger"), 0)
        self.assertEqual(self.run_cli("message", "show", msg_id), 0)

        out = Path(self.tmp.name) / "preview.eml"
        self.assertEqual(self.run_cli("email", "render", msg_id, "--out", str(out)), 0)
        self.assertTrue(out.exists())
        self.assertEqual(self.run_cli("email", "parse", str(out)), 0)


if __name__ == "__main__":
    unittest.main()
