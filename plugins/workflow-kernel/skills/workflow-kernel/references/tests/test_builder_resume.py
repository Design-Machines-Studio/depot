import unittest

from tests import detail_digest
from workflow_kernel.adapters.base import (
    HostCapabilities, HostCapability, NodeSpec, SessionHandle, SessionResult,
    ValidationFeedback,
)
from workflow_kernel.adapters.host import BuilderSessionManager, FakeHostAdapter
from workflow_kernel.schema import InvalidSchemaError


NOW = "2026-07-14T00:00:00Z"


def handle(host="codex", value="opaque-token-value", *, resumable=True, created_at=NOW):
    return SessionHandle(host, value, created_at, resumable)


def host_capabilities(name="codex"):
    return HostCapabilities(name, (HostCapability.NATIVE_DISPATCH, HostCapability.SESSION_RESUME))


class BuilderResumeTests(unittest.TestCase):
    def test_real_handle_is_resumed_with_deterministic_validation_feedback(self):
        original = handle()
        result = SessionResult("succeeded", ("validation.txt",))
        adapter = FakeHostAdapter(host_capabilities(), resume_results=(result,))
        feedback = ValidationFeedback(
            "build", "deterministic_validation_failure", ("test-report.txt",),
        )
        decision = BuilderSessionManager(adapter).resume_or_replace(
            NodeSpec("build"), original, feedback, now=NOW,
        )
        self.assertEqual(decision.status, "resumed")
        self.assertTrue(decision.resumed_original)
        self.assertIs(decision.handle, original)
        self.assertEqual(adapter.resume_calls, [(original, feedback)])
        self.assertEqual(decision.events, ("session_resumed",))

    def test_unavailable_resume_paths_emit_event_and_label_replacement(self):
        cases = {
            "missing": None,
            "non_resumable": handle(resumable=False),
            "stale": handle(created_at="2026-07-13T00:00:00Z"),
            "foreign": handle(host="claude-code"),
        }
        for name, original in cases.items():
            with self.subTest(name=name):
                replacement = handle(value="replacement-value")
                adapter = FakeHostAdapter(host_capabilities(), dispatch_handles=(replacement,))
                decision = BuilderSessionManager(adapter, max_age_seconds=3600).resume_or_replace(
                    NodeSpec("build"), original,
                    ValidationFeedback("build", "deterministic_validation_failure"),
                    now=NOW,
                )
                self.assertEqual(decision.status, "replacement_dispatched")
                self.assertFalse(decision.resumed_original)
                self.assertIs(decision.handle, replacement)
                self.assertEqual(decision.reason_code, "session_resume_unavailable")
                self.assertEqual(
                    decision.events,
                    ("session_resume_unavailable", "builder_replacement_dispatched"),
                )
                self.assertEqual(adapter.resume_calls, [])

    def test_missing_replacement_handle_is_not_fabricated(self):
        adapter = FakeHostAdapter(host_capabilities())
        decision = BuilderSessionManager(adapter).resume_or_replace(
            NodeSpec("build"), None,
            ValidationFeedback("build", "deterministic_validation_failure"),
            now=NOW,
        )
        self.assertEqual(decision.status, "resume_unavailable")
        self.assertIsNone(decision.handle)
        self.assertEqual(decision.events, ("session_resume_unavailable",))

    def test_session_serialization_redacts_opaque_values_and_credentials(self):
        secret = "sk-provider-credential"
        value = "session:" + secret
        session = handle(value=value)
        serialized = session.to_dict()
        projected = repr(serialized) + repr(session)
        self.assertNotIn(value, projected)
        self.assertNotIn(secret, projected)
        self.assertTrue(serialized["opaque_digest"].startswith("sha256:"))
        self.assertEqual(serialized["host_name"], "codex")
        self.assertTrue(serialized["resume_capable"])

    def test_invalid_session_handle_fails_with_stable_reason(self):
        for invalid in (
            {"created_at": "not-a-timestamp"},
            {"created_at": "2026-07-14T00:00:00"},
            {"host": "host:credential"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(InvalidSchemaError) as raised:
                handle(**invalid)
            self.assertEqual(
                raised.exception.details["reason_code"],
                detail_digest("invalid_session_handle"),
            )


if __name__ == "__main__":
    unittest.main()
