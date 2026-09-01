import copy
import unittest

from workflow_kernel.observation_index import (
    observation_index_digest, validate_observation_index,
)


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
STAMP = "2026-09-01T00:00:00Z"


def provenance(digest=DIGEST_B):
    return {"source_digest": digest, "observed_at": STAMP}


def available(value, digest=DIGEST_B):
    return {"availability": "available", "value": value, "provenance": provenance(digest)}


def unavailable(reason="not_reported"):
    return {"availability": "unavailable", "value": None, "reason": reason}


def sample_index():
    value = {
        "schema_version": 1,
        "contract": "observation-index-v1",
        "producer": {
            "name": "pipeline", "version": "1.64.0",
            "execution_profile": "builder-deep", "source_digest": DIGEST_A,
        },
        "run": {
            "run_id": "run-86",
            "session_id": available("session-1"),
            "attempt_ids": available(["attempt-1"]),
            "workflow_node_ids": available(["chunk-01"]),
            "action_ids": available(["action-1"]),
        },
        "sources": [
            {
                "role": "producer", "reference": "receipts/terminal.json",
                "digest": DIGEST_A, "media_type": "application/json",
                "size_bytes": 120, "source_timestamp": STAMP,
                "observed_at": STAMP, "freshness": "fresh",
                "freshness_reason": None,
            },
            {
                "role": "receipts", "reference": "receipts/attempts.jsonl",
                "digest": DIGEST_B, "media_type": "application/x-ndjson",
                "size_bytes": 240, "source_timestamp": STAMP,
                "observed_at": STAMP, "freshness": "fresh",
                "freshness_reason": None,
            },
            {
                "role": "cost", "reference": "receipts/cost.json",
                "digest": DIGEST_C, "media_type": "application/json",
                "size_bytes": 90, "source_timestamp": STAMP,
                "observed_at": STAMP, "freshness": "stale",
                "freshness_reason": "age_exceeded",
            },
        ],
        "observations": {
            "plugins": available([
                {"name": "pipeline", "version": "1.64.0", "digest": DIGEST_A},
                {"name": "workflow-kernel", "version": "0.19.0", "digest": DIGEST_B},
            ]),
            "objective": available("Ship the shared observation contract."),
            "budget": available("plans/run-budget.json"),
            "completion_contract": available("receipts/completion-contract.json"),
            "models": available([{
                "requested_model": available("openai/gpt-requested"),
                "attempted_model": available("openai/gpt-attempted"),
                "served_model": available("openai/gpt-served"),
                "provider": available("openai"),
                "routing_rationale": available("capability_match"),
                "fallback_reason": available("requested_unavailable"),
            }]),
            "usage": {
                "input_tokens": available(100), "output_tokens": available(50),
                "cache_read_tokens": available(10), "cache_write_tokens": available(5),
                "reasoning_tokens": available(20), "duration_seconds": available(12.5),
                "model_call_count": available(2), "tool_call_count": available(3),
            },
            "cost": {
                "status": "measured", "value_usd": 0.12,
                "measurement_reference": "receipts/cost.json",
                "provenance": provenance(DIGEST_C),
            },
            "verifier": available({
                "result": "passed", "evidence_references": ["evidence/tests.json"],
            }),
            "artifacts": available([{
                "handle": "artifact-1", "reference": "artifacts/output.bin",
                "digest": DIGEST_C, "media_type": "application/octet-stream",
                "size_bytes": 4096,
                "preview": {
                    "availability": "available", "reference": "artifacts/output.txt",
                    "digest": DIGEST_B, "media_type": "text/plain", "size_bytes": 120,
                },
            }]),
            "recovery": available({
                "failure_signature": DIGEST_C, "recovery_decision": "retry-once",
            }),
            "supervision": available({
                "stagnation": True, "intervention": "human-review",
            }),
            "candidates": available([{
                "candidate_id": "candidate-1", "parent_ids": [],
                "score": unavailable("consumer_not_defined"),
                "disposition": "accepted", "provenance": provenance(),
            }]),
            "next_action": available("Open the exact-head pull request."),
        },
        "emitted_at": STAMP,
        "digest": DIGEST_A,
    }
    value["digest"] = observation_index_digest(value)
    return value


