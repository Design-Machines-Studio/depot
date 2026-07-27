import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests import KERNEL_REFERENCES

from workflow_kernel import cli as kernel_cli
from workflow_kernel import publication as kernel_publication
from workflow_kernel.cli import command_inspection_publish
from workflow_kernel.inspection import (
    FIXED_EXECUTION_ENV, InspectionError, authoritative_bytes, build_authoritative_result,
    classify_observations, compare_trends, execute_inspection_lanes,
    finalize_authoritative_result, load_host_attestation,
    load_host_publication_authority_key, load_inspection_profile,
    normalize_owned_path,
    render_markdown, stable_projection, validate_authoritative_result,
    validate_inspection_profile, validate_published_outputs,
    validate_result_policy,
)
from workflow_kernel.receipts import _canonical_bytes
COMMIT = "a" * 40
PUBLICATION_KEY = b"quality-pulse-fixture-publication-key-v1"
ATTACKER_KEY = b"attacker-controlled-publication-key-v1"
_build_authoritative_result = build_authoritative_result


def result_policy_document():
    return {
        "schema_version": 1,
        "policy_id": "dm-review-quality-pulse",
        "policy_version": "1.0.0",
        "completion_labels": {
            "blocked": "blocked",
            "gaps": "complete_with_gaps",
            "findings": "complete_with_findings",
            "clean": "complete",
        },
        "lane_gap_statuses": ["unavailable", "failed"],
        "lane_blocker_statuses": ["unavailable", "failed"],
        "observation_blocker_evidence_statuses": [
            "unavailable", "failed", "skipped",
        ],
        "classified_reason_code": "classified",
    }


def build_authoritative_result(*args, **kwargs):
    kwargs.setdefault("publication_authority_key", PUBLICATION_KEY)
    if len(args) < 2 and "result_policy" not in kwargs:
        kwargs["result_policy"] = validate_result_policy(
            result_policy_document(),
        )
    return _build_authoritative_result(*args, **kwargs)


def publication_state_digest(result, status):
    return "sha256:" + hashlib.sha256(_canonical_bytes({
        "schema_version": 1,
        "stable_projection_digest": result["stable_projection_digest"],
        "publication_status": status,
    })).hexdigest()


def catalog_digest(catalog):
    projection = {
        key: catalog[key] for key in (
            "catalog_id", "schema_version", "catalog_version",
            "source_reference", "rules", "metrics",
        )
    }
    return "sha256:" + hashlib.sha256(_canonical_bytes(projection)).hexdigest()


def profile_document():
    catalog = {
        "catalog_id": "generic-quality",
        "schema_version": 1,
        "catalog_version": "1.0.0",
        "source_reference": "catalogs/generic-quality.json",
        "content_digest": "",
        "rules": [{
            "rule_id": "bounded-count",
            "definition": {"operator": "maximum", "unit": "count"},
        }],
        "metrics": [{
            "metric_id": "item-count",
            "definition": {"value_type": "integer", "unit": "count"},
        }],
    }
    catalog["content_digest"] = catalog_digest(catalog)
    digest = catalog["content_digest"]
    return {
        "schema_version": 1,
        "profile_id": "repository-quality",
        "profile_version": "1.0.0",
        "repository": {"scope_paths": ["src"]},
        "catalogs": [catalog],
        "surfaces": [{
            "surface_id": "primary-source", "paths": ["src/item.txt"],
        }],
        "metrics": [{
            "metric_id": "item-count", "catalog_id": "generic-quality",
            "catalog_version": "1.0.0", "catalog_digest": digest,
        }],
        "rules": [{
            "rule_id": "bounded-count", "catalog_id": "generic-quality",
            "catalog_version": "1.0.0", "catalog_digest": digest,
            "metric_ids": ["item-count"], "surface_ids": ["primary-source"],
        }],
        "lanes": [
            {
                "lane_id": "primary", "execution_type": "docker",
                "argv": [
                    "docker", "run", "--rm",
                    "example/tool@sha256:" + "1" * 64,
                ],
                "tool_identity": "docker:27.5.1",
                "image_identity": "example/tool@sha256:" + "1" * 64,
                "service_identity": None, "plugin_version": "1.2.0",
                "timeout_seconds": 30, "primary_lane_id": None,
                "evidence_paths": ["output/primary.json"],
            },
            {
                "lane_id": "fallback", "execution_type": "docker",
                "argv": [
                    "docker", "run", "--rm",
                    "example/fallback@sha256:" + "2" * 64,
                ],
                "tool_identity": "docker:27.5.1",
                "image_identity": "example/fallback@sha256:" + "2" * 64,
                "service_identity": None, "plugin_version": "1.2.0",
                "timeout_seconds": 30, "primary_lane_id": "primary",
                "evidence_paths": ["output/fallback.json"],
            },
        ],
        "classifications": [{
            "classification_id": "within-limit",
            "rule_ids": ["bounded-count"], "metric_ids": ["item-count"],
            "surface_ids": ["primary-source"], "confidence": "high",
            "actionability": "informational",
        }],
        "outputs": {
            "authoritative_json": "output/result.json",
            "markdown": "output/result.md",
        },
        "trend_compatibility": {
            "schema_version": 1,
            "required_identity_fields": [
                "profile", "result_policy", "metric_definitions",
                "tool_identities",
            ],
        },
    }


def observation(**changes):
    value = {
        "schema_version": 1, "observation_id": "observation-1",
        "surface_id": "primary-source", "rule_id": "bounded-count",
        "metric_id": "item-count", "path": "src/item.txt",
        "classification_id": "within-limit", "evidence_status": "available",
        "evidence_references": ["output/primary.json"],
        "raw_telemetry": {"value": 4},
    }
    value.update(changes)
    return value


def receipt_for_observations(observations):
    envelope = {
        "schema_version": 1, "lane_id": "primary",
        "observations": observations,
    }
    return {
        "lane_id": "primary", "status": "available",
        "reason_code": "completed", "primary_lane_id": None,
        "argv_identity": "sha256:" + "1" * 64,
        "tool_identity": "docker:27.5.1",
        "image_identity": "example/tool@sha256:" + "1" * 64,
        "service_identity": None, "plugin_version": "1.2.0",
        "timeout_seconds": 30,
        "started_at": "2026-07-27T00:00:00Z",
        "finished_at": "2026-07-27T00:00:01Z",
        "exit_code": 0, "evidence_references": ["output/primary.json"],
        "evidence_digest": (
            "sha256:" + hashlib.sha256(_canonical_bytes(envelope)).hexdigest()
        ),
        "observation_ids": [item["observation_id"] for item in observations],
        "stdout": "", "stderr": "", "redacted_values": 0,
    }


def attestation(profile, **changes):
    value = {
        "schema_version": 1,
        "repository_root": str(profile.repository_root),
        "profile_path": profile.profile_path,
        "profile_digest": profile.digest,
        "source": "git", "ref": "refs/heads/test", "commit": COMMIT,
        "dirty": False, "operator_authorization_event_id": "operator-event-1",
        "purpose": "scheduled-quality-pulse",
    }
    value.update(changes)
    return value


