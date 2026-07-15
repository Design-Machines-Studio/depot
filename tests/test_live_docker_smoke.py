import os
import subprocess
import unittest
import uuid


@unittest.skipUnless(
    os.environ.get("WORKFLOW_KERNEL_LIVE_DOCKER") == "1",
    "set WORKFLOW_KERNEL_LIVE_DOCKER=1 for the owned-resource smoke test",
)
class LiveDockerSmokeTests(unittest.TestCase):
    def test_unique_fully_labeled_resources_are_removed_by_exact_id(self):
        token = uuid.uuid4().hex
        labels = (
            f"com.designmachines.depot.scope-id=smoke-{token}",
            f"com.designmachines.depot.run-id=smoke-{token}",
            "com.designmachines.depot.node-id=live-docker-smoke",
            "com.designmachines.depot.lifecycle=chunk",
            "com.designmachines.depot.cleanup-policy=stop-remove",
        )
        network_id = volume_id = container_id = None

        def docker(*args):
            result = subprocess.run(
                ("docker",) + args, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()

        try:
            label_args = tuple(value for label in labels for value in ("--label", label))
            network_id = docker("network", "create", *label_args, f"wk-smoke-net-{token}")
            volume_id = docker("volume", "create", *label_args, f"wk-smoke-vol-{token}")
            container_id = docker(
                "create", *label_args, "--network", network_id,
                "--name", f"wk-smoke-container-{token}", "busybox:latest", "true",
            )
            docker("start", container_id)
            docker("stop", "--time", "2", container_id)
        finally:
            cleanup_failures = []
            if container_id:
                result = subprocess.run(
                    ("docker", "container", "rm", "--force", container_id),
                    text=True, capture_output=True, check=False,
                )
                if result.returncode != 0:
                    cleanup_failures.append(("container", result.stderr))
            if network_id:
                result = subprocess.run(
                    ("docker", "network", "rm", network_id),
                    text=True, capture_output=True, check=False,
                )
                if result.returncode != 0:
                    cleanup_failures.append(("network", result.stderr))
            if volume_id:
                result = subprocess.run(
                    ("docker", "volume", "rm", volume_id),
                    text=True, capture_output=True, check=False,
                )
                if result.returncode != 0:
                    cleanup_failures.append(("volume", result.stderr))
            self.assertEqual([], cleanup_failures, cleanup_failures)