class ObservationIndexTests(unittest.TestCase):
    def assert_invalid(self, mutate):
        value = sample_index()
        mutate(value)
        value["digest"] = observation_index_digest(value)
        with self.assertRaises(ValueError):
            validate_observation_index(value)

    def test_complete_index_validates(self):
        validate_observation_index(sample_index())

    def test_partial_index_uses_explicit_unavailable_facts(self):
        value = sample_index()
        for key in ("session_id", "attempt_ids", "workflow_node_ids", "action_ids"):
            value["run"][key] = unavailable()
        for key in ("plugins", "objective", "budget", "completion_contract", "models",
                    "verifier", "artifacts", "recovery", "supervision", "candidates",
                    "next_action"):
            value["observations"][key] = unavailable()
        for key in value["observations"]["usage"]:
            value["observations"]["usage"][key] = unavailable()
        value["observations"]["cost"] = {
            "status": "unavailable", "value_usd": None, "reason": "not_reported",
        }
        value["digest"] = observation_index_digest(value)
        validate_observation_index(value)

    def test_imputed_cost_requires_matrix_and_basis(self):
        value = sample_index()
        value["observations"]["cost"] = {
            "status": "imputed", "value_usd": 0.25,
            "matrix_snapshot": "2026-09-01", "matrix_digest": DIGEST_C,
            "basis": "api-equivalent", "provenance": provenance(DIGEST_C),
        }
        value["digest"] = observation_index_digest(value)
        validate_observation_index(value)
        del value["observations"]["cost"]["matrix_digest"]
        value["digest"] = observation_index_digest(value)
        with self.assertRaises(ValueError):
            validate_observation_index(value)

    def test_rejects_unknown_version_and_fields(self):
        self.assert_invalid(lambda value: value.__setitem__("schema_version", 2))
        self.assert_invalid(lambda value: value.__setitem__("surprise", True))

    def test_rejects_unsafe_reference_and_invalid_digest(self):
        self.assert_invalid(lambda value: value["sources"][0].__setitem__("reference", "../secret"))
        self.assert_invalid(lambda value: value["sources"][0].__setitem__("digest", "sha256:NO"))

    def test_rejects_missing_or_ambiguous_provenance(self):
        self.assert_invalid(lambda value: value["observations"]["objective"].pop("provenance"))
        self.assert_invalid(lambda value: value["sources"].append(copy.deepcopy(value["sources"][0])))

    def test_rejects_false_cost_claims(self):
        self.assert_invalid(lambda value: value["observations"]["cost"].__setitem__("value_usd", None))
        self.assert_invalid(lambda value: value["observations"].__setitem__(
            "cost", {"status": "unavailable", "value_usd": 1.0, "reason": "not_reported"},
        ))

    def test_rejects_model_fallback_ambiguity(self):
        def mutate(value):
            route = value["observations"]["models"]["value"][0]
            route["fallback_reason"] = unavailable()
        self.assert_invalid(mutate)

    def test_rejects_unbounded_or_embedded_artifact_data(self):
        self.assert_invalid(lambda value: value["observations"]["artifacts"]["value"][0].__setitem__("content", "raw"))
        self.assert_invalid(lambda value: value["observations"]["artifacts"].__setitem__("value", [
            copy.deepcopy(value["observations"]["artifacts"]["value"][0])
            for _ in range(257)
        ]))

    def test_rejects_digest_mismatch(self):
        value = sample_index()
        value["digest"] = DIGEST_A
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            validate_observation_index(value)


if __name__ == "__main__":
    unittest.main()
