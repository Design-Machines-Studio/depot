import copy
import json
import unittest

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.repository_verification import (
    compare_coverage, derive_verification_plan, repository_profile_digest,
    resolve_repository_profile, validate_repository_profile,
    validate_verification_plan,
)


DIGEST = "sha256:" + "a" * 64


def lane(identifier="doctor", tier="doctor", argv=None, parser=None, **changes):
    value = {
        "id": identifier, "tier": tier,
        "argv": ["git", "diff", "--check"] if argv is None else argv,
        "workdir": ".", "parser": parser or ("doctor" if tier == "doctor" else "exit-code"),
        "authority": "local", "runnable": True, "timeout_seconds": 30,
        "max_output_bytes": 65536,
        "selectors": {"path_prefixes": [], "packages": []},
        "risk_escalators": [],
        "prerequisites": [{"kind": "tool", "id": "git", "required": True}],
        "doctor_check": "diff_check" if tier == "doctor" else None,
    }
    value.update(changes)
    return value


def profile(kind="project"):
    return {
        "schema_version": 1, "profile_id": "example", "profile_version": 1,
        "source": {"kind": kind, "reference": ".verification/profile.json"},
        "declaration_digests": [DIGEST],
        "lanes": [
            lane(),
            lane("focused", "focused", ["go", "test", "-json", "./pkg"], "go-test-json",
                 selectors={"path_prefixes": ["pkg"], "packages": ["./pkg"]}),
            lane("race", "race", [], "exit-code", authority="github", runnable=False,
                 risk_escalators=["concurrency"]),
        ],
    }


def repository():
    return {
        "scope_id": "b" * 64, "commit_sha": "c" * 40,
        "tree_digest": DIGEST, "tracked_diff_digest": DIGEST,
        "untracked_digest": DIGEST, "branch": "feature", "worktree_state": "dirty",
    }


class RepositoryVerificationTests(unittest.TestCase):
    def test_profile_is_strict_canonical_and_matches_schema(self):
        value = profile()
        canonical = validate_repository_profile(value)
        schema = json.loads((KERNEL_REFERENCES / "repository-verification-profile-schema.json").read_text())
        self.assertTrue(schema_matches(canonical, schema))
        self.assertEqual(repository_profile_digest(value), repository_profile_digest(canonical))
        for mutate in (
            lambda item: item.update(extra=True),
            lambda item: item["lanes"].append(copy.deepcopy(item["lanes"][0])),
            lambda item: item["lanes"][0].update(argv=["sh", "-c", "echo no"]),
            lambda item: item["source"].update(reference="../escape"),
            lambda item: item["lanes"][0].update(timeout_seconds=True),
            lambda item: item["lanes"][0].update(argv=["tool", "--token", "opaque"]),
        ):
            candidate = copy.deepcopy(value); mutate(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                validate_repository_profile(candidate)

    def test_profile_precedence_is_explicit_and_no_heuristic_fallback_exists(self):
        project = profile("project")
        plugin = profile("plugin"); plugin["profile_id"] = "plugin-default"
        resolved = resolve_repository_profile(project_profile=project, plugin_profile=plugin)
        self.assertEqual((resolved["source"], resolved["profile"]["profile_id"]), ("project", "example"))
        self.assertEqual(resolve_repository_profile(plugin_profile=plugin)["source"], "plugin")
        self.assertEqual(resolve_repository_profile(), {"status": "unavailable", "source": "none", "profile": None})

    def test_plan_is_deterministic_and_keeps_selected_and_omitted_authority(self):
        arguments = dict(
            changed_paths=["pkg/file.go"], changed_packages=["./pkg"],
            risk_inputs=[], required_lane_ids=[], generated_at="2026-07-22T00:00:00Z",
        )
        first = derive_verification_plan(profile(), repository(), **arguments)
        second = derive_verification_plan(profile(), repository(), **arguments)
        self.assertEqual(first, second)
        self.assertEqual(validate_verification_plan(first), first)
        lanes = {item["id"]: item for item in first["lanes"]}
        self.assertTrue(lanes["doctor"]["selected"])
        self.assertTrue(lanes["focused"]["selected"])
        self.assertFalse(lanes["race"]["selected"])
        self.assertEqual(lanes["race"]["authority"], "github")
        changed = copy.deepcopy(first); changed["repository"]["commit_sha"] = "d" * 40
        with self.assertRaisesRegex(ValueError, "plan digest mismatch"):
            validate_verification_plan(changed)

    def test_risk_can_select_remote_lane_but_cannot_make_it_local(self):
        plan = derive_verification_plan(
            profile(), repository(), changed_paths=[], changed_packages=[],
            risk_inputs=["concurrency"], generated_at="2026-07-22T00:00:00Z",
        )
        race = next(item for item in plan["lanes"] if item["id"] == "race")
        self.assertTrue(race["selected"])
        self.assertFalse(race["runnable"])
        self.assertEqual(race["authority"], "github")

    def test_coverage_requires_comparable_metadata(self):
        metadata = {"packages": ["./pkg"], "command_digest": DIGEST, "tags": ["dev"],
                    "coverage_mode": "atomic", "profile_digest": DIGEST, "binding_digest": DIGEST}
        self.assertTrue(compare_coverage(79, 80, current_metadata=metadata, baseline_metadata=metadata)["regression"])
        other = copy.deepcopy(metadata); other["tags"] = []
        self.assertEqual(compare_coverage(79, 80, current_metadata=metadata, baseline_metadata=other)["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