class FakeAdapter:
    def __init__(self, returncodes, observations=None):
        self.returncodes = list(returncodes)
        self.observations = [] if observations is None else observations
        self.calls = []

    def run(self, argv, *, cwd, env, timeout):
        self.calls.append({
            "argv": argv, "cwd": cwd, "env": env, "timeout": timeout,
        })
        returncode = self.returncodes.pop(0)
        if returncode == 0:
            mount = next(
                item for item in argv
                if item.startswith("type=bind,source=")
                and item.endswith(",target=/inspection-evidence")
            )
            evidence_root = mount.split(",target=", 1)[0].split("source=", 1)[1]
            Path(evidence_root, "observations.json").write_text(json.dumps({
                "schema_version": 1,
                "lane_id": (
                    "fallback" if "example/fallback@" in " ".join(argv)
                    else "fallback-later" if "example/later@" in " ".join(argv)
                    else "primary"
                ),
                "observations": self.observations,
            }))
        return SimpleNamespace(returncode=returncode, stdout="", stderr="")


class NoEvidenceAdapter:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, cwd, env, timeout):
        self.calls.append({
            "argv": argv, "cwd": cwd, "env": env, "timeout": timeout,
        })
        return SimpleNamespace(returncode=0, stdout="", stderr="")


class RaisingAdapter:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, cwd, env, timeout):
        self.calls.append(argv)
        raise PermissionError("fixture")


