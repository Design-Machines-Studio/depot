import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.artifacts import (
    MAX_ARTIFACT_BYTES, build_staging_allowlist, classify_artifact,
    deleted_artifact_record, validate_artifact_record,
)


class ArtifactSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, path, value=b"safe content\n"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        return target

    def classify(self, path, **changes):
        arguments = {"lifecycle": "durable", "provenance": "generated", "owner": "chunk-02"}
        arguments.update(changes)
        return classify_artifact(self.root, path, **arguments)

    def intent(self, operation, path, digest=None, source=None):
        return {"operation": operation, "path": path, "source_path": source, "expected_digest": digest}

    def test_safe_record_is_strict_deterministic_and_schema_valid(self):
        self.write("reports/result.json")
        first = self.classify("reports/result.json")
        second = self.classify("reports/result.json")
        self.assertEqual(first, second)
        self.assertEqual((first["classification"], first["sensitivity"], first["lifecycle"], first["committable"]),
                         ("committable", "safe", "durable", True))
        schema = json.loads((KERNEL_REFERENCES / "artifact-classification-schema.json").read_text())
        self.assertTrue(schema_matches(first, schema))
        tampered = copy.deepcopy(first); tampered["byte_count"] += 1
        with self.assertRaisesRegex(ValueError, "record digest mismatch"):
            validate_artifact_record(tampered)
        extra = copy.deepcopy(first); extra["unknown"] = True
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            validate_artifact_record(extra)

    def test_lifecycle_and_sensitivity_are_independent(self):
        self.write("run/safe.log")
        ephemeral = self.classify("run/safe.log", lifecycle="run_scoped")
        self.assertEqual((ephemeral["classification"], ephemeral["sensitivity"], ephemeral["lifecycle"], ephemeral["committable"]),
                         ("ephemeral", "safe", "run_scoped", False))
        self.write("reports/private.txt", b"person@real-domain.org\n")
        private = self.classify("reports/private.txt")
        self.assertEqual((private["classification"], private["sensitivity"], private["lifecycle"]),
                         ("private_receipt", "private", "durable"))

    def test_explicit_sensitive_classes_are_detected_without_republishing_values(self):
        cases = {
            "email": (b"person@real-domain.org", "real_email"),
            "cookie": (b"Authorization: Bearer opaque-value", "cookie_or_authorization"),
            "password": (b"password=opaque-value", "password_or_token"),
            "mfa": (b"totp: 123456", "mfa_qr_authenticator"),
            "url": (b"https://account.internal/private", "private_url"),
            "env": (b"DATABASE_HOST=private-host", "environment_value"),
        }
        for name, (content, rule) in cases.items():
            path = f"evidence/{name}.txt"; self.write(path, content)
            with self.subTest(name=name):
                record = self.classify(path)
                self.assertIn(rule, record["rule_ids"])
                self.assertFalse(record["committable"])
                self.assertNotIn("opaque-value", json.dumps(record))

    def test_metadata_and_filename_are_inspected_and_binary_is_conservative(self):
        self.write("shots/screen.png", b"\x89PNG\x00\xff")
        binary = self.classify("shots/screen.png", metadata={"console": "session_cookie=opaque-value"})
        self.assertEqual(binary["classification"], "blocked_sensitive")
        self.assertIn("cookie_or_authorization", binary["rule_ids"])
        self.assertIn("opaque_binary", binary["rule_ids"])
        self.write("logs/password-export.txt")
        named = self.classify("logs/password-export.txt")
        self.assertIn("sensitive_filename", named["rule_ids"])

    def test_fixture_email_exception_is_explicit_and_does_not_bypass_secrets(self):
        self.write("fixtures/account.example", b"member@example.test")
        ordinary = self.classify("fixtures/account.example")
        fixture = self.classify("fixtures/account.example", provenance="test_fixture")
        self.assertEqual(ordinary["classification"], "private_receipt")
        self.assertEqual(fixture["classification"], "committable")
        self.write("fixtures/mixed.example", b"member@example.test\npassword=opaque")
        mixed = self.classify("fixtures/mixed.example", provenance="test_fixture")
        self.assertEqual(mixed["classification"], "blocked_sensitive")

    def test_traversal_links_special_and_oversized_files_fail_closed(self):
        outside = self.root.parent / "outside-artifact.txt"; outside.write_text("safe")
        self.write("safe.txt")
        (self.root / "link.txt").symlink_to(outside)
        os.link(self.root / "safe.txt", self.root / "hard.txt")
        fifo = self.root / "fifo"; os.mkfifo(fifo)
        for path in ("../outside-artifact.txt", "link.txt", "hard.txt", "fifo"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.classify(path)
        self.write("large.bin", b"x" * (MAX_ARTIFACT_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "size limit"):
            self.classify("large.bin")
        outside.unlink()

    def test_identity_change_during_read_fails_closed(self):
        target = self.write("changing.txt", b"safe")
        replacement = self.write("replacement.txt", b"other")
        original_read = os.read
        changed = {"done": False}

        def read_then_swap(descriptor, count):
            value = original_read(descriptor, count)
            if value and not changed["done"]:
                changed["done"] = True
                target.unlink()
                replacement.rename(target)
            return value

        with mock.patch("workflow_kernel.artifacts.os.read", side_effect=read_then_swap), self.assertRaises(ValueError):
            self.classify("changing.txt")
        self.assertTrue(changed["done"])

    def test_allowlist_is_exact_sorted_and_explains_each_rejection(self):
        self.write("safe.txt")
        self.write("private.txt", b"person@real-domain.org")
        self.write("temp.log")
        safe = self.classify("safe.txt")
        private = self.classify("private.txt")
        ephemeral = self.classify("temp.log", lifecycle="run_scoped")
        stale = copy.deepcopy(safe); stale["path"] = "stale.txt"; stale["record_digest"] = "sha256:" + "0" * 64
        # Reclassify a real second path rather than forging authority.
        self.write("stale.txt"); stale = self.classify("stale.txt")
        intents = [
            self.intent("modify", "temp.log", ephemeral["digest"]),
            self.intent("modify", "missing.txt"),
            self.intent("modify", "private.txt", private["digest"]),
            self.intent("modify", "stale.txt", stale["digest"]),
            self.intent("modify", "safe.txt", safe["digest"]),
            self.intent("modify", "../unsafe.txt"),
        ]
        observed = {"safe.txt": safe["digest"], "private.txt": private["digest"],
                    "temp.log": ephemeral["digest"], "stale.txt": "sha256:" + "f" * 64}
        result = build_staging_allowlist(intents, [private, safe, stale, ephemeral], observed)
        self.assertEqual([item["path"] for item in result["authorized"]], ["safe.txt"])
        reasons = {item["path"]: item["reason"] for item in result["rejected"]}
        self.assertEqual(reasons, {"missing.txt": "unclassified", "private.txt": "private",
                                   "stale.txt": "stale_digest", "temp.log": "ephemeral",
                                   next(path for path in reasons if path.startswith("unsafe-path-sha256-")): "unsafe_path"})
        schema = json.loads((KERNEL_REFERENCES / "staging-allowlist-schema.json").read_text())
        self.assertTrue(schema_matches(result, schema))
        reversed_result = build_staging_allowlist(list(reversed(intents)), list(reversed([private, safe, stale, ephemeral])), observed)
        self.assertEqual(result, reversed_result)

    def test_present_classification_with_absent_file_is_missing_and_blocked_is_distinct(self):
        self.write("safe.txt"); safe = self.classify("safe.txt")
        self.write("blocked.txt", b"password=opaque-value"); blocked = self.classify("blocked.txt")
        result = build_staging_allowlist(
            [self.intent("modify", "safe.txt", safe["digest"]), self.intent("modify", "blocked.txt", blocked["digest"])],
            [safe, blocked], {"safe.txt": None, "blocked.txt": blocked["digest"]},
        )
        self.assertEqual({item["path"]: item["reason"] for item in result["rejected"]},
                         {"blocked.txt": "blocked_sensitive", "safe.txt": "missing"})

    def test_delete_and_rename_require_explicit_exact_records(self):
        old_digest = "sha256:" + "a" * 64
        deleted = deleted_artifact_record("old.txt", old_digest, provenance="git_diff", owner="chunk-02")
        self.write("new.txt")
        renamed = self.classify("new.txt", source_path="old.txt")
        intents = [self.intent("delete", "old.txt", old_digest),
                   self.intent("rename", "new.txt", renamed["digest"], source="old.txt")]
        result = build_staging_allowlist(intents, [deleted, renamed], {"old.txt": None, "new.txt": renamed["digest"]})
        self.assertEqual([item["operation"] for item in result["authorized"]], ["rename", "delete"])
        missing_source = build_staging_allowlist(intents[1:], [renamed], {"new.txt": renamed["digest"]})
        self.assertEqual(missing_source["rejected"][0]["reason"], "unclassified")


if __name__ == "__main__":
    unittest.main()
