import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("jev_log_trial", ROOT / "tools/jev-log-trial.py")
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


def answer(options, choice, confidence=1):
    return {"type": "choice", "choice": choice, "confidence": confidence,
            "probabilities": {k: (1 if k == choice else 0) for k in options}}


def response(case, drop=False):
    chunks = trial.prepare(case)
    answers = {"category": answer(trial.CATEGORIES, case["expected_category"])}
    for chunk in chunks:
        essential = set(case["essential_lines"]) & trial.line_set([chunk])
        answers[chunk["id"]] = answer(["keep", "drop", "unknown"], "drop" if drop and not essential else "keep")
    return {"answers": answers}


class JevLogTrialTests(unittest.TestCase):
    def setUp(self):
        self.cases = trial.load_corpus(ROOT / "tests/fixtures/jev-log-corpus.json")

    def test_thirty_distinct_synthetic_cases_preserve_source_offsets(self):
        self.assertEqual(len(self.cases), 30)
        for case in self.cases:
            chunks = trial.prepare(case)
            original = case["log"].splitlines(keepends=True)
            for c in chunks:
                self.assertEqual(c["lines"], original[c["start"] - 1:c["end"]])
            self.assertFalse(trial.evaluate(case, chunks, chunks, None)["baseline_missed_essential_lines"])

    def test_fixture_mode_never_calls_provider_or_claims_usage(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(trial.subprocess, "run", side_effect=AssertionError("network")):
            out = Path(tmp) / "trial"
            rows = trial.run(self.cases, out, fixtures={c["id"]: response(c, True) for c in self.cases})
            self.assertTrue(all(r["selected_log_bytes"] < r["baseline_log_bytes"] for r in rows))
            self.assertTrue(all(not r["jev_missed_essential_lines"] for r in rows))
            self.assertTrue(all(r["usage"] is None and r["price_derived_usd"] is None for r in rows))
            self.assertEqual(json.loads((out / "results.json").read_text())["mode"], "synthetic_transport")

    def test_uncertain_drop_keeps_section(self):
        case = self.cases[0]
        chunks = trial.prepare(case)
        raw = response(case)
        a = raw["answers"][chunks[0]["id"]]
        a.update(choice="drop", confidence=.94, probabilities={"keep": .02, "drop": .94, "unknown": .04})
        self.assertEqual(trial.selection(raw, chunks)[0], chunks)

    def test_malformed_answer_falls_back_without_missing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = trial.run(self.cases[:1], Path(tmp) / "trial", fixtures={self.cases[0]["id"]: {"answers": {}}})
            self.assertEqual(rows[0]["status"], "fallback_invalid_answer")
            self.assertEqual(rows[0]["baseline_log_bytes"], rows[0]["selected_log_bytes"])

    def test_bad_probabilities_rejected(self):
        case = self.cases[0]
        for bad in [float("nan"), -1, True, 2]:
            raw = response(case)
            raw["answers"]["category"]["probabilities"]["unknown"] = bad
            with self.assertRaises(AssertionError):
                trial.selection(raw, trial.prepare(case))

    def test_missed_evidence_is_counted_not_hidden(self):
        case = self.cases[0]
        chunks = trial.prepare(case)
        raw = response(case)
        for c in chunks:
            if set(case["essential_lines"]) & trial.line_set([c]):
                raw["answers"][c["id"]] = answer(["keep", "drop", "unknown"], "drop")
        retained, category = trial.selection(raw, chunks)
        self.assertEqual(trial.evaluate(case, chunks, retained, category)["jev_missed_essential_lines"], case["essential_lines"])

    def test_paid_failure_stops_remaining_calls_and_preserves_results(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(trial.subprocess, "run") as dispatch:
            dispatch.return_value.returncode = 1
            out = Path(tmp) / "trial"
            rows = trial.run(self.cases[:3], out, adapter=Path("/unused/openrouter-decisions.sh"))
            self.assertEqual(dispatch.call_count, 1)
            self.assertEqual(rows[1]["status"], "fallback_rail_unavailable")
            self.assertEqual(len(json.loads((out / "results.json").read_text())["rows"]), 3)
            self.assertTrue((out / self.cases[0]["id"] / "original.log").is_file())

    def test_over_bound_falls_back_without_call_or_truncation(self):
        case = dict(self.cases[0], log="error: " + "x" * 40000)
        with tempfile.TemporaryDirectory() as tmp, patch.object(trial.subprocess, "run") as dispatch:
            rows = trial.run([case], Path(tmp) / "trial", adapter=Path("/unused"))
            dispatch.assert_not_called()
            self.assertEqual(rows[0]["status"], "fallback_input_bound")
            self.assertEqual(rows[0]["selected_log_bytes"], len(case["log"].encode()))

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                trial.run(self.cases[:1], Path(tmp))

    def test_labels_are_not_sent_to_provider(self):
        case = self.cases[0]
        payload = trial.request_for(case, trial.prepare(case))
        self.assertEqual(set(payload["state"]), {"exit_code", "sections"})
        self.assertNotIn("essential_lines", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
