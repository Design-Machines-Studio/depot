"""Static contracts for the deliberately small ned:publish-preview playbook."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "plugins/ned/skills/publish-preview"
MUTATION_LOCK = "/home/ned/.local/state/design-machines/publish-preview/mutation.lock"


class PublishPreviewSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        cls.schema = json.loads(
            (SKILL_ROOT / "references/inventory.schema.json").read_text(encoding="utf-8")
        )
        cls.example = json.loads(
            (SKILL_ROOT / "references/inventory.example.json").read_text(encoding="utf-8")
        )
        cls.runbook = (SKILL_ROOT / "references/operator-runbook.md").read_text(
            encoding="utf-8"
        )
        cls.receipt = (SKILL_ROOT / "references/plan-and-receipt.md").read_text(
            encoding="utf-8"
        )

    def test_skill_is_a_playbook_not_a_shipped_runtime(self) -> None:
        self.assertFalse((SKILL_ROOT / "scripts").exists())
        self.assertIn("Operate this as a careful playbook", self.skill)
        self.assertIn("Conversational operations", self.skill)

    def test_required_operations_and_approval_are_explicit(self) -> None:
        for operation in ("list/status", "plan", "publish", "verify", "unpublish"):
            self.assertIn(operation, self.skill)
        self.assertIn("explicit approval", self.skill)
        self.assertIn("changed state invalidates approval", self.skill)

    def test_mutation_lock_uses_the_exact_shared_ned_host_path(self) -> None:
        self.assertIn(MUTATION_LOCK, self.skill)
        self.assertIn(MUTATION_LOCK, self.runbook)

    def test_authority_and_no_dogfood_boundaries_are_explicit(self) -> None:
        for phrase in (
            "ned:operate-ned",
            "ssh ned9000-plain",
            "Never run a general agent as `trav`",
            "separate, explicit dogfood request",
        ):
            self.assertIn(phrase, self.skill)

    def test_inventory_example_is_fictional_unique_and_schema_shaped(self) -> None:
        self.assertEqual(self.example["version"], 1)
        projects = self.example["projects"]
        required = set(self.schema["$defs"]["project"]["required"])
        for project in projects:
            self.assertTrue(required.issubset(project))
            self.assertIn("fictional", json.dumps(project).lower())
        for field in ("id", "hostname", "internalPort"):
            values = [project[field] for project in projects]
            self.assertEqual(len(values), len(set(values)))

    def test_routing_identity_must_match_hostname(self) -> None:
        self.assertIn("`DM-NNN` to map to exactly `dmNNN.asmbly.app`", self.skill)
        self.assertIn("siteSlug", self.schema["$defs"]["project"]["$comment"])

        def identity_matches(project: dict[str, object]) -> bool:
            if project["type"] == "assembly":
                expected = str(project["factoryCode"]).replace("DM-", "dm") + ".asmbly.app"
                return project["hostname"] == expected
            return project["hostname"] == f"{project['siteSlug']}.designmachines.xyz"

        self.assertTrue(all(identity_matches(project) for project in self.example["projects"]))
        assembly = dict(self.example["projects"][0], hostname="dm998.asmbly.app")
        website = dict(
            self.example["projects"][1], hostname="different.designmachines.xyz"
        )
        self.assertFalse(identity_matches(assembly))
        self.assertFalse(identity_matches(website))

    def test_backend_collisions_allow_only_the_canonical_ddev_entrypoint(self) -> None:
        self.assertIn("sole endpoint-uniqueness exception", self.skill)

        def collision_allowed(left: dict[str, object], right: dict[str, object]) -> bool:
            same_endpoint = (
                left["publication"]["backendBinding"], left["internalPort"]
            ) == (right["publication"]["backendBinding"], right["internalPort"])
            if not same_endpoint:
                return True
            return (
                left["type"] == right["type"] == "ddev"
                and left["internalPort"] == 8080
                and left["publication"]["backendBinding"] == "127.0.0.1"
            )

        ddev_left = self.example["projects"][1]
        ddev_right = dict(ddev_left, id="another-ddev", hostname="other.designmachines.xyz")
        compose = dict(ddev_left, type="compose")
        assembly = dict(self.example["projects"][0], internalPort=8080)
        self.assertTrue(collision_allowed(ddev_left, ddev_right))
        self.assertFalse(collision_allowed(ddev_left, compose))
        self.assertFalse(collision_allowed(ddev_left, assembly))

    def test_schema_closes_objects_and_limits_hosts_paths_and_codes(self) -> None:
        project = self.schema["$defs"]["project"]
        self.assertFalse(self.schema["additionalProperties"])
        self.assertFalse(project["additionalProperties"])
        properties = project["properties"]
        self.assertEqual(properties["factoryCode"]["pattern"], "^DM-[0-9]{3}$")
        host_pattern = re.compile(properties["hostname"]["pattern"])
        self.assertTrue(host_pattern.fullmatch("dm023.asmbly.app"))
        self.assertTrue(host_pattern.fullmatch("client-name.designmachines.xyz"))
        for unsafe in (
            "dm23.asmbly.app",
            "other.example.com",
            "client_name.designmachines.xyz",
            "x.designmachines.xyz;id",
        ):
            self.assertIsNone(host_pattern.fullmatch(unsafe))
        path_pattern = re.compile(properties["checkoutPath"]["pattern"])
        self.assertTrue(path_pattern.fullmatch("/home/ned/sites/example-site"))
        for unsafe in ("/tmp/site", "/home/ned/sites/../private", "/home/ned/sites/x;id"):
            self.assertIsNone(path_pattern.fullmatch(unsafe))
        health_pattern = re.compile(properties["health"]["properties"]["path"]["pattern"])
        self.assertTrue(health_pattern.fullmatch("/healthz"))
        for unsafe in ("/../admin", "/health/../admin", "/health;id"):
            self.assertIsNone(health_pattern.fullmatch(unsafe))

    def test_runtime_caddy_cloudflare_kuma_and_rollback_contracts_exist(self) -> None:
        combined = self.skill + self.runbook
        for phrase in (
            "127.0.0.1",
            "honest 404",
            "existing Cloudflare Tunnel",
            "app-scoped Allow policy",
            "Do not edit Kuma SQLite",
            "Remove exact public exposure first",
            "Leave the project running",
        ):
            self.assertIn(phrase, combined)

    def test_browser_and_monitoring_evidence_cannot_be_faked(self) -> None:
        combined = self.skill + self.runbook
        self.assertIn("real browser session", combined)
        self.assertIn("curl", combined)
        self.assertIn("separate clean", combined)
        self.assertIn("Never weaken Access", combined)

    def test_plan_and_receipt_forbid_secrets_and_report_partial_state(self) -> None:
        self.assertIn("provider response", self.receipt)
        self.assertIn("manual-required", self.receipt)
        self.assertIn("ambiguous", self.receipt)
        self.assertIn("Delete only a resource", self.receipt)
        self.assertIn("before the first mutation", self.receipt)
        self.assertIn("Tunnel ingress", self.receipt)
        self.assertIn("fresh rediscovery", self.receipt)
        self.assertNotRegex(
            self.receipt,
            r"(?i)(?:bearer|api[_ -]?key|client[_ -]?secret)\s*[:=]\s*[A-Za-z0-9_-]{12,}",
        )


if __name__ == "__main__":
    unittest.main()