class QualityPulseKernelTests(unittest.TestCase):
    def repository(self, root):
        repository = root / "repository"
        (repository / "src").mkdir(parents=True)
        (repository / "src" / "item.txt").write_text("fixture\n")
        return repository

    def write_profile(self, repository, value=None):
        path = repository / "profile.json"
        path.write_text(json.dumps(
            profile_document() if value is None else value,
            sort_keys=True,
        ))
        return path

    def load_profile(self, root):
        repository = self.repository(root)
        path = self.write_profile(repository)
        return repository, path, load_inspection_profile(path, repository)

    def assert_reason(self, context, reason):
        with self.assertRaises(InspectionError) as raised:
            context()
        self.assertEqual(raised.exception.reason_code, reason)

    def test_profile_is_closed_exact_versioned_deterministic_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = self.repository(root)
            value = profile_document()
            first = validate_inspection_profile(value, repository)
            second = validate_inspection_profile(
                dict(reversed(list(value.items()))), repository,
            )
            self.assertEqual(first.digest, second.digest)
            self.assertEqual(first.canonical_bytes, second.canonical_bytes)
            with self.assertRaises(TypeError):
                first.document["profile_id"] = "changed"

            for mutation, reason in (
                ({**value, "schema_version": 2}, "unsupported_schema_version"),
                ({**value, "schema_version": True}, "unsupported_schema_version"),
                ({**value, "trusted": True}, "unknown_key"),
                ({**value, "profile_version": True}, "wrong_type"),
            ):
                self.assert_reason(
                    lambda mutation=mutation: validate_inspection_profile(
                        mutation, repository,
                    ),
                    reason,
                )
            aliased_outputs = profile_document()
            aliased_outputs["outputs"]["markdown"] = (
                aliased_outputs["outputs"]["authoritative_json"]
            )
            self.assert_reason(
                lambda: validate_inspection_profile(
                    aliased_outputs, repository,
                ),
                "invalid_outputs",
            )

    def test_duplicate_json_key_and_owned_path_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(Path(directory))
            path = repository / "profile.json"
            path.write_text('{"schema_version":1,"schema_version":1}')
            self.assert_reason(
                lambda: load_inspection_profile(path, repository),
                "duplicate_json_key",
            )
            for unsafe, reason in (
                ("", "invalid_repository_path"),
                ("/tmp/x", "invalid_repository_path"),
                ("../x", "invalid_repository_path"),
                ("a\0b", "invalid_repository_path"),
            ):
                self.assert_reason(
                    lambda unsafe=unsafe: normalize_owned_path(repository, unsafe),
                    reason,
                )
            outside = Path(directory) / "outside"
            outside.mkdir()
            (repository / "escape").symlink_to(outside, target_is_directory=True)
            self.assert_reason(
                lambda: normalize_owned_path(repository, "escape/file"),
                "repository_path_escape",
            )

    def test_catalog_and_lane_authority_fail_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = self.repository(root)
            value = profile_document()
            value["catalogs"][0]["content_digest"] = "sha256:" + "0" * 64
            self.assert_reason(
                lambda: validate_inspection_profile(value, repository),
                "catalog_digest_mismatch",
            )
            for argv, reason in (
                (["python3", "scan.py"], "untrusted_executable"),
                (["docker", "run", "--env", "TOKEN=x", "image:1"], "shell_or_environment_authority"),
                (["docker", "run", "-eTOKEN=x", "image:1"], "shell_or_environment_authority"),
                (["docker", "run", "--privileged", "image:1"], "shell_or_environment_authority"),
                (["docker", "run", "--mount", "type=bind,src=.,dst=/repo", "image:1"], "shell_or_environment_authority"),
                (["docker", "run", "--pid=host", "image:1"], "shell_or_environment_authority"),
                (["docker", "run", "--device=/dev/null", "image:1"], "shell_or_environment_authority"),
                (["docker", "run", "--entrypoint=/bin/true", "image:1"], "shell_or_environment_authority"),
                (["docker", "run", "image:latest"], "unpinned_image_identity"),
                (["docker", "run", "image:1.2.3"], "unpinned_image_identity"),
            ):
                value = profile_document()
                value["lanes"][0]["argv"] = argv
                if reason == "unpinned_image_identity":
                    value["lanes"][0]["image_identity"] = argv[-1]
                self.assert_reason(
                    lambda value=value: validate_inspection_profile(value, repository),
                    reason,
                )
            value = profile_document()
            value["lanes"][0]["argv"][-1] = "example/other@sha256:" + "3" * 64
            self.assert_reason(
                lambda: validate_inspection_profile(value, repository),
                "lane_identity_mismatch",
            )
            value = profile_document()
            value["lanes"][0]["argv"] = [
                "docker", "run", "--rm",
                "example/other@sha256:" + "3" * 64,
                value["lanes"][0]["image_identity"],
            ]
            self.assert_reason(
                lambda: validate_inspection_profile(value, repository),
                "lane_identity_mismatch",
            )
            (repository / "compose.yml").write_text("services:\n  scanner: {}\n")
            value = profile_document()
            value["lanes"][0].update({
                "execution_type": "compose",
                "argv": [
                    "docker", "compose", "-f", "compose.yml", "run", "other",
                    "scanner",
                ],
                "image_identity": None,
                "service_identity": "scanner@sha256:" + "4" * 64,
            })
            self.assert_reason(
                lambda: validate_inspection_profile(value, repository),
                "unknown_execution_type",
            )
            value = profile_document()
            value["catalogs"] = [True]
            self.assert_reason(
                lambda: validate_inspection_profile(value, repository),
                "invalid_collection_item",
            )

    def test_unknown_observations_are_actionable_and_secrets_are_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(Path(directory))
            profile = validate_inspection_profile(profile_document(), repository)
            result = classify_observations(profile, [observation(
                surface_id="unknown-surface",
                raw_telemetry={"value": 7, "token": "ghp_fixtureSecret123"},
            )])[0]
            self.assertTrue(result["actionable"])
            self.assertEqual(result["classification"], "unknown")
            self.assertEqual(result["reason_code"], "unknown_surface")
            self.assertEqual(result["raw_telemetry"]["token"], "[REDACTED]")
            self.assertEqual(result["evidence_status"], "available")
            malformed = classify_observations(profile, [observation(
                evidence_references=["../outside"],
            )])[0]
            self.assertTrue(malformed["actionable"])
            self.assertEqual(malformed["evidence_references"], [])
            raw_observations = [observation(
                raw_telemetry={
                    "token": "ghp_fixtureSecret123",
                    "safe_path": "output/primary.json",
                },
            )]
            authoritative = build_authoritative_result(
                profile,
                source="git",
                ref="refs/heads/conformance",
                commit=COMMIT,
                dirty=False,
                observations=raw_observations,
                lane_receipts=[receipt_for_observations(raw_observations)],
                invocation={
                    "started_at": "2026-07-27T00:00:00Z",
                    "finished_at": "2026-07-27T00:00:00Z",
                    "operator_authorization_event_id": "approved",
                    "purpose": "quality-pulse",
                    "selected_lane_ids": ["primary"],
                },
            )
            encoded = authoritative_bytes(
                authoritative,
                publication_authority_key=PUBLICATION_KEY,
            ).decode()
            markdown = render_markdown(
                authoritative,
                publication_authority_key=PUBLICATION_KEY,
            )
            self.assertNotIn("ghp_fixtureSecret123", encoded)
            self.assertNotIn("ghp_fixtureSecret123", markdown)
            self.assertIn("output/primary.json", encoded)

    def test_authoritative_profile_path_uses_repository_path_grammar(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(Path(directory))
            profile = validate_inspection_profile(
                profile_document(),
                repository,
                profile_path=".dm-review/quality-pulse.json",
            )
            result = build_authoritative_result(
                profile,
                source="git",
                ref="refs/heads/conformance",
                commit="a" * 40,
                dirty=False,
                observations=[],
                lane_receipts=[],
                invocation={
                    "started_at": "2026-07-27T00:00:00Z",
                    "finished_at": "2026-07-27T00:00:00Z",
                    "operator_authorization_event_id": "approved",
                    "purpose": "quality-pulse",
                    "selected_lane_ids": [],
                },
            )
            self.assertEqual(
                result["profile"]["profile_path"],
                ".dm-review/quality-pulse.json",
            )

    def test_every_attestation_binding_and_repository_control_fail_before_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository, path, profile = self.load_profile(root)
            bindings = {
                "repository_root": str(root / "other"),
                "profile_path": "other.json",
                "profile_digest": "sha256:" + "0" * 64,
                "source": "other", "ref": "refs/heads/other",
                "commit": "b" * 40, "dirty": True, "purpose": "other-purpose",
                "operator_authorization_event_id": "different-event",
            }
            for field, changed in bindings.items():
                fake = FakeAdapter([0])
                self.assert_reason(
                    lambda field=field, changed=changed, fake=fake:
                    execute_inspection_lanes(
                        profile, ["primary"],
                        attestation(profile, **{field: changed}),
                        source="git", ref="refs/heads/test", commit=COMMIT,
                        dirty=False, purpose="scheduled-quality-pulse",
                        operator_authorization_event_id="operator-event-1",
                        adapter=fake,
                    ),
                    (
                        "profile_digest_mismatch"
                        if field == "profile_digest"
                        else "attestation_binding_mismatch"
                    ),
                )
                self.assertEqual(fake.calls, [])
            host_file = repository / "attestation.json"
            host_file.write_text(json.dumps(attestation(profile)))
            self.assert_reason(
                lambda: load_host_attestation(host_file, repository),
                "repository_controlled_attestation",
            )
            with mock.patch(
                "workflow_kernel.inspection."
                "_host_publication_authority_key_path",
                return_value=host_file.resolve(),
            ):
                self.assert_reason(
                    lambda: load_host_publication_authority_key(repository),
                    "untrusted_publication_authority_key",
                )
            publication_key = root / "publication.key"
            publication_key.write_bytes(PUBLICATION_KEY)
            publication_key.chmod(0o600)
            with mock.patch(
                "workflow_kernel.inspection."
                "_host_publication_authority_key_path",
                return_value=publication_key.resolve(),
            ):
                self.assertEqual(
                    load_host_publication_authority_key(repository),
                    PUBLICATION_KEY,
                )
            publication_key_link = root / "publication-link.key"
            publication_key_link.symlink_to(publication_key)
            with mock.patch(
                "workflow_kernel.inspection."
                "_host_publication_authority_key_path",
                return_value=publication_key_link,
            ):
                self.assert_reason(
                    lambda: load_host_publication_authority_key(repository),
                    "untrusted_publication_authority_key",
                )
            publication_key.chmod(0o644)
            with mock.patch(
                "workflow_kernel.inspection."
                "_host_publication_authority_key_path",
                return_value=publication_key.resolve(),
            ):
                self.assert_reason(
                    lambda: load_host_publication_authority_key(repository),
                    "untrusted_publication_authority_key",
                )
            value = profile_document()
            value["trusted"] = True
            self.assert_reason(
                lambda: validate_inspection_profile(value, repository),
                "unknown_key",
            )

    def test_opt_in_catalog_decision_is_complete_and_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(Path(directory))

            def bind_catalog(value):
                catalog = value["catalogs"][0]
                catalog["content_digest"] = catalog_digest(catalog)
                for binding in value["metrics"] + value["rules"]:
                    binding["catalog_digest"] = catalog["content_digest"]

            missing = profile_document()
            missing["catalogs"][0]["rules"][0]["definition"].update({
                "alternative_decisions": ["keep-default", "use-wrapper"],
            })
            bind_catalog(missing)
            self.assert_reason(
                lambda: validate_inspection_profile(missing, repository),
                "missing_profile_decision",
            )

            invalid = copy.deepcopy(missing)
            invalid["catalogs"][0]["rules"][0]["definition"][
                "profile_decision"
            ] = "unlisted-decision"
            bind_catalog(invalid)
            self.assert_reason(
                lambda: validate_inspection_profile(invalid, repository),
                "missing_profile_decision",
            )

            selected = copy.deepcopy(missing)
            selected["catalogs"][0]["rules"][0]["definition"][
                "profile_decision"
            ] = "use-wrapper"
            bind_catalog(selected)
            profile = validate_inspection_profile(selected, repository)
            self.assertEqual(
                profile.document["catalogs"][0]["rules"][0]["definition"][
                    "profile_decision"
                ],
                "use-wrapper",
            )

    def test_post_validation_mutation_is_detected_without_adapter_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, path, profile = self.load_profile(root)
            fake = FakeAdapter([0])

            def mutate():
                value = profile_document()
                value["profile_id"] = "changed-profile"
                path.write_text(json.dumps(value))

            self.assert_reason(
                lambda: execute_inspection_lanes(
                    profile, ["primary"], attestation(profile),
                    source="git", ref="refs/heads/test", commit=COMMIT,
                    dirty=False, purpose="scheduled-quality-pulse",
                    operator_authorization_event_id="operator-event-1",
                    adapter=fake, pre_admission_hook=mutate,
                ),
                "profile_digest_mismatch",
            )
            self.assertEqual(fake.calls, [])

    def test_same_size_restored_mtime_mutation_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, path, profile = self.load_profile(root)
            original = path.read_bytes()
            observed = path.stat()
            replacement = bytearray(original)
            replacement[-2] = ord(" ")
            fake = FakeAdapter([0])

            def mutate():
                path.write_bytes(bytes(replacement))
                os.utime(
                    path, ns=(observed.st_atime_ns, observed.st_mtime_ns),
                )

            self.assert_reason(
                lambda: execute_inspection_lanes(
                    profile, ["primary"], attestation(profile),
                    source="git", ref="refs/heads/test", commit=COMMIT,
                    dirty=False, purpose="scheduled-quality-pulse",
                    operator_authorization_event_id="operator-event-1",
                    adapter=fake, pre_admission_hook=mutate,
                ),
                "profile_digest_mismatch",
            )
            self.assertEqual(fake.calls, [])

    def test_exact_execution_boundary_and_fallback_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository, _path, profile = self.load_profile(root)
            fake = FakeAdapter([125, 0])
            ticks = iter([
                "2026-07-27T00:00:00Z", "2026-07-27T00:00:01Z",
                "2026-07-27T00:00:02Z", "2026-07-27T00:00:03Z",
            ])
            receipts = execute_inspection_lanes(
                profile, ["primary"], attestation(profile),
                source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, purpose="scheduled-quality-pulse",
                operator_authorization_event_id="operator-event-1",
                adapter=fake, clock=lambda: next(ticks),
            )
            self.assertEqual([item["status"] for item in receipts], [
                "unavailable", "fallback",
            ])
            self.assertEqual(receipts[1]["primary_lane_id"], "primary")
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(fake.calls[0]["cwd"], repository.resolve())
            self.assertEqual(fake.calls[0]["env"], FIXED_EXECUTION_ENV)
            self.assertEqual(
                fake.calls[0]["env"]["PATH"],
                "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            )
            self.assertEqual(fake.calls[0]["timeout"], 30)
            self.assertEqual(fake.calls[0]["argv"][:2], ("docker", "run"))

            successful = FakeAdapter([0])
            ticks = iter([
                "2026-07-27T00:00:00Z", "2026-07-27T00:00:01Z",
                "2026-07-27T00:00:02Z", "2026-07-27T00:00:03Z",
            ])
            receipts = execute_inspection_lanes(
                profile, ["primary"], attestation(profile),
                source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, purpose="scheduled-quality-pulse",
                operator_authorization_event_id="operator-event-1",
                adapter=successful, clock=lambda: next(ticks),
            )
            self.assertEqual([item["status"] for item in receipts], [
                "available", "skipped",
            ])
            self.assertEqual(len(successful.calls), 1)

    def test_lane_success_requires_fresh_bound_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository, _path, profile = self.load_profile(root)
            missing = NoEvidenceAdapter()
            ticks = iter([
                "2026-07-27T00:00:00Z", "2026-07-27T00:00:01Z",
                "2026-07-27T00:00:02Z", "2026-07-27T00:00:03Z",
            ])
            receipts = execute_inspection_lanes(
                profile, ["primary"], attestation(profile),
                source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, purpose="scheduled-quality-pulse",
                operator_authorization_event_id="operator-event-1",
                adapter=missing, clock=lambda: next(ticks),
            )
            self.assertEqual(receipts[0]["status"], "failed")
            self.assertEqual(
                receipts[0]["reason_code"], "missing_lane_evidence",
            )
            actual_argv = missing.calls[0]["argv"]
            self.assertIn("--network=none", actual_argv)
            self.assertIn("--read-only", actual_argv)
            self.assertTrue(any(
                item.startswith(
                    f"type=bind,source={repository.resolve()},"
                    "target=/workspace,readonly"
                )
                for item in actual_argv
            ))

            raw = [observation(raw_telemetry={"value": 9})]
            producing = FakeAdapter([0], observations=raw)
            ticks = iter([
                "2026-07-27T00:00:00Z", "2026-07-27T00:00:01Z",
                "2026-07-27T00:00:02Z", "2026-07-27T00:00:03Z",
            ])
            receipts, captured = execute_inspection_lanes(
                profile, ["primary"], attestation(profile),
                source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, purpose="scheduled-quality-pulse",
                operator_authorization_event_id="operator-event-1",
                adapter=producing, clock=lambda: next(ticks),
                return_observations=True,
            )
            self.assertEqual(captured, raw)
            self.assertEqual(receipts[0]["observation_ids"], ["observation-1"])
            self.assertRegex(receipts[0]["evidence_digest"], r"^sha256:[0-9a-f]{64}$")

            forged = copy.deepcopy(raw)
            forged[0]["raw_telemetry"]["value"] = 999
            self.assert_reason(
                lambda: build_authoritative_result(
                    profile, source="git", ref="refs/heads/test", commit=COMMIT,
                    dirty=False, observations=forged, lane_receipts=receipts,
                    invocation={
                        "started_at": "2026-07-27T00:00:00Z",
                        "finished_at": "2026-07-27T00:00:01Z",
                        "operator_authorization_event_id": "operator-event-1",
                        "purpose": "scheduled-quality-pulse",
                        "selected_lane_ids": ["primary"],
                    },
                ),
                "unbound_lane_evidence",
            )

            authoritative = build_authoritative_result(
                profile, source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, observations=raw, lane_receipts=receipts,
                invocation={
                    "started_at": "2026-07-27T00:00:00Z",
                    "finished_at": "2026-07-27T00:00:01Z",
                    "operator_authorization_event_id": "operator-event-1",
                    "purpose": "scheduled-quality-pulse",
                    "selected_lane_ids": ["primary"],
                },
            )
            substituted = copy.deepcopy(authoritative)
            substituted["observations"][0]["raw_telemetry"]["value"] = 999
            substituted["lane_receipts"][0][
                "classified_observations_digest"
            ] = (
                "sha256:" + hashlib.sha256(_canonical_bytes(
                    substituted["observations"],
                )).hexdigest()
            )
            substituted["stable_projection_digest"] = (
                "sha256:" + hashlib.sha256(
                    _canonical_bytes(stable_projection(substituted))
                ).hexdigest()
            )
            self.assert_reason(
                lambda: validate_authoritative_result(substituted),
                "unbound_lane_evidence",
            )

            unknown_raw = [observation(metric_id="not-declared")]
            relabeled = build_authoritative_result(
                profile, source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, observations=unknown_raw,
                lane_receipts=[receipt_for_observations(unknown_raw)],
                invocation={
                    "started_at": "2026-07-27T00:00:00Z",
                    "finished_at": "2026-07-27T00:00:01Z",
                    "operator_authorization_event_id": "operator-event-1",
                    "purpose": "scheduled-quality-pulse",
                    "selected_lane_ids": ["primary"],
                },
            )
            relabeled["observations"][0].update({
                "classification": "within-limit",
                "confidence": "high",
                "actionable": False,
                "reason_code": "classified",
                "evidence_references": ["output/primary.json"],
            })
            relabeled["lane_receipts"][0][
                "classified_observations_digest"
            ] = (
                "sha256:" + hashlib.sha256(_canonical_bytes(
                    relabeled["observations"],
                )).hexdigest()
            )
            relabeled["stable_projection_digest"] = (
                "sha256:" + hashlib.sha256(
                    _canonical_bytes(stable_projection(relabeled))
                ).hexdigest()
            )
            self.assert_reason(
                lambda: validate_authoritative_result(relabeled),
                "unbound_lane_evidence",
            )

            forged_baseline = copy.deepcopy(authoritative)
            replacement_digest = "sha256:" + "f" * 64
            forged_baseline["profile"]["profile_digest"] = replacement_digest
            forged_baseline["compatibility_identity"]["profile"][
                "profile_digest"
            ] = replacement_digest
            forged_baseline["stable_projection_digest"] = (
                "sha256:" + hashlib.sha256(
                    _canonical_bytes(stable_projection(forged_baseline))
                ).hexdigest()
            )
            self.assert_reason(
                lambda: compare_trends(
                    authoritative, forged_baseline,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                "invalid_authoritative_profile",
            )

    def test_oserror_receipt_and_later_fallback_skip_are_structured(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, _path, profile = self.load_profile(root)
            raising = RaisingAdapter()
            ticks = iter([
                "2026-07-27T00:00:00Z", "2026-07-27T00:00:01Z",
                "2026-07-27T00:00:02Z", "2026-07-27T00:00:03Z",
            ])
            receipts = execute_inspection_lanes(
                profile, ["primary"], attestation(profile),
                source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, purpose="scheduled-quality-pulse",
                operator_authorization_event_id="operator-event-1",
                adapter=raising, clock=lambda: next(ticks),
            )
            self.assertEqual(receipts[0]["status"], "unavailable")
            self.assertEqual(receipts[0]["reason_code"], "runtime_unavailable")

            value = profile_document()
            extra = copy.deepcopy(value["lanes"][1])
            extra["lane_id"] = "fallback-later"
            extra["argv"][-1] = "example/later@sha256:" + "5" * 64
            extra["image_identity"] = extra["argv"][-1]
            value["lanes"].append(extra)
            self.write_profile(profile.repository_root, value)
            profile = load_inspection_profile(
                profile.repository_root / "profile.json", profile.repository_root,
            )
            fake = FakeAdapter([125, 0])
            ticks = iter([
                "2026-07-27T00:00:00Z", "2026-07-27T00:00:01Z",
                "2026-07-27T00:00:02Z", "2026-07-27T00:00:03Z",
            ])
            receipts = execute_inspection_lanes(
                profile, ["primary"], attestation(profile),
                source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, purpose="scheduled-quality-pulse",
                operator_authorization_event_id="operator-event-1",
                adapter=fake, clock=lambda: next(ticks),
            )
            self.assertEqual(
                [item["status"] for item in receipts],
                ["unavailable", "fallback", "skipped"],
            )
            self.assertEqual(
                receipts[2]["reason_code"], "earlier_fallback_available",
            )

    def test_fallback_findings_retain_lane_provenance_and_lower_confidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _repository, _path, profile = self.load_profile(root)
            raw = [observation()]
            fake = FakeAdapter([125, 0], observations=raw)
            ticks = iter([
                "2026-07-27T00:00:00Z", "2026-07-27T00:00:01Z",
                "2026-07-27T00:00:02Z", "2026-07-27T00:00:03Z",
            ])
            receipts, captured = execute_inspection_lanes(
                profile, ["primary"], attestation(profile),
                source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, purpose="scheduled-quality-pulse",
                operator_authorization_event_id="operator-event-1",
                adapter=fake, clock=lambda: next(ticks),
                return_observations=True,
            )
            result = build_authoritative_result(
                profile, source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, observations=captured, lane_receipts=receipts,
                invocation={
                    "started_at": "2026-07-27T00:00:00Z",
                    "finished_at": "2026-07-27T00:00:03Z",
                    "operator_authorization_event_id": "operator-event-1",
                    "purpose": "scheduled-quality-pulse",
                    "selected_lane_ids": ["primary"],
                },
            )
            finding = result["observations"][0]
            self.assertEqual(finding["lane_id"], "fallback")
            self.assertEqual(finding["primary_lane_id"], "primary")
            self.assertEqual(finding["evidence_status"], "available")
            self.assertEqual(finding["lane_status"], "fallback")
            self.assertEqual(finding["evidence_confidence"], "fallback")
            self.assertEqual(finding["confidence"], "medium")
            self.assertEqual(result["completion_state"], "complete_with_gaps")
            self.assertEqual(result["blockers"], [])
            self.assertEqual(
                [item["lane_id"] for item in result["coverage_gaps"]],
                ["primary"],
            )
            self.assertEqual(
                [item["lane_id"] for item in result["requested_identities"]],
                ["primary"],
            )
            self.assertEqual(
                [item["lane_id"] for item in result["actual_identities"]],
                ["fallback"],
            )

    def result(
        self,
        profile,
        value=4,
        publication_key=PUBLICATION_KEY,
        result_policy=None,
    ):
        raw = [observation(raw_telemetry={"value": value})]
        return _build_authoritative_result(
            profile,
            result_policy or validate_result_policy(result_policy_document()),
            source="git", ref="refs/heads/test", commit=COMMIT,
            dirty=False, observations=raw,
            lane_receipts=[receipt_for_observations(raw)], invocation={
                "started_at": "2026-07-27T00:00:00Z",
                "finished_at": "2026-07-27T00:00:01Z",
                "operator_authorization_event_id": "operator-event-1",
                "purpose": "scheduled-quality-pulse",
                "selected_lane_ids": ["primary"],
            },
            publication_authority_key=publication_key,
        )

    def test_authoritative_stability_trends_and_markdown_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(Path(directory))
            profile = validate_inspection_profile(profile_document(), repository)
            current = self.result(profile, 7)
            replay = copy.deepcopy(current)
            replay["invocation"]["started_at"] = "2026-07-28T00:00:00Z"
            self.assertEqual(
                current["stable_projection_digest"],
                replay["stable_projection_digest"],
            )
            self.assertEqual(
                authoritative_bytes(
                    current, publication_authority_key=PUBLICATION_KEY,
                ),
                authoritative_bytes(
                    current, publication_authority_key=PUBLICATION_KEY,
                ),
            )
            baseline = self.result(profile, 4)
            trend = compare_trends(
                current, baseline,
                publication_authority_key=PUBLICATION_KEY,
            )
            self.assertEqual(trend["status"], "compatible")
            self.assertEqual(trend["deltas"][0]["delta"], 3)

            changed = profile_document()
            changed["profile_version"] = "1.1.0"
            changed_profile = validate_inspection_profile(changed, repository)
            changed_baseline = self.result(changed_profile, 4)
            discontinuity = compare_trends(
                current, changed_baseline,
                publication_authority_key=PUBLICATION_KEY,
            )
            self.assertEqual(discontinuity["status"], "baseline_discontinuity")
            self.assertIn("profile", discontinuity["incompatible_identity_fields"])

            changed_policy_document = result_policy_document()
            changed_policy_document["policy_version"] = "1.1.0"
            changed_policy_baseline = self.result(
                profile,
                4,
                result_policy=validate_result_policy(
                    changed_policy_document,
                ),
            )
            policy_discontinuity = compare_trends(
                current,
                changed_policy_baseline,
                publication_authority_key=PUBLICATION_KEY,
            )
            self.assertEqual(
                policy_discontinuity["incompatible_identity_fields"],
                ["result_policy"],
            )

            incompatible_schema = copy.deepcopy(current)
            incompatible_schema["schema_version"] = 2
            self.assertEqual(
                compare_trends(
                    current, incompatible_schema,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                {
                    "schema_version": 1,
                    "status": "baseline_discontinuity",
                    "reason_code": "incompatible_baseline",
                    "incompatible_identity_fields": ["schema_version"],
                    "deltas": [],
                },
            )
            incompatible_draft = finalize_authoritative_result(
                current,
                publication_status="authoritative_json_ready",
                baseline=incompatible_schema,
                publication_authority_key=PUBLICATION_KEY,
            )
            self.assertEqual(
                incompatible_draft["trend_result"]["status"],
                "baseline_discontinuity",
            )
            secret_baseline = copy.deepcopy(incompatible_schema)
            secret_baseline["credential"] = "ghp_fixtureSecret1234567890"
            self.assert_reason(
                lambda: finalize_authoritative_result(
                    current,
                    publication_status="authoritative_json_ready",
                    baseline=secret_baseline,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                "invalid_trend_result",
            )

            rendered = render_markdown(
                current, publication_authority_key=PUBLICATION_KEY,
            )
            self.assertIn("# Inspection Result", rendered)
            self.assertIn("observation-1", rendered)
            for section in (
                "## Summary",
                "## Trend",
                "## Coverage Gaps",
                "## Blockers",
                "## Redaction",
            ):
                self.assertIn(section, rendered)
            self.assertIn("- Informational: **1**", rendered)
            self.assertIn("- None.", rendered)
            with self.assertRaises(InspectionError):
                render_markdown(
                    {"markdown": "# forged"},
                    publication_authority_key=PUBLICATION_KEY,
                )
            tampered = copy.deepcopy(current)
            tampered["repository"]["commit"] = "b" * 40
            with self.assertRaises(InspectionError):
                validate_authoritative_result(
                    tampered, publication_authority_key=PUBLICATION_KEY,
                )
            forged = copy.deepcopy(current)
            forged["observations"][0]["evidence_status"] = "invented"
            forged["stable_projection_digest"] = (
                "sha256:" + hashlib.sha256(
                    _canonical_bytes({
                        "schema_version": forged["schema_version"],
                        "result_type": forged["result_type"],
                        "repository": forged["repository"],
                        "profile": forged["profile"],
                        "compatibility_identity": forged["compatibility_identity"],
                        "observations": forged["observations"],
                        "lane_receipts": forged["lane_receipts"],
                        "redaction": forged["redaction"],
                    })
                ).hexdigest()
            )
            with self.assertRaises(InspectionError):
                render_markdown(
                    forged, publication_authority_key=PUBLICATION_KEY,
                )

    def test_authoritative_receipt_redaction_and_authorization_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(Path(directory))
            profile = validate_inspection_profile(profile_document(), repository)
            current = self.result(profile)
            self.assertEqual(
                current["inspection_id"], "scheduled-quality-pulse",
            )
            self.assertEqual(current["completion_state"], "complete")
            self.assertEqual(
                current["publication_status"], "authoritative_json_ready",
            )
            self.assertEqual(current["trend_result"]["status"], "not_compared")
            compared = finalize_authoritative_result(
                current,
                publication_status="authoritative_json_ready",
                baseline=current,
                publication_authority_key=PUBLICATION_KEY,
            )
            compared_markdown = render_markdown(
                compared, publication_authority_key=PUBLICATION_KEY,
            )
            compared_stable_digest = compared["stable_projection_digest"]
            compared_publication_digest = compared["publication_state_digest"]
            self.assert_reason(
                lambda: finalize_authoritative_result(
                    compared, publication_status="markdown_rendered",
                    publication_authority_key=PUBLICATION_KEY,
                ),
                "publication_action_not_verified",
            )
            output_directory = repository / "output"
            output_directory.mkdir()
            (output_directory / "result.md").write_text("forged\n")
            self.assert_reason(
                lambda: finalize_authoritative_result(
                    compared, publication_status="markdown_rendered",
                    publication_authority_key=PUBLICATION_KEY,
                    publication_repository_root=repository,
                ),
                "publication_action_not_verified",
            )
            (output_directory / "result.md").write_text(compared_markdown)
            rendered = finalize_authoritative_result(
                compared, publication_status="markdown_rendered",
                publication_authority_key=PUBLICATION_KEY,
                publication_repository_root=repository,
            )
            (output_directory / "result.json").write_bytes(
                authoritative_bytes(
                    rendered, publication_authority_key=PUBLICATION_KEY,
                ),
            )
            finalized = finalize_authoritative_result(
                rendered, publication_status="published",
                publication_authority_key=PUBLICATION_KEY,
                publication_repository_root=repository,
            )
            self.assertEqual(finalized["publication_status"], "published")
            self.assertEqual(finalized["trend_result"]["status"], "compatible")
            self.assertNotEqual(
                finalized["stable_projection_digest"],
                current["stable_projection_digest"],
            )
            self.assertEqual(
                finalized["stable_projection_digest"], compared_stable_digest,
            )
            self.assertEqual(
                render_markdown(
                    finalized,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                compared_markdown,
            )
            self.assertNotEqual(
                finalized["publication_state_digest"],
                compared_publication_digest,
            )
            self.assert_reason(
                lambda: finalize_authoritative_result(
                    finalized,
                    publication_status="authoritative_json_ready",
                    publication_authority_key=PUBLICATION_KEY,
                ),
                "invalid_publication_transition",
            )
            self.assert_reason(
                lambda: finalize_authoritative_result(
                    rendered,
                    publication_status="published",
                    baseline=current,
                    publication_authority_key=PUBLICATION_KEY,
                    publication_repository_root=repository,
                ),
                "trend_after_render",
            )
            forged_publication = copy.deepcopy(finalized)
            forged_publication["publication_status"] = "markdown_rendered"
            forged_publication["publication_state_digest"] = publication_state_digest(
                forged_publication, "markdown_rendered",
            )
            self.assert_reason(
                lambda: validate_authoritative_result(
                    forged_publication,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                "invalid_publication_transition",
            )
            rolled_back = copy.deepcopy(finalized)
            rolled_back["publication_status"] = "authoritative_json_ready"
            rolled_back["publication_state_digest"] = publication_state_digest(
                rolled_back, "authoritative_json_ready",
            )
            self.assert_reason(
                lambda: validate_authoritative_result(
                    rolled_back, publication_authority_key=PUBLICATION_KEY,
                ),
                "invalid_publication_transition",
            )
            direct_jump = copy.deepcopy(current)
            direct_jump["publication_status"] = "published"
            direct_jump["publication_state_digest"] = publication_state_digest(
                direct_jump, "published",
            )
            self.assert_reason(
                lambda: validate_authoritative_result(
                    direct_jump, publication_authority_key=PUBLICATION_KEY,
                ),
                "invalid_publication_transition",
            )
            self.assert_reason(
                lambda: validate_authoritative_result(
                    current, publication_authority_key=ATTACKER_KEY,
                ),
                "publication_attestation_binding_mismatch",
            )
            attacker_result = self.result(
                profile, publication_key=ATTACKER_KEY,
            )
            (output_directory / "result.md").write_text(render_markdown(
                attacker_result, publication_authority_key=ATTACKER_KEY,
            ))
            attacker_result = finalize_authoritative_result(
                attacker_result,
                publication_status="markdown_rendered",
                publication_authority_key=ATTACKER_KEY,
                publication_repository_root=repository,
            )
            (output_directory / "result.json").write_bytes(
                authoritative_bytes(
                    attacker_result,
                    publication_authority_key=ATTACKER_KEY,
                ),
            )
            attacker_result = finalize_authoritative_result(
                attacker_result,
                publication_status="published",
                publication_authority_key=ATTACKER_KEY,
                publication_repository_root=repository,
            )
            self.assert_reason(
                lambda: validate_authoritative_result(
                    attacker_result,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                "publication_attestation_binding_mismatch",
            )
            forged_trend = copy.deepcopy(finalized)
            forged_trend["trend_result"]["deltas"][0].update({
                "current": 999, "baseline": 1, "delta": 998,
            })
            forged_trend["stable_projection_digest"] = (
                "sha256:" + hashlib.sha256(
                    _canonical_bytes(stable_projection(forged_trend))
                ).hexdigest()
            )
            self.assert_reason(
                lambda: validate_authoritative_result(
                    forged_trend, publication_authority_key=PUBLICATION_KEY,
                ),
                "invalid_trend_result",
            )
            week_three = self.result(profile, 9)
            week_three = finalize_authoritative_result(
                week_three,
                publication_status="authoritative_json_ready",
                baseline=compared,
                publication_authority_key=PUBLICATION_KEY,
            )
            self.assertEqual(week_three["trend_result"]["status"], "compatible")
            self.assertEqual(week_three["trend_result"]["deltas"][0]["delta"], 5)

            actionable_document = profile_document()
            actionable_document["classifications"][0][
                "actionability"
            ] = "actionable"
            actionable_profile = validate_inspection_profile(
                actionable_document, repository,
            )
            actionable = self.result(actionable_profile)
            self.assertTrue(actionable["observations"][0]["actionable"])
            self.assertEqual(
                actionable["completion_state"], "complete_with_findings",
            )

            failed_raw = [observation(evidence_status="failed")]
            failed_evidence = build_authoritative_result(
                profile, source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, observations=failed_raw,
                lane_receipts=[receipt_for_observations(failed_raw)],
                invocation={
                    "started_at": "2026-07-27T00:00:00Z",
                    "finished_at": "2026-07-27T00:00:01Z",
                    "operator_authorization_event_id": "operator-event-1",
                    "purpose": "scheduled-quality-pulse",
                    "selected_lane_ids": ["primary"],
                },
            )
            failed_finding = failed_evidence["observations"][0]
            self.assertEqual(failed_finding["evidence_status"], "failed")
            self.assertEqual(failed_finding["lane_status"], "available")
            self.assertEqual(
                failed_finding["evidence_confidence"], "unavailable",
            )
            self.assertEqual(failed_evidence["completion_state"], "blocked")
            self.assertEqual(
                failed_evidence["blockers"][0]["reason_code"],
                "evidence_failed",
            )
            skipped_raw = [observation(evidence_status="skipped")]
            skipped_evidence = build_authoritative_result(
                profile, source="git", ref="refs/heads/test", commit=COMMIT,
                dirty=False, observations=skipped_raw,
                lane_receipts=[receipt_for_observations(skipped_raw)],
                invocation={
                    "started_at": "2026-07-27T00:00:00Z",
                    "finished_at": "2026-07-27T00:00:01Z",
                    "operator_authorization_event_id": "operator-event-1",
                    "purpose": "scheduled-quality-pulse",
                    "selected_lane_ids": ["primary"],
                },
            )
            self.assertEqual(skipped_evidence["completion_state"], "blocked")
            self.assertEqual(
                skipped_evidence["blockers"][0]["reason_code"],
                "evidence_skipped",
            )
            fabricated_fallback = [observation(evidence_status="fallback")]
            self.assert_reason(
                lambda: build_authoritative_result(
                    profile, source="git", ref="refs/heads/test", commit=COMMIT,
                    dirty=False, observations=fabricated_fallback,
                    lane_receipts=[
                        receipt_for_observations(fabricated_fallback),
                    ],
                    invocation={
                        "started_at": "2026-07-27T00:00:00Z",
                        "finished_at": "2026-07-27T00:00:01Z",
                        "operator_authorization_event_id": "operator-event-1",
                        "purpose": "scheduled-quality-pulse",
                        "selected_lane_ids": ["primary"],
                    },
                ),
                "unbound_lane_evidence",
            )

            forged_receipt = copy.deepcopy(current)
            forged_receipt["lane_receipts"][0]["exit_code"] = 42
            forged_receipt["lane_receipts"][0]["reason_code"] = "fabricated"
            forged_receipt["stable_projection_digest"] = (
                "sha256:" + hashlib.sha256(
                    _canonical_bytes(stable_projection(forged_receipt))
                ).hexdigest()
            )
            self.assert_reason(
                lambda: validate_authoritative_result(forged_receipt),
                "invalid_lane_receipt",
            )

            forged_redaction = copy.deepcopy(current)
            forged_redaction["redaction"] = {
                "applied": True, "redacted_value_count": 999,
            }
            forged_redaction["stable_projection_digest"] = (
                "sha256:" + hashlib.sha256(
                    _canonical_bytes(stable_projection(forged_redaction))
                ).hexdigest()
            )
            self.assert_reason(
                lambda: validate_authoritative_result(forged_redaction),
                "invalid_redaction_outcome",
            )

            forged_authorization = copy.deepcopy(current)
            forged_authorization["invocation"][
                "operator_authorization_event_id"
            ] = "forged-approval"
            self.assert_reason(
                lambda: validate_authoritative_result(forged_authorization),
                "authoritative_digest_mismatch",
            )

            forged_selection = copy.deepcopy(current)
            forged_selection["invocation"]["selected_lane_ids"] = []
            forged_selection["requested_identities"] = []
            forged_selection["stable_projection_digest"] = (
                "sha256:" + hashlib.sha256(
                    _canonical_bytes(stable_projection(forged_selection))
                ).hexdigest()
            )
            self.assert_reason(
                lambda: validate_authoritative_result(forged_selection),
                "invalid_invocation",
            )

    def test_cli_publish_couples_attestation_to_durable_profile_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository, _path, profile = self.load_profile(root)
            publication_key = root / "publication-authority.key"
            publication_key.write_bytes(PUBLICATION_KEY)
            publication_key.chmod(0o600)
            source = repository / "ready.json"
            source.write_text(json.dumps(self.result(profile)))
            emitted = []
            snapshot_reopen_denied = []
            original_snapshot_write = (
                kernel_publication._write_snapshot_file
            )

            def write_and_probe_snapshot_file(path, encoded):
                original_snapshot_write(path, encoded)
                try:
                    descriptor = os.open(path, os.O_WRONLY)
                except PermissionError:
                    snapshot_reopen_denied.append(Path(path).name)
                else:
                    os.close(descriptor)
                    self.fail("read-only snapshot file reopened writable")

            with (
                mock.patch(
                    "workflow_kernel.inspection."
                    "_host_publication_authority_key_path",
                    return_value=publication_key.resolve(),
                ),
                mock.patch(
                    "workflow_kernel.publication._write_snapshot_file",
                    side_effect=write_and_probe_snapshot_file,
                ),
                mock.patch(
                    "workflow_kernel.cli._emit",
                    side_effect=lambda value: emitted.append(value),
                ),
            ):
                self.assertEqual(command_inspection_publish(SimpleNamespace(
                    repository_root=str(repository),
                    input=str(source),
                )), 0)
            self.assertEqual(emitted[0]["publication_status"], "published")
            markdown_path = repository / "output" / "result.md"
            authoritative_path = repository / "output" / "result.json"
            self.assertTrue(markdown_path.read_text().startswith(
                "# Inspection Result\n",
            ))
            published = json.loads(authoritative_path.read_text())
            self.assertEqual(published, emitted[0])
            validate_authoritative_result(
                published, publication_authority_key=PUBLICATION_KEY,
            )
            self.assertCountEqual(
                snapshot_reopen_denied, ["authoritative.json", "report.md"],
            )
            bundle = (
                repository / ".inspection-publications"
                / published["inspection_id"]
                / published["publication_state_digest"].removeprefix(
                    "sha256:",
                )
            )
            bundle_json = bundle / "authoritative.json"
            bundle_markdown = bundle / "report.md"
            self.assertEqual(
                bundle_json.read_bytes(),
                authoritative_bytes(
                    published, publication_authority_key=PUBLICATION_KEY,
                ),
            )
            self.assertEqual(bundle_markdown.read_text(), markdown_path.read_text())
            self.assertEqual(stat.S_IMODE(bundle.stat().st_mode), 0o500)
            self.assertEqual(stat.S_IMODE(bundle_json.stat().st_mode), 0o400)
            self.assertEqual(
                stat.S_IMODE(bundle_markdown.stat().st_mode), 0o400,
            )
            self.assertEqual(
                validate_published_outputs(
                    published, repository,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                published,
            )

            bundle_json_before = bundle_json.read_bytes()
            bundle_markdown_before = bundle_markdown.read_bytes()
            os.chmod(bundle_markdown, 0o600)
            bundle_markdown.write_text("same-account mutation\n")
            os.chmod(bundle_markdown, 0o400)
            self.assert_reason(
                lambda: validate_published_outputs(
                    published, repository,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                "publication_action_not_verified",
            )
            os.chmod(bundle_markdown, 0o600)
            bundle_markdown.write_bytes(bundle_markdown_before)
            os.chmod(bundle_markdown, 0o400)
            markdown_path.write_text("mutable profile view changed\n")
            authoritative_path.write_text('{"mutable":"view"}\n')
            self.assertEqual(
                validate_published_outputs(
                    published, repository,
                    publication_authority_key=PUBLICATION_KEY,
                ),
                published,
            )
            self.assertEqual(bundle_json.read_bytes(), bundle_json_before)
            self.assertEqual(
                bundle_markdown.read_bytes(), bundle_markdown_before,
            )

            emitted.clear()
            with (
                mock.patch(
                    "workflow_kernel.inspection."
                    "_host_publication_authority_key_path",
                    return_value=publication_key.resolve(),
                ),
                mock.patch(
                    "workflow_kernel.cli._emit",
                    side_effect=lambda value: emitted.append(value),
                ),
            ):
                self.assertEqual(command_inspection_publish(SimpleNamespace(
                    repository_root=str(repository),
                    input=str(source),
                )), 0)
            self.assertEqual(emitted, [published])
            self.assertEqual(json.loads(authoritative_path.read_text()), published)
            self.assertEqual(markdown_path.read_bytes(), bundle_markdown_before)

            write_count = 0
            original_write_json = kernel_publication._replace_json

            def corrupt_after_rendered_json(path, value):
                nonlocal write_count
                original_write_json(path, value)
                write_count += 1
                if write_count == 2:
                    markdown_path.write_text("stale after rendered signing\n")

            emitted.clear()
            with (
                mock.patch(
                    "workflow_kernel.inspection."
                    "_host_publication_authority_key_path",
                    return_value=publication_key.resolve(),
                ),
                mock.patch(
                    "workflow_kernel.publication._replace_json",
                    side_effect=corrupt_after_rendered_json,
                ),
                mock.patch(
                    "workflow_kernel.cli._emit",
                    side_effect=lambda value: emitted.append(value),
                ),
            ):
                self.assert_reason(
                    lambda: command_inspection_publish(SimpleNamespace(
                        repository_root=str(repository),
                        input=str(source),
                    )),
                    "publication_action_not_verified",
                )
            self.assertEqual(emitted, [])
            self.assertEqual(
                json.loads(authoritative_path.read_text())[
                    "publication_status"
                ],
                "markdown_rendered",
            )

            os.chmod(bundle, 0o700)
            bundle_json.unlink()
            bundle_markdown.unlink()
            bundle.rmdir()
            attacker_directory = repository / "attacker-bundle"
            attacker_directory.mkdir()
            bundle.symlink_to(attacker_directory, target_is_directory=True)
            emitted.clear()
            with (
                mock.patch(
                    "workflow_kernel.inspection."
                    "_host_publication_authority_key_path",
                    return_value=publication_key.resolve(),
                ),
                mock.patch(
                    "workflow_kernel.cli._emit",
                    side_effect=lambda value: emitted.append(value),
                ),
            ):
                self.assert_reason(
                    lambda: command_inspection_publish(SimpleNamespace(
                        repository_root=str(repository),
                        input=str(source),
                    )),
                    "publication_action_not_verified",
                )
            self.assertEqual(emitted, [])
            self.assertTrue(bundle.is_symlink())

    def test_cli_help_and_invalid_inputs_have_stable_nonzero_exit(self):
        env = dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES))
        help_result = subprocess.run(
            [sys.executable, "-m", "workflow_kernel", "--help"],
            text=True, capture_output=True, env=env, check=False,
        )
        self.assertEqual(help_result.returncode, 0)
        for command in (
            "inspection-validate", "inspection-classify", "inspection-trend",
            "inspection-finalize", "inspection-publish", "inspection-render",
            "inspection-run", "kernel-info", "resolve-plugin-bundle",
        ):
            self.assertIn(command, help_result.stdout)
            detail = subprocess.run(
                [sys.executable, "-m", "workflow_kernel", command, "--help"],
                text=True, capture_output=True, env=env, check=False,
            )
            self.assertEqual(detail.returncode, 0)
            normalized_help = " ".join(detail.stdout.split()).replace(
                "non- zero", "non-zero",
            )
            self.assertIn("non-zero", normalized_help)
            self.assertNotIn("--publication-authority-key", detail.stdout)
            if command == "inspection-run":
                self.assertNotIn("--observations", detail.stdout)

        rejected = subprocess.run(
            [
                sys.executable, "-m", "workflow_kernel", "inspection-run",
                "--repository-root", "/missing", "--profile", "profile.json",
                "--result-policy", "/missing-policy.json",
                "--lane-id", "primary", "--attestation", "/missing-attestation",
                "--source", "git", "--ref", "refs/heads/test",
                "--commit", COMMIT, "--dirty", "false",
                "--authorization-event-id", "operator-event-1",
                "--purpose", "scheduled-quality-pulse",
            ],
            text=True, capture_output=True, env=env, check=False,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(
            json.loads(rejected.stderr)["error"]["code"], "inspection_error",
        )
        signing_oracle = subprocess.run(
            [
                sys.executable, "-m", "workflow_kernel",
                "inspection-finalize", "--repository-root", "/missing",
                "--input", "/missing", "--publication-status", "published",
            ],
            text=True, capture_output=True, env=env, check=False,
        )
        self.assertEqual(signing_oracle.returncode, 2)
        self.assertNotIn("published", signing_oracle.stdout)


if __name__ == "__main__":
    unittest.main()
