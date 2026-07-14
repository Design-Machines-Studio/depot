import unittest

from workflow_kernel.adapters.base import (
    HostCapabilities, HostCapability, IsolationMode, IsolationRequirements,
)
from workflow_kernel.adapters.isolation import IsolationSelector


MODE_CAPABILITY = {
    IsolationMode.REMOTE_SANDBOX: HostCapability.REMOTE_SANDBOX,
    IsolationMode.CONTAINER: HostCapability.CONTAINER,
    IsolationMode.WORKTREE: HostCapability.WORKTREE,
    IsolationMode.SEQUENTIAL_BRANCH: HostCapability.SEQUENTIAL_BRANCH,
}


class IsolationTests(unittest.TestCase):
    def test_all_modes_select_when_declared(self):
        selector = IsolationSelector()
        for mode, capability in MODE_CAPABILITY.items():
            with self.subTest(mode=mode.value):
                host = HostCapabilities("host", (capability,))
                decision = selector.select(IsolationRequirements(mode), host)
                self.assertFalse(decision.blocked)
                self.assertEqual(decision.selected, mode)
                self.assertIsNone(decision.degraded_from)

    def test_degradation_follows_policy_order_and_records_reason(self):
        host = HostCapabilities("host", (HostCapability.WORKTREE, HostCapability.SEQUENTIAL_BRANCH))
        decision = IsolationSelector().select(
            IsolationRequirements(IsolationMode.REMOTE_SANDBOX), host,
        )
        self.assertEqual(decision.selected, IsolationMode.WORKTREE)
        self.assertEqual(decision.degraded_from, IsolationMode.REMOTE_SANDBOX)
        self.assertEqual(decision.degraded_to, IsolationMode.WORKTREE)
        self.assertEqual(decision.reason_code, "preferred_isolation_unavailable")

    def test_policy_forbidden_downgrade_blocks_instead_of_using_branch(self):
        host = HostCapabilities("host", (HostCapability.SEQUENTIAL_BRANCH,))
        decision = IsolationSelector().select(
            IsolationRequirements(IsolationMode.REMOTE_SANDBOX), host,
        )
        self.assertTrue(decision.blocked)
        self.assertIsNone(decision.selected)
        self.assertEqual(decision.degraded_from, IsolationMode.REMOTE_SANDBOX)
        self.assertEqual(decision.degraded_to, IsolationMode.SEQUENTIAL_BRANCH)
        self.assertEqual(decision.reason_code, "isolation_downgrade_forbidden")

    def test_request_can_forbid_any_degradation(self):
        host = HostCapabilities("host", (HostCapability.CONTAINER,))
        decision = IsolationSelector().select(
            IsolationRequirements(IsolationMode.REMOTE_SANDBOX, allow_degradation=False), host,
        )
        self.assertTrue(decision.blocked)
        self.assertEqual(decision.reason_code, "isolation_degradation_disallowed")


if __name__ == "__main__":
    unittest.main()
