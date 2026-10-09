"""SYNTHETIC UNIT FIXTURES ONLY: never native participant or live review proof.

These inert event excerpts are authored test data. They contain no copied host
trace, encrypted assignment, router receipt, or provider-served identity.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest import mock

from workflow_kernel.dm_review_adapter import ReviewRequest, validate_evidence_input
from workflow_kernel.native_review import validate_native_output
from workflow_kernel.review_closeout import EvidenceAssemblyError, _validate_production_lane


THREAD = "11111111-1111-4111-8111-111111111111"
PARENT = "22222222-2222-4222-8222-222222222222"
TURN = "33333333-3333-4333-8333-333333333333"
OTHER = "44444444-4444-4444-8444-444444444444"
AGENT = "/root/synthetic_unit_reviewer"
HEAD = "a" * 40
STAMP = "2026-10-09T00:00:00Z"
OUTPUT_REF = "review/synthetic-unit-output.md"
OUTPUT_PATH = "/synthetic-unit-run/" + OUTPUT_REF
OUTPUT = b"SYNTHETIC UNIT OUTPUT; never live review proof.\nNo findings.\n"
REVIEWER = "native-" + hashlib.sha256(THREAD.encode()).hexdigest()[:16]


def fixture():
    """Production-shaped parser input; explicitly synthetic unit data."""
    value = {
        "schema_version": 1, "operation": "lane", "run_id": "synthetic-unit-run",
        "pass_id": "initial", "lane": "security", "attempt": 1,
        "reviewer": REVIEWER,
        "source": {"repository": "synthetic/unit-fixture", "head": HEAD,
                   "base": HEAD, "worktree_ref": None, "request_ref": "review/request.json"},
        "requested": {"designation": "scoped", "paths": ["source.txt"],
                      "evidence_refs": ["review/prompt.md"],
                      "required_evidence_refs": ["review/prompt.md"], "patch_ref": None},
        "inspected": {"paths": ["source.txt"], "basis": "repository",
                      "limitations": [], "missing_evidence_refs": []},
        "literal": {"output_ref": OUTPUT_REF, "native_trace_ref": "review/synthetic-unit-trace.jsonl",
                    "native_index_ref": "review/synthetic-unit-index.json"},
        "result": {"status": "no_findings", "findings": [], "incomplete_reasons": []},
        # recovery exercises the production envelope shape, not provenance of
        # these authored unit fixtures; no fixture is published as live proof.
        "provenance": {"kind": "recovery", "executed_at": STAMP, "source_refs": []},
        "recheck": {"prior_record_ref": None, "selection_ref": None, "repair_refs": []},
    }
    text = OUTPUT.decode()
    patch = "*** Begin Patch\n*** Add File: " + OUTPUT_PATH + "\n" + "".join(
        "+" + line + "\n" for line in text.splitlines()
    ) + "*** End Patch\n"
    payloads = [
        ("session_meta", {
            "id": THREAD, "parent_thread_id": PARENT, "agent_path": AGENT,
            "originator": "T3 Code", "thread_source": "subagent",
            "model_provider": "openai", "cwd": "/synthetic-unit-repository",
            "source": {"subagent": {"thread_spawn": {
                "parent_thread_id": PARENT, "agent_path": AGENT, "depth": 1,
            }}},
        }),
        ("turn_context", {"turn_id": TURN, "model": "gpt-6.1-sol",
                          "cwd": "/synthetic-unit-repository"}),
        ("response_item", {
            "type": "agent_message", "author": "/root", "recipient": AGENT,
            "internal_chat_message_metadata_passthrough": {"turn_id": TURN},
            "encrypted_content": "SYNTHETIC_UNIT_NOT_REAL_ENCRYPTION",
        }),
        ("event_msg", {
            "type": "item_completed", "thread_id": THREAD, "turn_id": TURN,
            "item": {"type": "CommandExecution", "status": "completed",
                     "cwd": "file:///synthetic-unit-repository",
                     "command": ["/bin/bash", "-lc", "git status --short --branch && git rev-parse HEAD && git diff --stat " + HEAD + "..HEAD"], "exit_code": 0,
                     "stdout": "## synthetic-unit-branch\n" + HEAD + "\n", "stderr": ""},
        }),
        ("response_item", {
            "type": "custom_tool_call", "name": "exec", "status": "completed",
            "call_id": "synthetic-unit-call", "turn_id": TURN,
            "input": "text(await tools.apply_patch(" + json.dumps(patch) + "));",
        }),
        ("event_msg", {
            "type": "item_completed", "thread_id": THREAD, "turn_id": TURN,
            "item": {"type": "FileChange", "status": "completed",
                     "changes": {OUTPUT_PATH: {"type": "add", "content": text}}},
        }),
        ("response_item", {
            "type": "custom_tool_call_output", "call_id": "synthetic-unit-call",
            "turn_id": TURN, "output": [{"type": "text", "text": "Script completed\n"}],
        }),
        ("response_item", {
            "type": "message", "role": "assistant", "phase": "final_answer",
            "turn_id": TURN, "content": [{"type": "output_text", "text": "Synthetic unit fixture completed."}],
        }),
        ("event_msg", {"type": "task_complete", "turn_id": TURN,
                       "last_agent_message": "Synthetic unit fixture completed."}),
    ]
    records = [{"ordinal": i * 2, "timestamp": STAMP, "type": kind, "payload": payload}
               for i, (kind, payload) in enumerate(payloads)]
    return records, value


def encoded(records):
    return b"".join(json.dumps(record, separators=(",", ":")).encode() + b"\n" for record in records)


def index_for(records):
    # Authored metadata exercises internal consistency, not original-host
    # authenticity. The declared full-trace digest is not authenticated here.
    return json.dumps({"schema_version": 1, "full_trace_digest": "sha256:" + "9" * 64,
                       "excerpt_digest": "sha256:" + hashlib.sha256(encoded(records)).hexdigest(),
                       "thread_id": THREAD, "original_ordinals": [r["ordinal"] for r in records],
                       "original_line_numbers": [r["ordinal"] + 1 for r in records]}).encode()


class NativeReviewTests(unittest.TestCase):
    def validate(self, records=None, value=None, output=OUTPUT):
        default_records, default_value = fixture()
        records = default_records if records is None else records
        return validate_native_output(encoded(records), output,
                                      default_value if value is None else value, index_for(records))

    def test_valid_excerpt_derives_participant_and_reported_identity(self):
        row = self.validate()
        self.assertEqual(REVIEWER, row["reviewer"])
        self.assertEqual("security", row["lane"])
        self.assertEqual("openai", row["provider"])
        self.assertEqual("openai", row["attempted_provider"])
        self.assertEqual("gpt-6.1-sol", row["model"])
        self.assertEqual("codex-collaboration", row["implemented_by"])
        self.assertEqual("openai", row["reviewer_family"])
        self.assertEqual([OUTPUT_REF], row["evidence_refs"])
        self.assertEqual(0, row["finding_count"])

    def test_inert_patch_and_source_commands_are_never_executed(self):
        # A valid parser result is not command execution or proof that this
        # synthetic path/source exists; the module consumes bytes only.
        with mock.patch("subprocess.run", side_effect=AssertionError("inert evidence must not execute")) as runner:
            self.assertEqual(REVIEWER, self.validate()["reviewer"])
            runner.assert_not_called()

    def test_every_required_witness_is_required(self):
        for missing in range(9):
            with self.subTest(missing=missing):
                records, value = fixture()
                del records[missing]
                with self.assertRaises(ValueError):
                    self.validate(records, value)

    def test_output_requires_exact_bytes_and_absolute_owned_reference(self):
        for mutation in ("body", "path", "relative", "traversal", "change_kind", "duplicate"):
            with self.subTest(mutation=mutation):
                records, value = fixture()
                changes = records[5]["payload"]["item"]["changes"]
                if mutation == "body":
                    changes[OUTPUT_PATH]["content"] += "Changed\n"
                elif mutation == "change_kind":
                    changes[OUTPUT_PATH]["type"] = "update"
                elif mutation == "duplicate":
                    records.insert(6, copy.deepcopy(records[5]))
                    for i, r in enumerate(records): r["ordinal"] = i
                else:
                    path = {"path": "/synthetic-unit-run/review/other.md",
                            "relative": OUTPUT_REF,
                            "traversal": "/synthetic-unit-run/../" + OUTPUT_REF}[mutation]
                    changes[path] = changes.pop(OUTPUT_PATH)
                with self.assertRaises(ValueError):
                    self.validate(records, value)
        with self.assertRaises(ValueError):
            self.validate(output=OUTPUT.rstrip(b"\n"))

    def test_source_observation_requires_exact_successful_head_and_turn(self):
        cases = (("stdout", "b" * 40 + "\n"), ("stdout", "prefix" + HEAD + "\n"),
                 ("exit_code", 1), ("exit_code", False), ("status", "failed"),
                 ("command", ["rtk git status --short"]), ("command", "git rev-parse HEAD"))
        for field, replacement in cases:
            with self.subTest(field=field, replacement=replacement):
                records, value = fixture()
                records[3]["payload"]["item"][field] = replacement
                with self.assertRaises(ValueError):
                    self.validate(records, value)
        for field, replacement in (("thread_id", OTHER), ("turn_id", OTHER)):
            records, value = fixture()
            records[3]["payload"][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(records, value)

    def test_closed_legacy_git_program_proves_head_and_clean_status(self):
        self.assertEqual(REVIEWER, self.validate()["reviewer"])

    def test_standalone_head_requires_separate_same_turn_clean_status(self):
        records, value = fixture()
        records[3]["payload"]["item"].update(command=["/bin/bash", "-lc", "rtk proxy git rev-parse HEAD"], stdout=HEAD + "\n")
        with self.assertRaises(ValueError): self.validate(records, value)
        status = copy.deepcopy(records[3])
        status["payload"]["item"].update(command=["/bin/bash", "-lc", "rtk proxy git status --short"], stdout="")
        records.insert(4, status)
        for i, record in enumerate(records): record["ordinal"] = i
        self.assertEqual(REVIEWER, self.validate(records, value)["reviewer"])
        for field, replacement in (("stdout", " M source.txt\n"), ("exit_code", 1)):
            changed = copy.deepcopy(records)
            changed[4]["payload"]["item"][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate(changed, value)
        changed = copy.deepcopy(records)
        changed[4]["payload"]["turn_id"] = OTHER
        with self.assertRaises(ValueError): self.validate(changed, value)

    def test_closed_asset_lookup_program_has_no_dirty_status_after_head(self):
        records, value = fixture()
        script = ("rtk rg --files /synthetic-unit/.codex/plugins/cache/depot"
                  " | rtk rg 'runtime-resolution\\.md$|workflow-kernel.*SKILL\\.md$' | rtk head -30\n"
                  "rtk git remote -v\nrtk git rev-parse HEAD\nrtk git status --short")
        records[3]["payload"]["item"].update(command=["/bin/bash", "-lc", script],
                                             stdout="/synthetic-unit/asset.md\norigin synthetic (fetch)\n" + HEAD + "\n")
        self.assertEqual(REVIEWER, self.validate(records, value)["reviewer"])
        records[3]["payload"]["item"]["stdout"] += " M source.txt\n"
        with self.assertRaises(ValueError): self.validate(records, value)

    def test_standalone_source_pair_requires_order_and_same_normalized_cwd(self):
        def pair():
            records, value = fixture()
            records[3]["payload"]["item"].update(command=["/bin/bash", "-lc", "rtk proxy git rev-parse HEAD"], stdout=HEAD + "\n")
            status = copy.deepcopy(records[3])
            status["payload"]["item"].update(command=["/bin/bash", "-lc", "rtk proxy git status --short"], stdout="")
            records.insert(4, status)
            for i, r in enumerate(records): r["ordinal"] = i
            return records, value
        records, value = pair()
        records[4]["payload"]["item"]["cwd"] = "file://localhost/synthetic-unit-repository/."
        self.assertEqual(REVIEWER, self.validate(records, value)["reviewer"])
        for cwd in ("file:///other-repository", None, "file:///synthetic-unit-repository/../other", "https://example.test/repo"):
            records, value = pair()
            records[4]["payload"]["item"]["cwd"] = cwd
            with self.subTest(cwd=cwd), self.assertRaises(ValueError): self.validate(records, value)
        records, value = pair()
        records[3], records[4] = records[4], records[3]
        for i, r in enumerate(records): r["ordinal"] = i
        with self.assertRaises(ValueError): self.validate(records, value)
        records, value = pair()
        dirty = copy.deepcopy(records[4]);dirty["payload"]["item"]["stdout"] = " M source.txt\n"
        records.insert(5, dirty)
        for i, r in enumerate(records): r["ordinal"] = i
        with self.assertRaises(ValueError): self.validate(records, value)

    def test_conflicting_head_context_and_missing_combined_cwd_are_blocked(self):
        records, value = fixture()
        records[3]["payload"]["item"].pop("cwd")
        with self.assertRaises(ValueError): self.validate(records, value)
        for different in ("head", "cwd"):
            records, value = fixture()
            other = copy.deepcopy(records[3])
            if different == "head": other["payload"]["item"]["stdout"] = "## branch\n" + "b" * 40 + "\n"
            else: other["payload"]["item"]["cwd"] = "file:///other-repository"
            records.insert(4, other)
            for i, r in enumerate(records): r["ordinal"] = i
            with self.subTest(different=different), self.assertRaises(ValueError): self.validate(records, value)

    def test_printed_quoted_control_and_multi_head_commands_cannot_rebind_source(self):
        commands = ("printf '; git rev-parse HEAD;\\n%s\\n' " + HEAD,
                    "rtk git rev-parse HEAD; rtk git rev-parse HEAD~1",
                    "false && git rev-parse HEAD; echo " + HEAD,
                    "echo 'git rev-parse HEAD'", "git rev-parse HEAD >/dev/null; echo " + HEAD,
                    "git status --short; rtk proxy git rev-parse HEAD")
        for command in commands:
            for declared in (HEAD, "b" * 40):
                records, value = fixture()
                value["source"]["head"] = declared
                records[3]["payload"]["item"].update(command=["/bin/bash", "-lc", command],
                                                     stdout=HEAD + "\n" + "b" * 40 + "\n")
                with self.subTest(command=command, declared=declared), self.assertRaises(ValueError): self.validate(records, value)
        for stdout in (" M source.txt\n" + HEAD + "\n", "## branch\n M source.txt\n" + HEAD + "\n",
                       "## branch\n" + HEAD + "\n" + "b" * 40 + "\n"):
            records, value = fixture()
            records[3]["payload"]["item"]["stdout"] = stdout
            with self.subTest(stdout=stdout), self.assertRaises(ValueError): self.validate(records, value)

    def test_missing_null_and_malformed_call_identity_never_pairs(self):
        for replacement in (None, "", 5, True, "x" * 257, "bad id"):
            records, value = fixture()
            for i in (4, 6): records[i]["payload"]["call_id"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError): self.validate(records, value)
        records, value = fixture()
        for i in (4, 6): del records[i]["payload"]["call_id"]
        with self.assertRaises(ValueError): self.validate(records, value)

    def test_required_index_binds_excerpt_actor_and_original_record_mapping(self):
        records, value = fixture()
        index = json.loads(index_for(records))
        mutations = (("schema_version", True), ("full_trace_digest", "not-a-digest"),
                     ("excerpt_digest", "sha256:" + "0" * 64), ("thread_id", OTHER),
                     ("original_ordinals", list(reversed(index["original_ordinals"]))),
                     ("original_line_numbers", [n + 1 for n in index["original_line_numbers"]]))
        for field, replacement in mutations:
            changed = dict(index, **{field: replacement})
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_native_output(encoded(records), OUTPUT, value, json.dumps(changed).encode())
        for invalid in (b"{}", b"null", b"NaN", b" " * (64 * 1024 + 1)):
            with self.assertRaises(ValueError): validate_native_output(encoded(records), OUTPUT, value, invalid)

    def test_source_identity_cannot_be_retargeted_by_envelope(self):
        records, value = fixture()
        value["source"]["head"] = "b" * 40
        with self.assertRaises(ValueError): self.validate(records, value)
        value["source"]["head"] = HEAD
        value["source"]["worktree_ref"] = "review/staged-historical.patch"
        with self.assertRaisesRegex(ValueError, "committed source"):
            self.validate(records, value)
        value["source"]["worktree_ref"] = None
        value["reviewer"] = "native-wrong-actor"
        with self.assertRaisesRegex(ValueError, "participant mismatch"):
            self.validate(records, value)

    def test_session_and_assignment_cannot_claim_another_actor(self):
        mutations = ((0, "id", PARENT), (0, "parent_thread_id", THREAD),
                     (0, "originator", "other host"), (0, "thread_source", "main"),
                     (0, "agent_path", "/root/other_reviewer"),
                     (2, "recipient", "/root/other_reviewer"),
                     (2, "author", "/root/other_reviewer"), (2, "turn_id", OTHER))
        for index, field, replacement in mutations:
            with self.subTest(index=index, field=field):
                records, value = fixture()
                records[index]["payload"][field] = replacement
                with self.assertRaises(ValueError): self.validate(records, value)
        records, value = fixture()
        records[0]["payload"]["source"]["subagent"]["thread_spawn"]["depth"] = True
        with self.assertRaises(ValueError): self.validate(records, value)

    def test_turn_cannot_be_spliced_across_write_result_final_and_completion(self):
        for index in (1, 4, 5, 6, 7, 8):
            with self.subTest(index=index):
                records, value = fixture()
                records[index]["payload"]["turn_id"] = OTHER
                with self.assertRaises(ValueError): self.validate(records, value)

    def test_optional_completion_identity_must_match_when_present(self):
        for index in (6, 7, 8):
            records, value = fixture()
            records[index]["payload"]["thread_id"] = OTHER
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.validate(records, value)
        records, value = fixture()
        records[5]["payload"]["thread_id"] = OTHER
        with self.assertRaises(ValueError): self.validate(records, value)
        records, value = fixture()
        del records[6]["payload"]["turn_id"]
        self.assertEqual(REVIEWER, self.validate(records, value)["reviewer"])

    def test_duplicate_session_or_completion_witness_is_ambiguous(self):
        for index in (0, 6, 7, 8):
            records, value = fixture()
            records.insert(index + 1, copy.deepcopy(records[index]))
            for i, record in enumerate(records): record["ordinal"] = i
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.validate(records, value)

    def test_tool_call_and_result_must_bind_one_completed_patch(self):
        mutations = ((4, "call_id", "other-call"), (6, "call_id", "other-call"),
                     (4, "status", "in_progress"), (4, "name", "other_tool"),
                     (4, "input", 'text("no file write");'),
                     (6, "output", []), (6, "output", [{"type": "text", "text": "Script failed\n"}]))
        for index, field, replacement in mutations:
            with self.subTest(index=index, field=field):
                records, value = fixture()
                records[index]["payload"][field] = replacement
                with self.assertRaises(ValueError): self.validate(records, value)

    def test_final_and_task_complete_follow_paired_tool_result(self):
        for left, right in ((6, 7), (7, 8), (5, 8)):
            records, value = fixture()
            records[left], records[right] = records[right], records[left]
            for i, r in enumerate(records): r["ordinal"] = i
            with self.subTest(swap=(left, right)), self.assertRaises(ValueError):
                self.validate(records, value)
        for field, replacement in (("role", "user"), ("phase", "commentary")):
            records, value = fixture()
            records[7]["payload"][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate(records, value)

    def test_strict_json_and_original_ordinals_reject_reordered_or_truncated_trace(self):
        records, value = fixture()
        raw = encoded(records)
        hostile = (raw.replace(b'"ordinal":0', b'"ordinal":0,"ordinal":0', 1),
                   raw.replace(b'"model_provider":"openai"', b'"model_provider":"openai","model_provider":"openai"', 1),
                   raw[:-5], raw + b"\n", b"[]\n", b"null\n", b'NaN\n')
        for trace in hostile:
            with self.subTest(trace_prefix=trace[:30]), self.assertRaises(ValueError):
                validate_native_output(trace, OUTPUT, value, index_for(records))
        for ordinal in (-1, True, 0, 1.5):
            records, value = fixture()
            records[1]["ordinal"] = ordinal
            with self.subTest(ordinal=ordinal), self.assertRaises(ValueError): self.validate(records, value)
        records, value = fixture()
        records[0], records[1] = records[1], records[0]
        with self.assertRaises(ValueError): self.validate(records, value)

    def test_record_and_byte_caps_reject_oversized_input(self):
        records, value = fixture()
        with self.assertRaises(ValueError):
            validate_native_output(b" " * (2 * 1024 * 1024 + 1), OUTPUT, value, index_for(records))
        oversized = copy.deepcopy(records)
        oversized[1]["payload"]["padding"] = "x" * (512 * 1024)
        with self.assertRaises(ValueError): self.validate(oversized, value)
        extras = [{"ordinal": 100 + i, "type": "event_msg", "payload": {"type": "unit_padding"}}
                  for i in range(4096)]
        with self.assertRaises(ValueError): self.validate(records + extras, value)

    def test_malformed_model_metadata_is_rejected(self):
        for index, field in ((0, "model_provider"), (1, "model")):
            for malformed in ({"model": "pretend"}, "bad\nidentity", "x" * 129, True):
                records, value = fixture()
                records[index]["payload"][field] = malformed
                with self.subTest(index=index, malformed=malformed), self.assertRaises(ValueError):
                    self.validate(records, value)

    def test_missing_provider_and_model_are_reported_as_unknown(self):
        records, value = fixture()
        records[0]["payload"].pop("model_provider")
        records[1]["payload"].pop("model")
        row = self.validate(records, value)
        self.assertEqual("unknown", row["provider"])
        self.assertEqual("not_reported", row["model"])

    def test_unclassified_model_keeps_actual_trace_and_unknown_summary(self):
        records, value = fixture()
        records[1]["payload"]["model"] = "opaque-model"
        row = self.validate(records, value)
        self.assertEqual("opaque-model", records[1]["payload"]["model"])
        self.assertEqual("not_reported", row["model"])
        self.assertEqual("unknown", row["reviewer_family"])

    def test_task_completion_timestamp_is_aware_and_exact(self):
        for timestamp in ("2026-10-09T00:00:01Z", "2026-10-09T00:00:00", "not-a-time"):
            records, value = fixture()
            records[8]["timestamp"] = timestamp
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError): self.validate(records, value)
        records, value = fixture()
        value["provenance"]["executed_at"] = "2026-10-09T08:00:00+08:00"
        self.assertEqual(REVIEWER, self.validate(records, value)["reviewer"])


class NativeLiteralEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.records, self.value = fixture()
        self.request = ReviewRequest.from_mapping({
            "run_id": "synthetic-unit-run", "requested_lanes": ["security"], "mode": "full",
            "source_repository": "synthetic/unit-fixture", "source_head": HEAD,
        })

    def test_closed_native_literal_variant_and_existing_router_variant(self):
        self.assertEqual(self.value, validate_evidence_input(self.value, self.request))
        routed = copy.deepcopy(self.value)
        routed["literal"] = {"output_ref": OUTPUT_REF,
                             "dispatch_receipt_ref": "receipts/private/router/unit.json",
                             "companion_ref": "review/unit-companion.json"}
        # References test only the historical envelope. No router receipt or
        # provider execution is manufactured by these unit tests.
        self.assertEqual(routed, validate_evidence_input(routed, self.request))
        routed["provenance"]["kind"] = "synthetic_test"
        self.assertEqual(routed, validate_evidence_input(routed, self.request))

    def test_native_literal_rejects_mixed_missing_and_unknown_fields(self):
        mutations = ({"output_ref": OUTPUT_REF},
                     {"native_trace_ref": "review/unit.jsonl"},
                     {"output_ref": OUTPUT_REF, "native_trace_ref": "review/unit.jsonl",
                      "dispatch_receipt_ref": "receipts/private/router/unit.json"},
                     {"output_ref": OUTPUT_REF, "native_trace_ref": "review/unit.jsonl",
                      "companion_ref": "review/unit-companion.json"},
                     {"output_ref": OUTPUT_REF, "native_trace_ref": "review/unit.jsonl", "unknown": "unit"})
        for literal in mutations:
            value = copy.deepcopy(self.value)
            value["literal"] = literal
            with self.subTest(fields=sorted(literal)), self.assertRaises(ValueError):
                validate_evidence_input(value, self.request)

    def test_native_envelope_rejects_dirty_source_and_synthetic_provenance(self):
        for field, replacement in (("worktree_ref", "review/dirty.patch"),
                                   ("kind", "synthetic_test")):
            value = copy.deepcopy(self.value)
            value["source" if field == "worktree_ref" else "provenance"][field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "committed production source"):
                validate_evidence_input(value, self.request)


class MixedNativeRoutedIntakeTests(unittest.TestCase):
    """Synthetic mixed-history regression; never real dispatch or lane proof.

    Mock only the sealed-storage readers. Native witness validation, routed
    companion agreement and routed dispatch anti-reuse remain real code paths.
    """
    def setUp(self):
        records, native = fixture()
        self.native_record = {
            "input": native,
            "source_snapshot": {"repository": "synthetic/unit-fixture", "head": HEAD},
            "bindings": {ref: {} for ref in native["literal"].values()},
        }
        self.current = self.routed_record("current", HEAD)
        self.previous = self.routed_record("previous", "b" * 40)
        self.history = {"unit-native": self.native_record, "unit-routed": self.previous}
        self.dispatch = {
            # Minimal authored unit input, not an invented actual receipt.
            "schemaVersion": 1,
            "served": {"provider": "openai", "model": "gpt-6.1-sol", "family": "openai"},
            "attempts": [{"status": "completed"}],
            "publication": {"output": "published"}, "transportStub": False,
        }
        companion = validate_native_output(encoded(records), OUTPUT, native, index_for(records))
        companion.update(reviewer="synthetic-routed-unit", implemented_by="unit-router")
        dispatch_bytes = json.dumps(self.dispatch).encode()
        self.bound = {
            id(self.native_record): {
                native["literal"]["native_trace_ref"]: encoded(records),
                native["literal"]["output_ref"]: OUTPUT,
                native["literal"]["native_index_ref"]: index_for(records),
            },
            id(self.current): {
                self.current["input"]["literal"]["dispatch_receipt_ref"]: dispatch_bytes,
                self.current["input"]["literal"]["companion_ref"]: json.dumps(companion).encode(),
            },
            id(self.previous): {
                self.previous["input"]["literal"]["dispatch_receipt_ref"]: dispatch_bytes,
            },
        }

    @staticmethod
    def routed_record(label, head):
        _records, value = fixture()
        value["reviewer"] = "synthetic-routed-unit"
        value["source"]["head"] = head
        value["literal"] = {
            "output_ref": OUTPUT_REF,
            "dispatch_receipt_ref": "review/unit-" + label + "-dispatch.json",
            "companion_ref": "review/unit-" + label + "-companion.json",
        }
        return {"input": value,
                "source_snapshot": {"repository": "synthetic/unit-fixture", "head": head},
                "bindings": {ref: {} for ref in value["literal"].values()}}

    def validate_intake(self, record, history_order):
        receipts = [{"stage": "review_lane_evidence", "authoritative_receipt": ref}
                    for ref in history_order]
        receipts.insert(0, {"stage": "unrelated-unit-stage"})
        with mock.patch("workflow_kernel.review_closeout._bound_bytes",
                        side_effect=lambda _root, bound_record, ref: self.bound[id(bound_record)][ref]), \
                mock.patch("workflow_kernel.review_closeout._read_source_record",
                           side_effect=lambda _root, ref, _role: self.history[ref]) as reader:
            row = _validate_production_lane("synthetic-unit-root", record, receipts)
            return row, reader

    def test_routed_lane_accepts_native_history_without_dispatch_reference(self):
        previous_ref = self.previous["input"]["literal"]["dispatch_receipt_ref"]
        different_dispatch = dict(self.dispatch, unit_fixture_note="SYNTHETIC DISTINCT DISPATCH")
        self.bound[id(self.previous)][previous_ref] = json.dumps(different_dispatch).encode()
        self.assertNotIn("dispatch_receipt_ref", self.native_record["input"]["literal"])
        for order in (("unit-native", "unit-routed"), ("unit-routed", "unit-native")):
            with self.subTest(order=order):
                row, reader = self.validate_intake(self.current, order)
                self.assertEqual("synthetic-routed-unit", row["reviewer"])
                self.assertEqual(2, reader.call_count)

    def test_native_history_does_not_disable_routed_cross_source_anti_reuse(self):
        for order in (("unit-native", "unit-routed"), ("unit-routed", "unit-native")):
            with self.subTest(order=order), self.assertRaises(EvidenceAssemblyError) as caught:
                self.validate_intake(self.current, order)
            self.assertEqual({"stage": "lane_validation", "reason": "source_scope_mismatch",
                              "path": "review/evidence.json"}, caught.exception.detail())

    def test_exact_source_routed_retry_remains_valid_alongside_native_history(self):
        self.previous["source_snapshot"] = copy.deepcopy(self.current["source_snapshot"])
        row, reader = self.validate_intake(self.current, ("unit-native", "unit-routed"))
        self.assertEqual("gpt-6.1-sol", row["model"])
        self.assertEqual(2, reader.call_count)

    def test_native_intake_uses_its_witnesses_even_with_routed_history(self):
        row, reader = self.validate_intake(self.native_record, ("unit-routed",))
        self.assertEqual(REVIEWER, row["reviewer"])
        self.assertEqual("codex-collaboration", row["implemented_by"])
        reader.assert_not_called()
        # Routed history cannot rescue a missing native source witness.
        trace_ref = self.native_record["input"]["literal"]["native_trace_ref"]
        records, _value = fixture()
        records[3]["payload"]["item"]["stdout"] = "b" * 40 + "\n"
        self.bound[id(self.native_record)][trace_ref] = encoded(records)
        with self.assertRaises(EvidenceAssemblyError) as caught:
            self.validate_intake(self.native_record, ("unit-routed",))
        self.assertEqual({"stage": "lane_validation", "reason": "incomplete_inspection",
                          "path": "review/evidence.json"}, caught.exception.detail())


if __name__ == "__main__":
    unittest.main()
