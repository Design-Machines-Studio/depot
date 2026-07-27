"""Executable conformance contract for the repository quality pulse.

The fixtures are synthetic release-readiness evidence.  They do not inspect
Baseplate, pull Docker images, contact a network, or provide authority to close
Baseplate issue #572.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from workflow_kernel.inspection import (
    InspectionError,
    authoritative_bytes,
    build_authoritative_result,
    classify_observations,
    compare_trends,
    decode_json_bytes,
    execute_inspection_lanes,
    load_host_attestation,
    load_inspection_profile,
    normalize_owned_path,
    render_markdown,
    stable_projection,
    validate_authoritative_result,
    validate_inspection_profile,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "quality-pulse"
LIVE_WIRES_CATALOG = ROOT / "plugins" / "live-wires" / "references" / "quality-rules-v1.json"
FIXED_COMMIT = "a" * 40
FIXED_REF = "refs/heads/conformance"
FIXED_PURPOSE = "quality-pulse"
FIXED_TIME = "2026-07-27T00:00:00Z"


def canonical_bytes(value):
    return (
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def compact_digest(value):
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_json(path):
    return decode_json_bytes(path.read_bytes())


def tree_digest(root):
    state = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            state.update(path.relative_to(root).as_posix().encode())
            state.update(b"\0")
            state.update(path.read_bytes())
            state.update(b"\0")
    return state.hexdigest()


class FakeAdapter:
    def __init__(self, returncodes):
        self.returncodes = iter(returncodes)
        self.calls = []

    def run(self, argv, *, cwd, env, timeout):
        self.calls.append((tuple(argv), Path(cwd), dict(env), timeout))
        returncode = next(self.returncodes)
        if returncode == 0:
            mount = next(
                item for item in argv
                if item.startswith("type=bind,source=")
                and item.endswith(",target=/quality-pulse-evidence")
            )
            evidence_root = mount.split(",target=", 1)[0].split("source=", 1)[1]
            lane_id = (
                "grep-fallback"
                if "quality-pulse-grep-fixture@" in " ".join(argv)
                else "dead-code-lint-primary"
            )
            Path(evidence_root, "observations.json").write_text(json.dumps({
                "schema_version": 1, "lane_id": lane_id, "observations": [],
            }))
        return SimpleNamespace(returncode=returncode, stdout="", stderr="")


class QualityPulseContract(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.fixture_digest = tree_digest(FIXTURES)
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name) / "repository"
        self.repository.mkdir()

    def tearDown(self):
        self.temporary.cleanup()
        self.assertEqual(
            tree_digest(FIXTURES),
            self.fixture_digest,
            "source fixture tree mutated during a conformance case",
        )

    def document(self, family="baseplate-derived"):
        return load_json(FIXTURES / family / "profile.json")

    def observations(self, family="baseplate-derived", changed=False):
        name = "changed-observations.json" if changed else "observations.json"
        return load_json(FIXTURES / family / name)

    def profile(self, family="baseplate-derived", document=None):
        return validate_inspection_profile(
            copy.deepcopy(document or self.document(family)),
            self.repository,
            profile_path=".dm-review/quality-pulse.json",
        )

    def assert_reason(self, expected, callback):
        with self.assertRaises(InspectionError) as caught:
            callback()
        self.assertEqual(caught.exception.reason_code, expected)

    def assert_baseplate_fixture_policy(self, document):
        catalog = next(
            item for item in document["catalogs"]
            if item["catalog_id"] == "baseplate-572-synthetic-rules"
        )
        wrapper = next(
            item for item in catalog["rules"]
            if item["rule_id"] == "bp-historical-wrapper"
        )
        definition = wrapper["definition"]
        self.assertIn("profile_decision", definition)
        self.assertIn(
            definition["profile_decision"],
            definition["alternative_decisions"],
        )

    def write_loaded_profile(self, family="baseplate-derived"):
        relative = Path(".dm-review/quality-pulse.json")
        path = self.repository / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(canonical_bytes(self.document(family)))
        return load_inspection_profile(relative, self.repository), path

    def attestation(self, profile):
        return {
            "schema_version": 1,
            "repository_root": str(profile.repository_root),
            "profile_path": profile.profile_path,
            "profile_digest": profile.digest,
            "source": "git",
            "ref": FIXED_REF,
            "commit": FIXED_COMMIT,
            "dirty": False,
            "operator_authorization_event_id": "approved-conformance",
            "purpose": FIXED_PURPOSE,
        }

    def run_lanes(self, returncodes, family="baseplate-derived", mutate=None):
        profile, _path = self.write_loaded_profile(family)
        adapter = FakeAdapter(returncodes)
        receipts = execute_inspection_lanes(
            profile,
            [profile.to_dict()["lanes"][0]["lane_id"]],
            self.attestation(profile),
            source="git",
            ref=FIXED_REF,
            commit=FIXED_COMMIT,
            dirty=False,
            purpose=FIXED_PURPOSE,
            operator_authorization_event_id="approved-conformance",
            adapter=adapter,
            clock=lambda: FIXED_TIME,
            pre_admission_hook=mutate,
        )
        return profile, receipts, adapter

    def receipts(self, profile, statuses=None, observations=None):
        lanes = profile.to_dict()["lanes"]
        observations = [] if observations is None else observations
        statuses = statuses or (
            ["unavailable", "fallback"] if len(lanes) == 2 else ["available"]
        )
        values = []
        bound = False
        for lane, status in zip(lanes, statuses):
            reason = {
                "available": "completed",
                "unavailable": "runtime_unavailable",
                "failed": "nonzero_exit",
                "fallback": "primary_unavailable",
                "skipped": "primary_available",
            }[status]
            lane_observations = (
                observations
                if status in {"available", "fallback"} and not bound
                else []
            )
            if lane_observations:
                bound = True
            envelope = {
                "schema_version": 1,
                "lane_id": lane["lane_id"],
                "observations": lane_observations,
            }
            values.append({
                "lane_id": lane["lane_id"],
                "status": status,
                "reason_code": reason,
                "primary_lane_id": lane["primary_lane_id"],
                "argv_identity": digest({"argv": lane["argv"]}),
                "tool_identity": lane["tool_identity"],
                "image_identity": lane["image_identity"],
                "service_identity": lane["service_identity"],
                "plugin_version": lane["plugin_version"],
                "timeout_seconds": lane["timeout_seconds"],
                "started_at": None if status == "skipped" else FIXED_TIME,
                "finished_at": None if status == "skipped" else FIXED_TIME,
                "exit_code": (
                    None if status in {"unavailable", "skipped"} else
                    (0 if status in {"available", "fallback"} else 1)
                ),
                "evidence_references": lane["evidence_paths"],
                "evidence_digest": (
                    digest(envelope)
                    if status in {"available", "fallback"} else None
                ),
                "observation_ids": [
                    item["observation_id"] for item in lane_observations
                ],
                "stdout": "",
                "stderr": "",
                "redacted_values": 0,
            })
        return values

    def authoritative(self, family="baseplate-derived", observations=None):
        profile = self.profile(family)
        observations = observations or self.observations(family)
        result = build_authoritative_result(
            profile,
            source="git",
            ref=FIXED_REF,
            commit=FIXED_COMMIT,
            dirty=False,
            observations=observations,
            lane_receipts=self.receipts(profile, observations=observations),
            invocation={
                "started_at": FIXED_TIME,
                "finished_at": FIXED_TIME,
                "operator_authorization_event_id": "approved-conformance",
                "purpose": FIXED_PURPOSE,
                "selected_lane_ids": [profile.to_dict()["lanes"][0]["lane_id"]],
            },
        )
        return profile, result

    # Profile and catalog cases -------------------------------------------------

    def case_profile_valid(self):
        document = self.document()
        self.assert_baseplate_fixture_policy(document)
        profile = self.profile(document=document)
        self.assertEqual(profile.document["schema_version"], 1)

    def case_profile_version(self):
        value = self.document()
        value["schema_version"] = 2
        self.assert_reason(
            "unsupported_schema_version", lambda: self.profile(document=value),
        )

    def case_duplicate_key(self):
        self.assert_reason(
            "duplicate_json_key",
            lambda: decode_json_bytes(b'{"schema_version":1,"schema_version":1}'),
        )

    def case_unknown_field(self):
        value = self.document()
        value["unexpected"] = True
        self.assert_reason("unknown_key", lambda: self.profile(document=value))

    def case_missing_reference(self):
        value = self.document()
        value["rules"][0]["metric_ids"] = ["missing-metric"]
        self.assert_reason(
            "unknown_metric_reference", lambda: self.profile(document=value),
        )

    def case_catalog_digest(self):
        value = self.document()
        value["catalogs"][0]["content_digest"] = "sha256:" + "0" * 64
        self.assert_reason(
            "catalog_digest_mismatch", lambda: self.profile(document=value),
        )

    def case_catalog_identity(self):
        for mutation, reason in (
            ({"catalog_id": "unknown-catalog"}, "unknown_catalog_reference"),
            ({"catalog_version": "9.9.9"}, "catalog_binding_mismatch"),
        ):
            value = self.document()
            value["metrics"][0].update(mutation)
            with self.subTest(mutation=mutation):
                self.assert_reason(reason, lambda: self.profile(document=value))

    # Path and classification cases -------------------------------------------

    def case_exact_design_path(self):
        results = classify_observations(self.profile(), self.observations())
        item = next(x for x in results if x["observation_id"] == "design-panel-javascript-count")
        self.assertEqual(item["classification"], "design_panel_informational")

    def case_baseplate_path(self):
        results = classify_observations(self.profile(), self.observations())
        item = next(x for x in results if x["observation_id"] == "bp-application-regression")
        self.assertEqual(item["classification"], "baseplate_actionable")

    def case_unknown_path(self):
        raw = self.observations()[0]
        raw["path"] = "outside/scope.txt"
        item = classify_observations(self.profile(), [raw])[0]
        self.assertEqual((item["classification"], item["actionable"]), ("unknown", True))

    def case_absolute_path(self):
        self.assert_reason(
            "invalid_repository_path",
            lambda: normalize_owned_path(self.repository, "/tmp/outside"),
        )

    def case_parent_traversal(self):
        self.assert_reason(
            "invalid_repository_path",
            lambda: normalize_owned_path(self.repository, "../outside"),
        )

    def case_symlink_escape(self):
        outside = Path(self.temporary.name) / "outside"
        outside.write_text("outside")
        link = self.repository / "escape"
        link.symlink_to(outside)
        self.assert_reason(
            "repository_path_escape",
            lambda: normalize_owned_path(self.repository, "escape", must_exist=True),
        )

    def case_classifications(self):
        values = classify_observations(self.profile(), self.observations())
        self.assertEqual(
            [item["classification"] for item in values],
            [
                "baseplate_actionable",
                "design_panel_informational",
                "design_panel_actionable",
                "unknown",
            ],
        )
        self.assertTrue(values[-1]["actionable"])
        self.assertEqual(values[-1]["raw_telemetry"]["retained"], "unknown fixture telemetry")
        expected = load_json(FIXTURES / "baseplate-derived" / "expected.json")
        self.assertEqual(
            [
                (
                    "unknown_fail_closed"
                    if item["classification"] == "unknown"
                    else item["classification"]
                )
                for item in values
            ],
            expected["expected_bucket_order"],
        )
        by_id = {item["observation_id"]: item for item in values}
        self.assertEqual(
            by_id["design-panel-javascript-count"]["confidence"],
            "low",
        )
        self.assertEqual(
            by_id["bp-application-regression"]["confidence"],
            "high",
        )
        base = self.observations()[0]
        mutations = (
            ("unknown_observation_schema", {"schema_version": 2}),
            ("unknown_path", {"path": "outside/scope.txt"}),
            ("unknown_metric", {"metric_id": "unknown-metric"}),
            ("unknown_surface", {"surface_id": "unknown-surface"}),
            ("unknown_classification", {"classification_id": "unknown-classification"}),
        )
        for reason, change in mutations:
            raw = copy.deepcopy(base)
            raw.update(change)
            raw["raw_telemetry"] = {"retained": reason, "value": 1}
            with self.subTest(reason=reason):
                item = classify_observations(self.profile(), [raw])[0]
                self.assertEqual(item["reason_code"], reason)
                self.assertEqual(item["classification"], "unknown")
                self.assertTrue(item["actionable"])
                self.assertEqual(item["raw_telemetry"]["retained"], reason)
        sensitive_rule = next(
            item for item in self.document()["catalogs"][0]["rules"]
            if item["rule_id"] == "bp-sensitive-surface"
        )
        self.assertEqual(
            set(sensitive_rule["definition"]["always_actionable_categories"]),
            {
                "accessibility",
                "authorization-default-deny",
                "csp-injection",
                "secret-leakage",
                "style-leakage",
                "transaction-event-ordering",
                "unsafe-raw-rendering",
            },
        )

    def case_missing_wrapper_decision(self):
        value = self.document()
        rule = next(
            x for x in value["catalogs"][0]["rules"]
            if x["rule_id"] == "bp-historical-wrapper"
        )
        del rule["definition"]["profile_decision"]
        projection = {
            key: value["catalogs"][0][key]
            for key in (
                "catalog_id", "schema_version", "catalog_version",
                "source_reference", "rules", "metrics",
            )
        }
        value["catalogs"][0]["content_digest"] = digest(projection)
        for binding in value["metrics"] + value["rules"]:
            if binding["catalog_id"] == value["catalogs"][0]["catalog_id"]:
                binding["catalog_digest"] = value["catalogs"][0]["content_digest"]
        self.assert_reason(
            "missing_profile_decision",
            lambda: validate_inspection_profile(
                value,
                self.repository,
                profile_path=".dm-review/quality-pulse.json",
            ),
        )

    # Lane and trust cases -----------------------------------------------------

    def case_lane_available(self):
        _profile, receipts, _adapter = self.run_lanes([0])
        self.assertEqual([x["status"] for x in receipts], ["available", "skipped"])

    def case_lane_unavailable_fallback(self):
        _profile, receipts, _adapter = self.run_lanes([125, 0])
        self.assertEqual([x["status"] for x in receipts], ["unavailable", "fallback"])
        self.assertEqual(receipts[1]["reason_code"], "primary_unavailable")

    def case_lane_failed_fallback(self):
        _profile, receipts, _adapter = self.run_lanes([1, 0])
        self.assertEqual([x["status"] for x in receipts], ["failed", "fallback"])
        self.assertEqual(receipts[1]["reason_code"], "primary_failed")

    def case_lane_skipped(self):
        _profile, receipts, adapter = self.run_lanes([0])
        self.assertEqual(receipts[1]["status"], "skipped")
        self.assertEqual(len(adapter.calls), 1)

    def case_unpinned(self):
        mutations = []
        unpinned = self.document()
        unpinned["lanes"][0]["image_identity"] = "fixture:latest"
        unpinned["lanes"][0]["argv"][-1] = "fixture:latest"
        mutations.append((unpinned, "unpinned_image_identity"))
        shell = self.document()
        shell["lanes"][0]["argv"].insert(-1, "--entrypoint=/bin/sh")
        mutations.append((shell, "shell_or_environment_authority"))
        undeclared = self.document()
        undeclared["outputs"]["undeclared"] = "output/extra.json"
        mutations.append((undeclared, "unknown_key"))
        for value, reason in mutations:
            adapter = FakeAdapter([0])
            with self.subTest(reason=reason):
                self.assert_reason(reason, lambda: self.profile(document=value))
                self.assertEqual(adapter.calls, [])

    def case_untrusted_execution(self):
        profile = self.profile()
        self.assert_reason(
            "loaded_profile_required",
            lambda: execute_inspection_lanes(
                profile, [profile.to_dict()["lanes"][0]["lane_id"]],
                self.attestation(profile), source="git", ref=FIXED_REF,
                commit=FIXED_COMMIT, dirty=False, purpose=FIXED_PURPOSE,
                operator_authorization_event_id="approved-conformance",
                adapter=FakeAdapter([0]), clock=lambda: FIXED_TIME,
            ),
        )

    def case_repository_attestation(self):
        profile, _ = self.write_loaded_profile()
        path = self.repository / "attestation.json"
        path.write_bytes(canonical_bytes(self.attestation(profile)))
        self.assert_reason(
            "repository_controlled_attestation",
            lambda: load_host_attestation(path, self.repository),
        )

    def case_attestation_root(self):
        profile, _ = self.write_loaded_profile()
        value = self.attestation(profile)
        value["repository_root"] = str(self.repository / "wrong")
        adapter = FakeAdapter([0])
        self.assert_reason(
            "attestation_binding_mismatch",
            lambda: execute_inspection_lanes(
                profile, [profile.to_dict()["lanes"][0]["lane_id"]], value,
                source="git", ref=FIXED_REF, commit=FIXED_COMMIT, dirty=False,
                purpose=FIXED_PURPOSE,
                operator_authorization_event_id="approved-conformance",
                adapter=adapter, clock=lambda: FIXED_TIME,
            ),
        )
        self.assertEqual(adapter.calls, [])

    def case_attestation_identity(self):
        profile, _ = self.write_loaded_profile()
        for field, replacement in (
            ("profile_digest", "sha256:" + "f" * 64),
            ("ref", "refs/heads/wrong"),
            ("commit", "b" * 40),
            ("dirty", True),
            ("purpose", "wrong-purpose"),
            ("operator_authorization_event_id", "different-approval"),
        ):
            value = self.attestation(profile)
            value[field] = replacement
            adapter = FakeAdapter([0])
            with self.subTest(field=field):
                self.assertRaises(
                    InspectionError,
                    execute_inspection_lanes,
                    profile,
                    [profile.to_dict()["lanes"][0]["lane_id"]],
                    value,
                    source="git",
                    ref=FIXED_REF,
                    commit=FIXED_COMMIT,
                    dirty=False,
                    purpose=FIXED_PURPOSE,
                    operator_authorization_event_id="approved-conformance",
                    adapter=adapter,
                    clock=lambda: FIXED_TIME,
                )
                self.assertEqual(adapter.calls, [])

    def case_profile_mutation(self):
        profile, path = self.write_loaded_profile()
        adapter = FakeAdapter([0])
        self.assert_reason(
            "profile_digest_mismatch",
            lambda: execute_inspection_lanes(
                profile, [profile.to_dict()["lanes"][0]["lane_id"]],
                self.attestation(profile), source="git", ref=FIXED_REF,
                commit=FIXED_COMMIT, dirty=False, purpose=FIXED_PURPOSE,
                operator_authorization_event_id="approved-conformance",
                adapter=adapter, clock=lambda: FIXED_TIME,
                pre_admission_hook=lambda: path.write_text("{}"),
            ),
        )
        self.assertEqual(adapter.calls, [])

    # Determinism, trend, redaction, render, and generic cases -----------------

    def case_stable_replay(self):
        _profile, first = self.authoritative()
        _profile, second = self.authoritative()
        self.assertEqual(authoritative_bytes(first), authoritative_bytes(second))

    def case_single_delta(self):
        _profile, baseline = self.authoritative()
        _profile, current = self.authoritative(
            observations=self.observations(changed=True),
        )
        trend = compare_trends(current, baseline)
        changed = [x for x in trend["deltas"] if x["delta"]]
        self.assertEqual(
            changed,
            [{
                "observation_id": "design-panel-javascript-count",
                "current": 4,
                "baseline": 3,
                "delta": 1,
            }],
        )
        baseline_by_id = {
            item["observation_id"]: item for item in baseline["observations"]
        }
        current_by_id = {
            item["observation_id"]: item for item in current["observations"]
        }
        for observation_id in sorted(baseline_by_id):
            before = copy.deepcopy(baseline_by_id[observation_id])
            after = copy.deepcopy(current_by_id[observation_id])
            if observation_id == "design-panel-javascript-count":
                before["raw_telemetry"]["value"] = after["raw_telemetry"]["value"]
            self.assertEqual(after, before)

    def case_path_order(self):
        _profile, result = self.authoritative()
        item = next(
            x for x in result["observations"]
            if x["observation_id"] == "design-panel-javascript-count"
        )
        self.assertEqual(
            item["raw_telemetry"]["ordered_paths"],
            sorted(item["raw_telemetry"]["ordered_paths"]),
        )

    def case_volatile_excluded(self):
        _profile, first = self.authoritative()
        second = copy.deepcopy(first)
        second["invocation"]["started_at"] = "2026-07-28T00:00:00Z"
        second["invocation"]["finished_at"] = "2026-07-28T00:00:01Z"
        self.assertEqual(stable_projection(first), stable_projection(second))

    def case_trend_compatible(self):
        _profile, value = self.authoritative()
        self.assertEqual(compare_trends(value, value)["status"], "compatible")

    def case_trend_discontinuity(self, field):
        _profile, current = self.authoritative()
        baseline = copy.deepcopy(current)
        if field == "schema_version":
            baseline["schema_version"] = 2
            status = compare_trends(current, baseline)
            self.assertEqual(status["status"], "baseline_discontinuity")
            self.assertEqual(status["incompatible_identity_fields"], ["schema_version"])
            return
        if field == "profile":
            fixture = load_json(
                FIXTURES / "baseplate-derived" / "prior-incompatible.json",
            )
            baseline["compatibility_identity"]["profile"]["profile_digest"] = (
                fixture["replacement"]
            )
            baseline["profile"]["profile_digest"] = fixture["replacement"]
        elif field == "metric_definitions":
            baseline["compatibility_identity"][field][0]["catalog_digest"] = (
                "sha256:" + "f" * 64
            )
        else:
            baseline["compatibility_identity"][field][0]["image_identity"] = (
                "fixture.example/tool@sha256:" + "f" * 64
            )
            baseline["lane_receipts"][0]["image_identity"] = (
                "fixture.example/tool@sha256:" + "f" * 64
            )
        baseline["stable_projection_digest"] = digest(stable_projection(baseline))
        status = compare_trends(current, baseline)
        self.assertEqual(status["status"], "baseline_discontinuity")
        self.assertIn(field, status["incompatible_identity_fields"])
        if field == "profile":
            self.assertEqual(status["status"], fixture["expected_status"])
            self.assertEqual(status["reason_code"], fixture["expected_reason_code"])
            self.assertEqual(
                status["incompatible_identity_fields"],
                fixture["expected_incompatible_identity_fields"],
            )

    def case_redaction(self, kind):
        raw = self.observations()[0]
        secret = {
            "credential": "ghp_fixtureSecret1234567890",
            "private": "-----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----",
            "dsn": "postgres://fixture:secret@db.example/test",
        }[kind]
        raw["raw_telemetry"] = {
            "token": secret,
            "safe_path": "quality-pulse-evidence/useful.json",
        }
        _profile, result = self.authoritative(observations=[raw])
        authoritative = authoritative_bytes(result).decode()
        markdown = render_markdown(result)
        self.assertNotIn(secret, authoritative)
        self.assertNotIn(secret, markdown)
        item = result["observations"][0]
        self.assertEqual(
            item["raw_telemetry"]["safe_path"],
            "quality-pulse-evidence/useful.json",
        )
        self.assertIn("quality-pulse-evidence/useful.json", authoritative)

    def case_render_valid(self):
        _profile, result = self.authoritative()
        markdown = render_markdown(result)
        self.assertTrue(markdown.startswith("# Inspection Result\n"))
        expected = load_json(FIXTURES / "baseplate-derived" / "expected.json")
        self.assertEqual(
            "sha256:" + hashlib.sha256(markdown.encode()).hexdigest(),
            expected["expected_markdown_sha256"],
        )

    def case_render_invalid(self):
        _profile, result = self.authoritative()
        result["stable_projection_digest"] = "sha256:" + "0" * 64
        self.assert_reason(
            "authoritative_digest_mismatch", lambda: render_markdown(result),
        )

    def case_render_order(self):
        _profile, result = self.authoritative()
        markdown = render_markdown(result)
        positions = [markdown.index(f"`{x['observation_id']}`") for x in result["observations"]]
        self.assertEqual(positions, sorted(positions))

    def case_generic(self):
        _profile, result = self.authoritative("live-wires-generic")
        self.assertEqual(result["observations"][0]["classification"], "live_wires_actionable")
        text = json.dumps(result)
        self.assertNotIn("baseplate", text.lower())
        self.assertNotIn("assembly", text.lower())

    def case_generic_unknown(self):
        raw = self.observations("live-wires-generic")[0]
        raw["rule_id"] = "unknown-rule"
        item = classify_observations(self.profile("live-wires-generic"), [raw])[0]
        self.assertEqual((item["classification"], item["actionable"]), ("unknown", True))

    def case_catalog_provenance(self):
        source = json.loads(LIVE_WIRES_CATALOG.read_text())
        projection = {
            key: source[key]
            for key in source["canonical_projection"]["included_fields"]
        }
        source_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                projection, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            ).encode()
        ).hexdigest()
        self.assertEqual(
            source_digest,
            "sha256:d674f80f25e2b12b72b8144c8b01ad27e67b164143c0d281c229e5090581ac94",
        )
        source_by_id = {x["rule_id"]: x for x in source["rules"]}
        for family in ("baseplate-derived", "live-wires-generic"):
            catalog = next(
                x for x in self.document(family)["catalogs"]
                if x["catalog_id"] == "live-wires-quality-rules"
            )
            self.assertEqual(catalog["schema_version"], source["schema_version"])
            self.assertEqual(catalog["catalog_version"], source["catalog_version"])
            for rule in catalog["rules"]:
                canonical = source_by_id[rule["rule_id"]]
                self.assertEqual(
                    rule["definition"]["source_rule_digest"], compact_digest(canonical),
                )
                self.assertEqual(
                    rule["definition"]["source_catalog_digest"], source_digest,
                )
            kernel_projection = {
                key: catalog[key]
                for key in (
                    "catalog_id", "schema_version", "catalog_version",
                    "source_reference", "rules", "metrics",
                )
            }
            self.assertEqual(catalog["content_digest"], digest(kernel_projection))

    def case_expected_projection(self, family):
        _profile, result = self.authoritative(family)
        expected = load_json(FIXTURES / family / "expected.json")
        self.assertEqual(
            result["stable_projection_digest"],
            expected["expected_stable_projection_digest"],
        )
        self.assertEqual(
            "sha256:" + hashlib.sha256(render_markdown(result).encode()).hexdigest(),
            expected["expected_markdown_sha256"],
        )
        if family == "baseplate-derived":
            self.assertIs(expected["real_run_evidence"], False)
            self.assertEqual(expected["closure_authority"], "none")
            self.assertNotIn("closure_authority", result)
            self.assertEqual(
                [item["status"] for item in result["lane_receipts"]],
                expected["expected_lane_statuses"],
            )
            self.assertEqual(
                [
                    (
                        "unknown_fail_closed"
                        if item["classification"] == "unknown"
                        else item["classification"]
                    )
                    for item in result["observations"]
                ],
                expected["expected_bucket_order"],
            )
        validate_authoritative_result(result)


CASES = {
    "QP-PROFILE-001": lambda self: self.case_profile_valid(),
    "QP-PROFILE-002": lambda self: self.case_profile_version(),
    "QP-PROFILE-003": lambda self: self.case_duplicate_key(),
    "QP-PROFILE-004": lambda self: self.case_unknown_field(),
    "QP-PROFILE-005": lambda self: self.case_missing_reference(),
    "QP-PROFILE-006": lambda self: self.case_catalog_digest(),
    "QP-PROFILE-007": lambda self: self.case_catalog_identity(),
    "QP-PATH-001": lambda self: self.case_exact_design_path(),
    "QP-PATH-002": lambda self: self.case_baseplate_path(),
    "QP-PATH-003": lambda self: self.case_unknown_path(),
    "QP-PATH-004": lambda self: self.case_absolute_path(),
    "QP-PATH-005": lambda self: self.case_parent_traversal(),
    "QP-PATH-006": lambda self: self.case_symlink_escape(),
    "QP-CLASS-001": lambda self: self.case_classifications(),
    "QP-CLASS-002": lambda self: self.case_exact_design_path(),
    "QP-CLASS-003": lambda self: self.case_classifications(),
    "QP-CLASS-004": lambda self: self.case_classifications(),
    "QP-CLASS-005": lambda self: self.case_missing_wrapper_decision(),
    "QP-LANE-001": lambda self: self.case_lane_available(),
    "QP-LANE-002": lambda self: self.case_lane_unavailable_fallback(),
    "QP-LANE-003": lambda self: self.case_lane_failed_fallback(),
    "QP-LANE-004": lambda self: self.case_lane_skipped(),
    "QP-LANE-005": lambda self: self.case_unpinned(),
    "QP-LANE-006": lambda self: self.case_untrusted_execution(),
    "QP-LANE-007": lambda self: self.case_repository_attestation(),
    "QP-LANE-008": lambda self: self.case_attestation_root(),
    "QP-LANE-009": lambda self: self.case_attestation_identity(),
    "QP-LANE-010": lambda self: self.case_profile_mutation(),
    "QP-DETERMINISM-001": lambda self: self.case_stable_replay(),
    "QP-DETERMINISM-002": lambda self: self.case_single_delta(),
    "QP-DETERMINISM-003": lambda self: self.case_path_order(),
    "QP-DETERMINISM-004": lambda self: self.case_volatile_excluded(),
    "QP-TREND-001": lambda self: self.case_trend_compatible(),
    "QP-TREND-002": lambda self: self.case_trend_discontinuity("schema_version"),
    "QP-TREND-003": lambda self: self.case_trend_discontinuity("profile"),
    "QP-TREND-004": lambda self: self.case_trend_discontinuity("metric_definitions"),
    "QP-TREND-005": lambda self: self.case_trend_discontinuity("tool_identities"),
    "QP-REDACTION-001": lambda self: self.case_redaction("credential"),
    "QP-REDACTION-002": lambda self: self.case_redaction("private"),
    "QP-REDACTION-003": lambda self: self.case_redaction("dsn"),
    "QP-REDACTION-004": lambda self: self.case_redaction("credential"),
    "QP-RENDER-001": lambda self: self.case_render_valid(),
    "QP-RENDER-002": lambda self: self.case_render_invalid(),
    "QP-RENDER-003": lambda self: self.case_render_order(),
    "QP-GENERIC-001": lambda self: self.case_generic(),
    "QP-GENERIC-002": lambda self: self.case_generic_unknown(),
    "QP-CATALOG-001": lambda self: self.case_catalog_provenance(),
    "QP-EXPECTED-001": lambda self: self.case_expected_projection("baseplate-derived"),
    "QP-EXPECTED-002": lambda self: self.case_expected_projection("live-wires-generic"),
}


def _install_case(case_id, callback):
    def test(self):
        callback(self)

    test.__name__ = "test_" + case_id.replace("-", "_")
    setattr(QualityPulseContract, test.__name__, test)


for _case_id, _callback in CASES.items():
    _install_case(_case_id, _callback)
