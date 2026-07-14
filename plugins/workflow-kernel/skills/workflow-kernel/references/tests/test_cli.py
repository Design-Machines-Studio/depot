import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests import detail_digest, detail_key_digest
from workflow_kernel import cli
from workflow_kernel.cli import command_append, command_init, command_replay, command_validate
from workflow_kernel.schema import ErrorMessage, InvalidSchemaError, UnsafePayloadError


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).parents[1])
        return subprocess.run([sys.executable, "-m", "workflow_kernel", *args], text=True, capture_output=True, env=env, check=False)

    def install_cached_runtime(self, home, cache, version, main_source=None, *, mtime=None):
        refs = (Path(home) / cache / "plugins/cache/depot/workflow-kernel" /
                version / "skills/workflow-kernel/references")
        if main_source is None:
            refs.mkdir(parents=True)
            if mtime is not None:
                os.utime(refs, (mtime, mtime))
            return refs
        package = refs / "workflow_kernel"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "cli.py").write_text("")
        (package / "__main__.py").write_text(main_source)
        if mtime is not None:
            os.utime(refs, (mtime, mtime))
        return refs

    def run_cache_resolver(self, home, *, cwd=None, **environment):
        skill = Path(__file__).parents[2] / "SKILL.md"
        snippet = skill.read_text().split("```sh\n", 1)[1].split("```", 1)[0]
        env = dict(os.environ, HOME=str(home), **environment)
        return subprocess.run(
            ["zsh", "-c", snippet], cwd=cwd, text=True,
            capture_output=True, env=env, check=False,
        )

    def test_help_lists_commands(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        for command in ("init", "validate", "append", "replay", "status"):
            self.assertIn(command, result.stdout)

    def test_init_append_replay_status_and_safe_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli("init", directory, "--run-id", "run-1", "--occurred-at", "2026-07-14T00:00:00Z").returncode, 0)
            state_path = Path(directory) / "run-state.json"
            self.assertEqual(json.loads(state_path.read_text())["mode"], "shadow")
            event_data = {
                "schema_version": 1, "sequence": 1, "run_id": "run-1", "node_id": None,
                "kind": "run.started", "occurred_at": "2026-07-14T00:00:01Z", "payload": {},
            }
            self.assertEqual(self.run_cli("append", directory, "--event", json.dumps(event_data)).returncode, 0)
            self.assertEqual(self.run_cli("replay", directory).returncode, 0)
            status = self.run_cli("status", directory)
            self.assertEqual(json.loads(status.stdout)["status"], "running")
            bad = self.run_cli("append", directory, "--event", '{"password":"fixture-secret"}')
            self.assertNotEqual(bad.returncode, 0)
            self.assertNotIn("fixture-secret", bad.stderr)

    def test_validate_rejects_missing_empty_and_state_without_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = self.run_cli("validate", directory)
            self.assertNotEqual(missing.returncode, 0)
            Path(directory, "events.jsonl").write_text("")
            empty = self.run_cli("validate", directory)
            self.assertNotEqual(empty.returncode, 0)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli("init", directory, "--run-id", "run-1", "--occurred-at", "2026-07-14T00:00:00Z").returncode, 0)
            Path(directory, "events.jsonl").write_text("")
            result = self.run_cli("validate", directory)
            self.assertNotEqual(result.returncode, 0)

    def test_validate_rejects_dangling_state_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            initialized = self.run_cli(
                "init", directory, "--run-id", "run-1",
                "--occurred-at", "2026-07-14T00:00:00Z",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            state_path = Path(directory) / "run-state.json"
            state_path.unlink()
            state_path.symlink_to("missing-state-target")
            result = self.run_cli("validate", directory)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "corrupt_state")

    def test_append_rejects_dangling_state_symlink_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            initialized = self.run_cli(
                "init", directory, "--run-id", "run-1",
                "--occurred-at", "2026-07-14T00:00:00Z",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            events_path = Path(directory) / "events.jsonl"
            before = events_path.read_bytes()
            state_path = Path(directory) / "run-state.json"
            state_path.unlink()
            state_path.symlink_to("missing-state-target")
            candidate = {
                "schema_version": 1, "sequence": 1, "run_id": "run-1",
                "node_id": None, "kind": "run.started",
                "occurred_at": "2026-07-14T00:00:01Z", "payload": {},
            }
            result = self.run_cli(
                "append", directory, "--event", json.dumps(candidate),
            )
            after = events_path.read_bytes()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "corrupt_state")
        self.assertEqual(after, before)

    def test_init_rejects_dangling_state_before_creating_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_path = root / "run-state.json"
            state_path.symlink_to("missing-state-target")
            result = self.run_cli(
                "init", directory, "--run-id", "run-1",
                "--occurred-at", "2026-07-14T00:00:00Z",
            )
            self.assertFalse((root / "events.jsonl").exists())
            self.assertTrue(state_path.is_symlink())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "corrupt_state")

    def test_init_rejects_dangling_ledger_without_creating_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger_path = root / "events.jsonl"
            ledger_path.symlink_to("missing-ledger-target")
            result = self.run_cli(
                "init", directory, "--run-id", "run-1",
                "--occurred-at", "2026-07-14T00:00:00Z",
            )
            self.assertTrue(ledger_path.is_symlink())
            self.assertFalse((root / "run-state.json").exists())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "corrupt_event")

    def test_init_prepares_state_before_creating_ledger(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch("workflow_kernel.state.MAX_STATE_BYTES", 1):
            with self.assertRaises(UnsafePayloadError):
                command_init(SimpleNamespace(
                    directory=directory, run_id="run-1", mode="shadow",
                    occurred_at="2026-07-14T00:00:00Z",
                ))
            self.assertFalse((Path(directory) / "events.jsonl").exists())

    def test_append_rejects_every_materialized_ledger_mismatch_before_mutation(self):
        mutations = (
            ("ahead", lambda data: data.update(revision=data["revision"] + 1)),
            ("behind", lambda data: data.update(revision=data["revision"] - 1)),
            ("equal-revision-different-content", lambda data: data.update(mode="enforce")),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                initialized = self.run_cli(
                    "init", directory, "--run-id", "run-1",
                    "--occurred-at", "2026-07-14T00:00:00Z",
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                root = Path(directory)
                ledger_path = root / "events.jsonl"
                state_path = root / "run-state.json"
                state = json.loads(state_path.read_text())
                mutate(state)
                state_path.write_text(json.dumps(state, sort_keys=True) + "\n")
                before = ledger_path.read_bytes()
                candidate = {
                    "schema_version": 1, "sequence": 1, "run_id": "run-1",
                    "node_id": None, "kind": "run.started",
                    "occurred_at": "2026-07-14T00:00:01Z", "payload": {},
                }
                result = self.run_cli(
                    "append", directory, "--event", json.dumps(candidate),
                )
                self.assertEqual(ledger_path.read_bytes(), before)
                self.assertNotEqual(result.returncode, 0)
                error = json.loads(result.stderr)["error"]
                self.assertEqual(error["code"], "invalid_schema")
                self.assertEqual(error["message"], "materialized state does not match event ledger")

    def test_append_rebuilds_missing_materialization_from_candidate_state(self):
        with tempfile.TemporaryDirectory() as directory:
            initialized = self.run_cli(
                "init", directory, "--run-id", "run-1",
                "--occurred-at", "2026-07-14T00:00:00Z",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            state_path = Path(directory) / "run-state.json"
            state_path.unlink()
            candidate = {
                "schema_version": 1, "sequence": 1, "run_id": "run-1",
                "node_id": None, "kind": "run.started",
                "occurred_at": "2026-07-14T00:00:01Z", "payload": {},
            }
            appended = self.run_cli(
                "append", directory, "--event", json.dumps(candidate),
            )
            self.assertEqual(appended.returncode, 0, appended.stderr)
            rebuilt = json.loads(state_path.read_text())
        self.assertEqual(rebuilt["revision"], 2)
        self.assertEqual(rebuilt["status"], "running")

    def test_replay_reconciles_every_materialization_direction_to_ledger(self):
        mutations = (
            ("missing", None),
            ("behind", lambda data: data.update(revision=data["revision"] - 1)),
            ("equal-revision-divergent", lambda data: data.update(mode="enforce")),
            ("ahead", lambda data: data.update(revision=data["revision"] + 1)),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                initialized = self.run_cli(
                    "init", directory, "--run-id", "run-1",
                    "--occurred-at", "2026-07-14T00:00:00Z",
                )
                self.assertEqual(initialized.returncode, 0, initialized.stderr)
                state_path = Path(directory) / "run-state.json"
                authoritative = json.loads(state_path.read_text())
                if mutate is None:
                    state_path.unlink()
                else:
                    materialized = dict(authoritative)
                    mutate(materialized)
                    state_path.write_text(json.dumps(materialized, sort_keys=True) + "\n")
                replayed = self.run_cli("replay", directory)
                self.assertEqual(replayed.returncode, 0, replayed.stderr)
                self.assertEqual(json.loads(state_path.read_text()), authoritative)

    def test_non_init_commands_do_not_create_a_missing_run_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing-run"
            result = self.run_cli("validate", missing)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(missing.exists())

    def test_argparse_error_does_not_echo_rejected_value(self):
        sentinel = "NEVER-PRINT-THIS-SECRET"
        result = self.run_cli("init", "/tmp/unused", "--run-id", "run-1",
                              "--occurred-at", "2026-07-14T00:00:00Z", "--mode", sentinel)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(sentinel, result.stderr)
        expected = detail_digest("invalid_argument")
        self.assertEqual(json.loads(result.stderr)["error"]["details"]["reason_code"], expected)

    def test_rejected_event_kind_is_hashed_in_public_error_details(self):
        sentinel = "never-persist-rejected-event-kind"
        digest = detail_digest(sentinel)
        with tempfile.TemporaryDirectory() as directory:
            initialized = self.run_cli(
                "init", directory, "--run-id", "run-1",
                "--occurred-at", "2026-07-14T00:00:00Z",
            )
            self.assertEqual(initialized.returncode, 0)
            event = {
                "schema_version": 1,
                "sequence": 1,
                "run_id": "run-1",
                "node_id": None,
                "kind": sentinel,
                "occurred_at": "2026-07-14T00:00:01Z",
                "payload": {},
            }
            rejected = self.run_cli("append", directory, "--event", json.dumps(event))
        self.assertEqual(rejected.returncode, 2)
        self.assertNotIn(sentinel, rejected.stderr)
        self.assertEqual(json.loads(rejected.stderr)["error"]["details"]["kind"], digest)

    def test_main_uses_base_owned_serializer_for_trusted_subclasses(self):
        sentinel = "never-persist-subclass-serializer"

        class TrustedError(UnsafePayloadError):
            def to_dict(self):
                return {"secret": sentinel}

        error = TrustedError(ErrorMessage.INVALID_STRING_FIELD, {"field": sentinel})
        parsed = SimpleNamespace(handler=mock.Mock(side_effect=error))
        with mock.patch("workflow_kernel.cli.parser") as parser, \
                mock.patch("workflow_kernel.cli._emit") as emit:
            parser.return_value.parse_args.return_value = parsed
            self.assertEqual(cli.main([]), 2)
        emitted = emit.call_args.args[0]
        self.assertEqual(emitted["error"]["code"], "unsafe_payload")
        self.assertNotIn(sentinel, json.dumps(emitted, sort_keys=True))

    def test_main_hashes_unknown_error_detail_keys(self):
        sentinel = "never-persist-cli-detail-key"
        error = UnsafePayloadError(ErrorMessage.INVALID_STRING_FIELD, {sentinel: "value"})
        parsed = SimpleNamespace(handler=mock.Mock(side_effect=error))
        with mock.patch("workflow_kernel.cli.parser") as parser, \
                mock.patch("workflow_kernel.cli._emit") as emit:
            parser.return_value.parse_args.return_value = parsed
            self.assertEqual(cli.main([]), 2)
        emitted = emit.call_args.args[0]
        self.assertIn(detail_key_digest(sentinel), emitted["error"]["details"])
        self.assertNotIn(sentinel, json.dumps(emitted))

    def test_append_normalizes_deeply_nested_json_without_traceback(self):
        nested = "[" * 1_200 + "0" + "]" * 1_200
        result = self.run_cli("append", "/tmp/workflow-kernel-unused", "--event", nested)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "invalid_schema")
        self.assertNotIn("Traceback", result.stderr)

    def test_validate_loads_materialized_state_once_on_mismatch(self):
        materialized = SimpleNamespace(revision=3)
        reconstructed = SimpleNamespace(revision=4)
        events = mock.Mock()
        events.validate.return_value = ((object(),), ())
        states = mock.Mock()
        states.load.return_value = materialized
        args = SimpleNamespace(directory="unused", recovery=False)
        with mock.patch("workflow_kernel.cli._paths", return_value=(mock.Mock(), events, states)), \
                mock.patch("workflow_kernel.cli._coordinated_run", return_value=mock.MagicMock()), \
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine:
            engine.return_value.reconstruct.return_value = reconstructed
            with self.assertRaises(InvalidSchemaError):
                command_validate(args)
        states.load.assert_called_once_with()

    def test_validate_holds_run_lease_across_ledger_and_state_observation(self):
        active = {"lease": False}

        class Lease:
            def __enter__(self):
                active["lease"] = True
                return self

            def __exit__(self, *_):
                active["lease"] = False

        def observed(value):
            if not active["lease"]:
                raise AssertionError("validation observed outside run lease")
            return value

        reconstructed = SimpleNamespace(revision=1)
        events = mock.Mock()
        events.validate.side_effect = lambda **_: observed(((object(),), ()))
        states = mock.Mock()
        states.load.side_effect = lambda: observed(reconstructed)
        with mock.patch("workflow_kernel.cli._paths", return_value=(mock.Mock(), events, states)), \
                mock.patch("workflow_kernel.cli.RunLease", return_value=Lease()), \
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine, \
                mock.patch("workflow_kernel.cli._emit"):
            engine.return_value.reconstruct.return_value = reconstructed
            self.assertEqual(command_validate(SimpleNamespace(directory="unused", recovery=False)), 0)
        self.assertFalse(active["lease"])

    def test_validate_binds_run_directory_before_parent_alias_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            alias = root / "alias"
            for path, run_id in ((first, "run-first"), (second, "run-second")):
                self.assertEqual(self.run_cli(
                    "init", path, "--run-id", run_id,
                    "--occurred-at", "2026-07-14T00:00:00Z",
                ).returncode, 0)
            (second / "events.jsonl").write_text("corrupt\n")
            alias.symlink_to(first, target_is_directory=True)

            original = cli.EventStore.validate

            def retarget_then_validate(store, recovery=False):
                alias.unlink()
                alias.symlink_to(second, target_is_directory=True)
                return original(store, recovery=recovery)

            with mock.patch.object(cli.EventStore, "validate", retarget_then_validate), \
                    mock.patch("workflow_kernel.cli._emit") as emit:
                self.assertEqual(command_validate(
                    SimpleNamespace(directory=alias, recovery=False),
                ), 0)
            replayed = original(cli._paths(first)[1], recovery=False)[0]
            self.assertEqual(replayed[0].run_id, "run-first")
            self.assertEqual(emit.call_args.args[0]["event_count"], 1)

    def test_path_factory_binds_event_and_state_stores_from_one_root_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            alias = root / "alias"
            alias.symlink_to(first, target_is_directory=True)
            original = cli.StateStore

            def retarget_after_state(path):
                state = original(path)
                alias.unlink()
                alias.symlink_to(second, target_is_directory=True)
                return state

            with mock.patch("workflow_kernel.cli.StateStore", side_effect=retarget_after_state):
                _, events, states = cli._paths(alias)
            self.assertEqual(events.state_path, states.path)

    def test_documented_cache_resolver_is_quiet_with_only_codex_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            self.install_cached_runtime(
                directory, ".codex", "0.1.0", "print('codex-only-runtime')\n",
            )
            caller = Path(directory) / "caller"
            conflicting = caller / "workflow_kernel"
            conflicting.mkdir(parents=True)
            (conflicting / "__init__.py").write_text("")
            (conflicting / "__main__.py").write_text("print('caller-runtime')\n")
            result = self.run_cache_resolver(
                directory, cwd=caller, PYTHONPATH=str(caller),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("codex-only-runtime", result.stdout)
        self.assertNotIn("caller-runtime", result.stdout)

    def test_documented_cache_resolver_skips_incomplete_newer_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            self.install_cached_runtime(directory, ".claude", "9.9.9")
            self.install_cached_runtime(
                directory, ".codex", "0.1.0", "print('fallback-runtime')\n",
            )
            result = self.run_cache_resolver(directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("fallback-runtime", result.stdout)

    def test_documented_cache_resolver_falls_through_unimportable_candidate_in_one_root(self):
        with tempfile.TemporaryDirectory() as directory:
            self.install_cached_runtime(
                directory, ".claude", "9.9.9", "raise RuntimeError('broken')\n",
                mtime=200,
            )
            self.install_cached_runtime(
                directory, ".claude", "0.1.0", "print('older-viable-runtime')\n",
                mtime=100,
            )
            result = self.run_cache_resolver(directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("older-viable-runtime", result.stdout)

    def test_documented_cache_resolver_prioritizes_valid_claude_over_newer_codex(self):
        with tempfile.TemporaryDirectory() as directory:
            self.install_cached_runtime(
                directory, ".claude", "0.1.0", "print('claude-priority-runtime')\n",
                mtime=100,
            )
            self.install_cached_runtime(
                directory, ".codex", "9.9.9", "print('codex-newer-runtime')\n",
                mtime=200,
            )
            result = self.run_cache_resolver(directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("claude-priority-runtime", result.stdout)
        self.assertNotIn("codex-newer-runtime", result.stdout)

    def test_documented_cache_resolver_quietly_rejects_broken_main(self):
        with tempfile.TemporaryDirectory() as directory:
            self.install_cached_runtime(
                directory, ".claude", "9.9.9",
                "raise RuntimeError('broken-main')\n",
            )
            result = self.run_cache_resolver(directory)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime not found", result.stderr)
        self.assertNotIn("broken-main", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_documented_cache_resolver_falls_from_broken_claude_to_codex(self):
        with tempfile.TemporaryDirectory() as directory:
            self.install_cached_runtime(
                directory, ".claude", "9.9.9",
                "raise RuntimeError('broken-claude')\n",
            )
            self.install_cached_runtime(
                directory, ".codex", "0.1.0",
                "print('codex-fallback-runtime')\n",
            )
            result = self.run_cache_resolver(directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("codex-fallback-runtime", result.stdout)

    def test_documented_contract_names_cooperating_writer_and_lookahead_boundaries(self):
        skill = (Path(__file__).parents[2] / "SKILL.md").read_text()
        plan = (Path(__file__).parents[6] / "plans/ai-developer-workflow-kernel/plan.html").read_text()
        for document in (skill, plan):
            self.assertIn("cooperating writers", document)
            self.assertIn("non-cooperating filesystem mutation", document)
            self.assertNotIn("interlopers are never overwritten", document)
            self.assertIn("verified absence preflight", document)
            self.assertIn("exactly matches the replay-derived state", document)
            self.assertIn("lease-protected authoritative replacement", document)
            self.assertIn("ordinary publication rejects backward revisions", document)
            self.assertIn("one public publication path", document)
            self.assertIn("private ledger-derived prepared issuance", document)
            self.assertNotIn("StateStore.reconcile", document)
        self.assertIn("one lookahead item", skill)
        self.assertIn("MAX_RECONSTRUCTION_WORK", skill)
        self.assertIn("event payload snapshot", skill)
        self.assertIn("scalar event snapshot", skill)
        self.assertIn("trusted node updates", skill)

    def test_replay_holds_run_lease_across_observation_and_publication(self):
        active = {"lease": False}

        class ObservedPath:
            def exists(self):
                self.assert_active()
                return True

            @staticmethod
            def assert_active():
                if not active["lease"]:
                    raise AssertionError("state observed outside run lease")

        class Lease:
            def __enter__(self):
                active["lease"] = True
                return self

            def __exit__(self, *_):
                active["lease"] = False

        state = mock.Mock(run_id="run-1", revision=1)
        state.status.value = "planned"
        events = mock.Mock()
        events.replay.side_effect = lambda: (ObservedPath.assert_active(), (object(),))[1]
        states = mock.Mock(path=ObservedPath())
        states.load.side_effect = lambda: (ObservedPath.assert_active(), state)[1]
        states.write.side_effect = lambda *_args, **_kwargs: (
            ObservedPath.assert_active(), {"directory_fsync": "completed"}
        )[1]
        prepared = object()
        with mock.patch("workflow_kernel.cli._paths", return_value=(mock.Mock(), events, states)), \
                mock.patch("workflow_kernel.cli.RunLease", return_value=Lease()), \
                mock.patch("workflow_kernel.cli._prepare_replay_state", return_value=prepared) as prepare_replay, \
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine, \
                mock.patch("workflow_kernel.cli._emit"):
            engine.return_value.reconstruct.return_value = state
            self.assertEqual(command_replay(SimpleNamespace(directory="unused")), 0)
        self.assertFalse(active["lease"])
        prepare_replay.assert_called_once_with(states, state)
        states.prepare.assert_not_called()
        states.publish.assert_called_once_with(
            prepared, state.revision, lease=mock.ANY,
        )
        states.write.assert_not_called()

    def test_append_observes_state_before_publishing_event(self):
        order = []
        event_data = {
            "schema_version": 1, "sequence": 1, "run_id": "run-1", "node_id": None,
            "kind": "run.started", "occurred_at": "2026-07-14T00:00:01Z", "payload": {},
        }
        events = mock.Mock()
        events.validate.return_value = ((object(),), ())
        events.append.side_effect = lambda *_args, **_kwargs: order.append("event")
        current = mock.Mock(revision=1)
        states = mock.Mock()
        states.load.side_effect = lambda: (order.append("state"), current)[1]
        prepared = object()
        states.prepare.side_effect = lambda *_: (order.append("prepare"), prepared)[1]
        states.publish.side_effect = lambda *_args, **_kwargs: (
            order.append("publish"), {"directory_fsync": "completed"}
        )[1]
        next_state = mock.Mock(revision=2)
        next_state.status.value = "running"
        coordinator = mock.MagicMock()
        coordinator.__enter__.return_value = object()
        with mock.patch("workflow_kernel.cli._paths", return_value=(mock.Mock(), events, states)), \
                mock.patch("workflow_kernel.cli._coordinated_run", return_value=coordinator), \
                mock.patch("workflow_kernel.cli.TransitionEngine") as engine, \
                mock.patch("workflow_kernel.cli._emit"):
            engine.return_value.reconstruct.return_value = current
            engine.return_value.apply.return_value = next_state
            self.assertEqual(command_append(SimpleNamespace(directory="unused", event=json.dumps(event_data))), 0)
        engine.assert_called_once_with()
        self.assertEqual(order, ["state", "prepare", "event", "publish"])
        self.assertIs(events.append.call_args.kwargs["lease"], coordinator.__enter__.return_value)
        states.publish.assert_called_once_with(prepared, 1, lease=coordinator.__enter__.return_value)
        states.write.assert_not_called()

    def test_append_state_prepare_preserves_prior_ledger_and_state(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch("workflow_kernel.cli._emit"):
            command_init(SimpleNamespace(directory=directory, run_id="run-1", mode="shadow",
                                         occurred_at="2026-07-14T00:00:00Z"))
            events_path = Path(directory) / "events.jsonl"
            state_path = Path(directory) / "run-state.json"
            before_events = events_path.read_bytes()
            before_state = state_path.read_bytes()
            event_data = {
                "schema_version": 1, "sequence": 1, "run_id": "run-1", "node_id": None,
                "kind": "evidence.recorded", "occurred_at": "2026-07-14T00:00:01Z",
                "payload": {"evidence": ["x" * 256]},
            }
            with mock.patch("workflow_kernel.state.MAX_STATE_BYTES", len(before_state) + 16):
                with self.assertRaises(UnsafePayloadError):
                    command_append(SimpleNamespace(directory=directory, event=json.dumps(event_data)))
            self.assertEqual(events_path.read_bytes(), before_events)
            self.assertEqual(state_path.read_bytes(), before_state)


if __name__ == "__main__":
    unittest.main()
