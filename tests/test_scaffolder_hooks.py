"""Execute the shipped Craft hook template without running its input commands."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins/project-scaffolder/skills/scaffolding/references/hooks.md"


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "bash and jq required")
class CraftHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        section = HOOKS.read_text().split("## 2. block-bare-craft.sh\n", 1)[1]
        cls.script = re.search(r"```bash\n(.*?)\n```", section, re.S).group(1)

    def run_hook(self, command):
        with tempfile.TemporaryDirectory() as directory:
            hook = Path(directory) / "block-bare-craft.sh"
            hook.write_text(self.script)
            return subprocess.run(
                ["bash", str(hook)],
                input=json.dumps({"tool_input": {"command": command}}),
                text=True, capture_output=True, check=False,
            )

    def test_rejects_host_commands_without_global_ddev_exemption(self):
        for command in (
            "composer install",
            "php craft migrate/all",
            "ddev start && composer install",
            "ddev describe; php craft migrate/all",
            "composer install && ddev describe",
            "composer install --working-dir=.ddev",
            "php craft migrate/all # ddev",
            "printf 'ddev ready'; composer install",
            "ddev describe\nphp craft migrate/all",
            "env composer install",
            "env -i composer install",
            "env -- composer install",
            "env -u APP_ENV composer install",
            "env APP_ENV=dev php craft migrate/all",
            "APP_ENV=dev composer install",
            "command composer install",
            "command -p composer install",
            "command -- composer install",
            "command -- php craft migrate/all",
            "command -p -- composer install",
            "exec php craft migrate/all",
            "exec -- composer install",
            "printf x | composer install",
            "(composer install)",
        ):
            with self.subTest(command=command):
                result = self.run_hook(command)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("BLOCKED", result.stderr)

    def test_allows_wrapped_commands_and_unrelated_text_silently(self):
        for command in (
            "ddev composer install",
            "ddev craft migrate/all",
            "ddev start && ddev composer install",
            "env APP_ENV=dev ddev craft migrate/all",
            "env -i ddev composer install",
            "command -p ddev craft migrate/all",
            "command -- ddev composer install",
            "exec -- ddev craft migrate/all",
            "command -v composer",
            "echo 'composer install'",
            "printf '%s\\n' 'php craft migrate/all'",
            "git diff -- composer.json",
            "php -v",
            "",
        ):
            with self.subTest(command=command):
                result = self.run_hook(command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
