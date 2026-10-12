"""Real byte-boundary mechanics; fixtures never establish consumer coverage."""
import hashlib
import json
import unittest
from pathlib import Path

from tests import test_review_closeout as fixture
from workflow_kernel import owned_run, review_closeout as review


MIB = 1024 * 1024
SUPPORTED = 129 * MIB
BOUND = 192 * MIB


class ReviewEvidenceSizeTests(unittest.TestCase):
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve

    @staticmethod
    def sparse(path, size):
        with path.open("wb") as stream:
            stream.truncate(size)

    @staticmethod
    def digest(path):
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def test_supported_package_assembles_copies_preserves_and_finishes(self):
        run, paths = self.make_run(run_id="supported-129-mib")
        # A report-linked fixture artifact is required by the existing closure
        # contract. It is neither a fabricated live lane nor a count override.
        ref = "review/evidence/large-proof.bin"
        proof = run.root / ref
        self.sparse(proof, SUPPORTED)
        before = self.digest(proof)
        paths["report"].write_text(f"# Review\n[Required proof]({ref})\n")
        value = json.loads(paths["coverage_input"].read_text())
        value["pass_id"] = "above-former-byte-limit"
        paths["coverage_input"].write_text(json.dumps(value))
        assembled = review.assemble_review_evidence(
            run_root=run.root, repository_root=self.repo,
            request_path=paths["request"], receipts_path=paths["receipts"],
            input_path=paths["coverage_input"])
        self.assertEqual("complete", assembled["status"])
        self.assertGreater(review._check_evidence_bound(proof.parent)[1], 128 * MIB)
        self.assertEqual(SUPPORTED, len(review._regular_file(proof)))
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"], result)
        copied = Path(result["evidence_path"]) / ref
        self.assertEqual(before, self.digest(copied))
        self.assertEqual(before, self.digest(proof))
        retained = review.validate_preserved_review_evidence(
            run.root / "diagnostic", run=owned_run.ExactOwnedRun.open(run.root))
        row = retained["retention"]["required_review"]
        self.assertGreater(row["actual_bytes"], 128 * MIB)
        self.assertLess(row["actual_bytes"], BOUND)
        self.assertEqual(BOUND, row["allowed_bytes"])
        self.assertEqual(2048, row["allowed_files"])
        self.assertEqual(0, retained["retention"]["diagnostic"]["actual_files"])
        run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual(before, self.digest(copied))

    def test_workspace_exact_bound_and_failed_seal_keep_original(self):
        run, _ = self.make_run(run_id="workspace-byte-bound")
        directory = run.root / "review/evidence"
        proof = directory / "existing.bin"
        existing = sum(owned_run._diagnostic_inventory(directory).values())
        self.sparse(proof, BOUND - existing)
        self.assertEqual(BOUND, review._check_evidence_bound(directory)[1])
        before = self.digest(proof)
        names = set(directory.iterdir())
        with self.assertRaises(review.EvidenceAssemblyError) as caught:
            review._seal_evidence(run.root, "literal", b"x", literal=True)
        error = caught.exception
        self.assertEqual("workspace_limit", error.reason)
        self.assertEqual("assembly_workspace", error.measurement["category"])
        self.assertEqual(BOUND + 1, error.measurement["actual_bytes"])
        self.assertEqual(BOUND, error.measurement["allowed_bytes"])
        self.assertIn("Keep original evidence", error.measurement["next_action"])
        self.assertEqual(names, set(directory.iterdir()))
        self.assertEqual(before, self.digest(proof))

    def test_retention_and_per_read_exact_bound_and_one_over(self):
        directory = self.root / "retention"
        directory.mkdir()
        proof = directory / "required.bin"
        self.sparse(proof, BOUND)
        owned_run._require_retention_projection(owned_run._retention_projection(
            owned_run._diagnostic_inventory(directory), [proof.name]))
        with proof.open("ab") as stream:
            stream.write(b"x")
        before = self.digest(proof)
        with self.assertRaises(owned_run.BoundedDiagnosticLimitError) as caught:
            owned_run._require_retention_projection(owned_run._retention_projection(
                owned_run._diagnostic_inventory(directory), [proof.name]))
        self.assertEqual("required_review", caught.exception.measurement["category"])
        self.assertEqual(BOUND + 1, caught.exception.measurement["actual_bytes"])
        self.assertEqual(BOUND, caught.exception.measurement["allowed_bytes"])
        self.assertIn("Keep original evidence", caught.exception.measurement["next_action"])
        with self.assertRaises(owned_run.BoundedDiagnosticLimitError):
            review._regular_file(proof)
        self.assertEqual(before, self.digest(proof))

    def test_intermediate_router_copy_accepts_supported_bytes(self):
        run, paths = self.make_run(run_id="router-129-mib")
        # JSON whitespace makes a valid inert diagnostic file for the helper;
        # required/diagnostic membership is checked separately by retention.
        large = paths["router"] / "large.json"
        with large.open("wb") as stream:
            stream.write(b"{}"); block = b" " * MIB
            for _ in range(129):
                stream.write(block)
        before = self.digest(large)
        target = self.root / "router-copy"
        files, size = review._copy_router_tree(paths["router"], target)
        self.assertEqual(3, files)
        self.assertGreater(size, 128 * MIB)
        self.assertLess(size, BOUND)
        self.assertEqual(before, self.digest(target / large.name))
        # Unindexed bytes still cannot borrow required membership.
        with self.assertRaises(owned_run.BoundedDiagnosticLimitError):
            owned_run._bounded_diagnostic(target)

    def test_file_and_diagnostic_limits_remain_enforced(self):
        for required, count, size, category in (
            (True, 2049, 0, "required_review"),
            (False, 417, 0, "diagnostic"),
            (False, 1, 9 * MIB + 1, "diagnostic"),
        ):
            inventory = {str(index): 0 for index in range(count)}
            inventory["0"] = size
            projection = owned_run._retention_projection(
                inventory, inventory if required else ())
            with self.assertRaises(owned_run.BoundedDiagnosticLimitError) as caught:
                owned_run._require_retention_projection(projection)
            self.assertEqual(category, caught.exception.measurement["category"])
        self.assertEqual(4096, review._MAX_ASSEMBLY_WORKSPACE_FILES)
        self.assertEqual(416, owned_run._MAX_DIAGNOSTIC_FILES)
        self.assertEqual(9 * MIB, owned_run._MAX_DIAGNOSTIC_BYTES)

    def test_digest_unsafe_path_and_owner_still_reject_without_source_loss(self):
        run, paths = self.make_run(run_id="unchanged-safety")
        record = json.loads((run.root / paths["record_ref"]).read_text())
        binding = next(iter(record["bindings"].values()))["retained_ref"]
        sealed = run.root / binding
        original = sealed.read_bytes()
        sealed.write_bytes(b"digest mismatch")
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertEqual(b"digest mismatch", sealed.read_bytes())
        sealed.write_bytes(original)
        proof = self.root / "proof.bin"
        proof.write_bytes(b"source evidence")
        link = run.root / "review/evidence/unsafe.bin"
        link.symlink_to(proof)
        with self.assertRaises(ValueError):
            owned_run._diagnostic_inventory(link.parent)
        link.unlink()
        metadata = run.root / ".depot-owned-run.json"
        owner = json.loads(metadata.read_text())
        owner["root_identity"][1] += 1
        metadata.write_text(json.dumps(owner))
        with self.assertRaises(ValueError):
            self.preserve(run, paths)
        self.assertEqual(original, sealed.read_bytes())
        self.assertEqual(b"source evidence", proof.read_bytes())
        self.assertFalse((run.root / "CLEANUP.txt").exists())
