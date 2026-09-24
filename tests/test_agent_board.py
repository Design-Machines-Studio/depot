from __future__ import annotations

import concurrent.futures
import json
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "plugins/workflow-kernel/skills/workflow-kernel/references"
sys.path.insert(0, str(REFERENCES))
from workflow_kernel import agent_board, cli  # noqa: E402


FIXTURE = ROOT / "tests/fixtures/agent-board/baseplate-handoff.json"
TIME = "2026-09-24T10:20:00Z"


class AgentBoardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-board-test-")
        self.root = Path(self.temporary.name) / "board"
        self.root.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def handoff(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def reply(self, target, *, message_id=None, body="The cited PR is merged at the exact revision. I checked the current repository state; Governance can proceed with the existing status values."):
        return {
            "schema": "agent-message-v1",
            "id": message_id or uuid.uuid4().hex,
            "source_project": "Design-Machines-Studio/assembly-governance",
            "source_thread": "governance-membership-rules-resumed",
            "destination_project": "Design-Machines-Studio/assembly-baseplate",
            "destination_thread": "baseplate-pr-672",
            "kind": "reply",
            "body": body,
            "source_links": self.handoff()["source_links"],
            "created_at": TIME,
            "reply_to": target,
            "source_verifications": [{
                "url": self.handoff()["source_links"][0]["url"],
                "revision": self.handoff()["source_links"][0]["revision"],
                "checked_at": TIME,
                "outcome": "verified",
            }],
        }

    def test_separate_reader_posts_linked_reply_and_restart_keeps_exchange(self):
        original = agent_board.post(self.root, self.handoff())
        # A second session lists only its destination and reads the source file.
        listing = agent_board.list_messages(self.root, "Design-Machines-Studio/assembly-governance")
        self.assertEqual([original["id"]], [item["id"] for item in listing["messages"]])
        self.assertEqual("unanswered", listing["messages"][0]["state"])
        self.assertFalse(agent_board.list_messages(self.root, "Design-Machines-Studio/other")["messages"])
        read = agent_board.read_message(self.root, original["id"])
        self.assertEqual(original, read["message"])
        response = agent_board.post(self.root, self.reply(original["id"]))
        # A new helper invocation models a fresh process/session.
        resumed = agent_board.read_message(self.root, original["id"])
        self.assertEqual("answered", resumed["state"])
        self.assertEqual(response["id"], resumed["replies"][0]["id"])
        self.assertEqual("verified", resumed["replies"][0]["source_verifications"][0]["outcome"])
        self.assertNotEqual("done", agent_board.list_messages(
            self.root, "Design-Machines-Studio/assembly-governance",
        )["messages"][0]["state"])

    def test_cli_post_list_and_read_commands(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, agent_board.main([
                "--directory", str(self.root), "post", "--input", str(FIXTURE),
            ]))
            posted = json.loads(output.getvalue())
            output.seek(0)
            output.truncate()
            self.assertEqual(0, agent_board.main([
                "--directory", str(self.root), "list", "--destination-project",
                "Design-Machines-Studio/assembly-governance",
            ]))
            self.assertEqual(posted["id"], json.loads(output.getvalue())["messages"][0]["id"])
            output.seek(0)
            output.truncate()
            self.assertEqual(0, agent_board.main([
                "--directory", str(self.root), "read", posted["id"],
            ]))
            self.assertEqual(posted["id"], json.loads(output.getvalue())["message"]["id"])

    def test_launcher_accepts_directory_override_and_help(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, cli.main([
                "agent-board", "--directory", str(self.root), "list",
                "--destination-project", "Design-Machines-Studio/assembly-governance",
            ]))
        self.assertEqual([], json.loads(output.getvalue())["messages"])
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as help_exit:
            cli.main(["agent-board", "--help"])
        self.assertEqual(0, help_exit.exception.code)
        launcher = REFERENCES / "workflow-kernel-launcher.sh"
        launched = subprocess.run(
            [str(launcher), "agent-board", "--directory", str(self.root), "list",
             "--destination-project", "Design-Machines-Studio/assembly-governance"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, launched.returncode, launched.stderr)
        self.assertEqual([], json.loads(launched.stdout)["messages"])

    def test_listing_is_bounded_and_signals_more_and_excludes_other_projects(self):
        first = self.handoff()
        agent_board.post(self.root, first)
        unrelated = self.handoff()
        unrelated.update(id=uuid.uuid4().hex, destination_project="Elsewhere/another-repo")
        agent_board.post(self.root, unrelated)
        third = self.handoff()
        third.update(id=uuid.uuid4().hex, created_at="2026-09-24T10:16:00Z")
        agent_board.post(self.root, third)
        result = agent_board.list_messages(
            self.root, "Design-Machines-Studio/assembly-governance", limit=1,
        )
        self.assertEqual(2, result["matching_count"])
        self.assertEqual(1, result["returned"])
        self.assertTrue(result["more"])
        self.assertEqual(third["id"], result["messages"][0]["id"])

    def test_listing_pages_beyond_the_limit(self):
        for _ in range(101):
            item = self.handoff()
            item["id"] = uuid.uuid4().hex
            agent_board.post(self.root, item)
        first = agent_board.list_messages(
            self.root, "Design-Machines-Studio/assembly-governance", limit=100,
        )
        self.assertTrue(first["more"])
        self.assertEqual(100, first["next_offset"])
        last = agent_board.list_messages(
            self.root, "Design-Machines-Studio/assembly-governance", limit=100,
            offset=first["next_offset"],
        )
        self.assertEqual(1, last["returned"])
        self.assertIsNone(last["next_offset"])
        self.assertEqual(101, len({item["id"] for item in first["messages"] + last["messages"]}))

    def test_timezone_offsets_sort_by_instant(self):
        newer = self.handoff()
        newer.update(id=uuid.uuid4().hex, created_at="2026-09-24T10:00:00Z")
        older = self.handoff()
        older.update(id=uuid.uuid4().hex, created_at="2026-09-24T12:00:00+03:00")
        agent_board.post(self.root, newer)
        agent_board.post(self.root, older)
        first = agent_board.list_messages(
            self.root, "Design-Machines-Studio/assembly-governance", limit=1,
        )
        self.assertEqual(newer["id"], first["messages"][0]["id"])

    def test_timestamp_that_overflows_utc_is_rejected_and_skipped(self):
        invalid = self.handoff()
        invalid.update(id=uuid.uuid4().hex, created_at="0001-01-01T00:00:00+23:59")
        with self.assertRaisesRegex(agent_board.BoardError, "represented in UTC"):
            agent_board.post(self.root, invalid)
        (self.root / f"{invalid['id']}.json").write_text(json.dumps(invalid), encoding="utf-8")
        valid = agent_board.post(self.root, dict(self.handoff(), id=uuid.uuid4().hex))
        listing = agent_board.list_messages(self.root, "Design-Machines-Studio/assembly-governance")
        self.assertEqual(valid["id"], listing["messages"][0]["id"])
        self.assertEqual(invalid["id"] + ".json", listing["diagnostics"][0]["file"])

    def test_superseding_message_is_visible_without_editing_original(self):
        original = agent_board.post(self.root, self.handoff())
        replacement = self.handoff()
        replacement.update(id=uuid.uuid4().hex, created_at=TIME, supersedes_id=original["id"],
                           body="Correction: the PR is still under review; please wait for current checks.")
        agent_board.post(self.root, replacement)
        result = agent_board.read_message(self.root, original["id"])
        self.assertEqual("superseded", result["state"])
        self.assertEqual(replacement["id"], result["superseded_by"][0]["id"])
        self.assertEqual(original["body"], json.loads((self.root / f"{original['id']}.json").read_text())["body"])

    def test_superseding_message_keeps_source_and_destination_thread(self):
        original = agent_board.post(self.root, self.handoff())
        for change in (
            {"source_project": "Other-Team/other-repo"},
            {"destination_thread": "another-thread"},
        ):
            replacement = self.handoff()
            replacement.update(id=uuid.uuid4().hex, supersedes_id=original["id"], **change)
            with self.assertRaisesRegex(agent_board.BoardError, "original source and destination"):
                agent_board.post(self.root, replacement)
        self.assertEqual("unanswered", agent_board.read_message(self.root, original["id"])["state"])

    def test_unavailable_and_conflicting_evidence_remain_claims_after_reply(self):
        original = agent_board.post(self.root, self.handoff())
        response = self.reply(original["id"], body="I checked, but the cited release evidence is currently unavailable.")
        response["source_verifications"][0]["outcome"] = "unavailable"
        agent_board.post(self.root, response)
        conflict = self.reply(
            original["id"], body="A second check conflicts with the release claim.",
        )
        conflict["source_verifications"][0]["outcome"] = "conflict"
        agent_board.post(self.root, conflict)
        result = agent_board.read_message(self.root, original["id"])
        self.assertEqual("answered", result["state"])
        outcomes = {reply["source_verifications"][0]["outcome"] for reply in result["replies"]}
        self.assertEqual({"unavailable", "conflict"}, outcomes)
        self.assertTrue(all("completed" not in reply for reply in result["replies"]))

    def test_two_concurrent_writers_publish_intact_distinct_messages(self):
        docs = []
        for _ in range(2):
            item = self.handoff()
            item["id"] = uuid.uuid4().hex
            docs.append(item)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            saved = list(pool.map(lambda message: agent_board.post(self.root, message), docs))
        self.assertEqual(2, len({item["id"] for item in saved}))
        for item in saved:
            self.assertEqual(item, agent_board.read_message(self.root, item["id"])["message"])

    def test_duplicate_id_does_not_overwrite_existing_message(self):
        original = agent_board.post(self.root, self.handoff())
        duplicate = dict(original, body="Overwrite attempt")
        with self.assertRaisesRegex(agent_board.BoardError, "duplicate message id"):
            agent_board.post(self.root, duplicate)
        self.assertEqual(original, agent_board.read_message(self.root, original["id"])["message"])

    def test_corrupt_file_does_not_hide_valid_entries_and_has_diagnostic(self):
        valid = agent_board.post(self.root, self.handoff())
        broken_id = uuid.uuid4().hex
        (self.root / f"{broken_id}.json").write_text("{partial", encoding="utf-8")
        listing = agent_board.list_messages(self.root, "Design-Machines-Studio/assembly-governance")
        self.assertEqual(valid["id"], listing["messages"][0]["id"])
        self.assertEqual(f"{broken_id}.json", listing["diagnostics"][0]["file"])
        with self.assertRaisesRegex(agent_board.BoardError, "malformed"):
            agent_board.read_message(self.root, broken_id)

    def test_deep_or_oversized_integer_json_does_not_block_board(self):
        valid = agent_board.post(self.root, self.handoff())
        for payload in ("[" * 30000 + "0" + "]" * 30000, "[" + "9" * 5000 + "]"):
            broken_id = uuid.uuid4().hex
            (self.root / f"{broken_id}.json").write_text(payload, encoding="utf-8")
        listing = agent_board.list_messages(self.root, "Design-Machines-Studio/assembly-governance")
        self.assertEqual(valid["id"], listing["messages"][0]["id"])
        self.assertEqual(2, len(listing["diagnostics"]))
        agent_board.post(self.root, dict(self.handoff(), id=uuid.uuid4().hex))

    def test_deep_post_input_returns_a_cli_error_without_traceback(self):
        source = Path(self.temporary.name) / "deep.json"
        source.write_text("[" * 30000 + "0" + "]" * 30000, encoding="utf-8")
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = cli.main([
                "agent-board", "--directory", str(self.root), "post", "--input", str(source),
            ])
        self.assertEqual(2, code)
        self.assertNotIn("Traceback", error.getvalue())
        self.assertEqual([], list(self.root.glob("*.json")))

    def test_only_replies_can_link_an_answer(self):
        original = agent_board.post(self.root, self.handoff())
        question = self.reply(original["id"])
        question["kind"] = "question"
        question.pop("source_verifications")
        with self.assertRaisesRegex(agent_board.BoardError, "only reply"):
            agent_board.post(self.root, question)
        self.assertEqual("unanswered", agent_board.read_message(self.root, original["id"])["state"])

    def test_duplicate_json_fields_are_rejected_and_do_not_publish(self):
        message = json.dumps(self.handoff())
        duplicate = message[:-1] + ', "kind":"reply"}'
        source = Path(self.temporary.name) / "duplicate.json"
        source.write_text(duplicate, encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaisesRegex(
            agent_board.BoardError, "duplicate field",
        ):
            agent_board.main(["--directory", str(self.root), "post", "--input", str(source)])
        self.assertEqual("", output.getvalue())
        self.assertEqual([], list(self.root.glob("*.json")))

    def test_rejects_invalid_references_and_never_creates_missing_root(self):
        message = self.handoff()
        message["kind"] = "reply"
        message["reply_to"] = "22222222222242228222222222222222"
        with self.assertRaisesRegex(agent_board.BoardError, "readable existing message"):
            agent_board.post(self.root, message)
        missing = self.root / "absent"
        with self.assertRaisesRegex(agent_board.BoardError, "does not exist"):
            agent_board.list_messages(missing, "Design-Machines-Studio/assembly-governance")
        self.assertFalse(missing.exists())

    def test_input_cannot_choose_a_path_outside_the_board(self):
        message = self.handoff()
        message["id"] = "../../outside"
        with self.assertRaises(agent_board.BoardError):
            agent_board.post(self.root, message)
        self.assertEqual([], list(Path(self.temporary.name).glob("outside*")))


if __name__ == "__main__":
    unittest.main()
