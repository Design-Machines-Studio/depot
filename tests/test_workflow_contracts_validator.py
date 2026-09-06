import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = Path("tools/validate-workflow-contracts.sh")
PROTOTYPE_FILES = (
    Path("plugins/pipeline/references/prototype-authority.md"),
    Path("plugins/pipeline/skills/assess/references/ux-assessment-protocol.md"),
    Path("plugins/pipeline/skills/assess/SKILL.md"),
    Path("plugins/pipeline/skills/promptcraft/SKILL.md"),
    Path("plugins/pipeline/skills/promptcraft/references/prompt-template.md"),
    Path("plugins/pipeline/skills/promptcraft/references/manifest-schema.md"),
    Path("plugins/pipeline/references/visual-verification-protocol.md"),
    Path("plugins/pipeline/references/phase7-visual-verification.md"),
    Path("plugins/dm-review/skills/review/references/design-spec-discovery.md"),
    Path("plugins/dm-review/skills/review/references/reviewer-prompt-template.md"),
    Path("plugins/dm-review/skills/review/references/visual-finding-rules.md"),
    Path("plugins/dm-review/skills/review/references/ui-review-readiness.md"),
    Path("plugins/dm-review/agents/review/ui-standards-reviewer.md"),
    Path("plugins/dm-review/agents/review/ux-quality-reviewer.md"),
    Path("plugins/dm-review/agents/review/visual-browser-tester.md"),
    Path("plugins/assembly/skills/development/SKILL.md"),
    Path("plugins/assembly/skills/development/pages.md"),
)


class WorkflowContractsValidatorTests(unittest.TestCase):
    def fixture(self, directory):
        destination = Path(directory) / "depot"
        for relative in (VALIDATOR, *PROTOTYPE_FILES):
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return destination

    def run_validator(self, root, *arguments):
        return subprocess.run(
            (str(root / VALIDATOR), *arguments),
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_focused_prototype_contract_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_validator(self.fixture(directory), "--prototype-parity")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Prototype authority contract intact", result.stdout)

    def test_focused_prototype_contract_detects_missing_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            authority = root / "plugins/pipeline/references/prototype-authority.md"
            original = authority.read_text()
            mutated = original.replace("Resolve once, source first", "Resolve source later", 1)
            self.assertNotEqual(mutated, original)
            authority.write_text(mutated)
            result = self.run_validator(root, "--prototype-parity")
        self.assertEqual(result.returncode, 1)
        self.assertIn("prototype identity and exact commit", result.stdout)

    def test_unsupported_argument_exits_two_with_usage(self):
        result = self.run_validator(ROOT, "--unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
