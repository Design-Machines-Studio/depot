import copy
import json
import unittest

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.evidence_binding import (
    build_evidence_binding, match_evidence_binding, validate_evidence_binding,
)


DIGEST = "sha256:" + "a" * 64


def binding(**changes):
    value = {
        "commit_sha": "b" * 40, "tree_digest": DIGEST,
        "tracked_diff_digest": DIGEST, "untracked_digest": DIGEST,
        "untracked_classification": "safe", "profile_digest": DIGEST,
        "plan_digest": DIGEST, "scenario_digest": None, "command_digest": DIGEST,
        "artifact_digest": None, "image_digest": None,
        "started_at": "2026-07-22T00:00:00Z", "completed_at": "2026-07-22T00:00:01Z",
        "exit_status": 0, "evidence_digest": DIGEST,
    }
    value.update(changes)
    return build_evidence_binding(**value)


class EvidenceBindingTests(unittest.TestCase):
    def test_binding_matches_schema_and_digest_is_tamper_evident(self):
        value = binding()
        schema = json.loads((KERNEL_REFERENCES / "evidence-binding-schema.json").read_text())
        self.assertTrue(schema_matches(value, schema))
        self.assertEqual(validate_evidence_binding(value), value)
        tampered = copy.deepcopy(value); tampered["commit_sha"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "binding digest mismatch"):
            validate_evidence_binding(tampered)

    def test_match_reports_specific_reasons(self):
        expected = binding()
        current = binding(commit_sha="c" * 40, profile_digest="sha256:" + "d" * 64,
                          scenario_digest="sha256:" + "e" * 64)
        result = match_evidence_binding(expected, current)
        self.assertFalse(result["matches"])
        self.assertEqual(result["reasons"], ["head_changed", "profile_changed", "scenario_changed"])
        self.assertEqual(match_evidence_binding(expected, expected), {"matches": True, "reasons": []})

    def test_unknown_fields_bad_time_and_secret_are_rejected(self):
        for mutation in (
            lambda value: value.update(extra=True),
            lambda value: value.update(started_at="yesterday"),
            lambda value: value.update(untracked_classification="passed"),
            lambda value: value.update(evidence_digest="sk_live_1234567890abcdef"),
        ):
            value = binding(); mutation(value)
            with self.assertRaises(ValueError):
                validate_evidence_binding(value)


if __name__ == "__main__":
    unittest.main()
