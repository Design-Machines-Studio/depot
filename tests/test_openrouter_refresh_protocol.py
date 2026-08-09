"""Contract tests for independent OpenRouter matrix refresh provenance."""

import json
from pathlib import Path
import unittest


MATRIX_PATH = (
    Path(__file__).parents[1]
    / "plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
)


class OpenRouterRefreshProtocolTests(unittest.TestCase):
    def test_routing_and_native_cost_own_disjoint_snapshot_paths(self):
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        protocol = matrix["refresh_protocol"]
        self.assertIn("routing", protocol)
        self.assertIn("native_api_equivalent_cost", protocol)
        routing = protocol["routing"]
        native = protocol["native_api_equivalent_cost"]

        routing_paths = ["snapshot_date", "models[*].snapshot_date"]
        native_paths = [
            "native_api_equivalent_cost.snapshot_date",
            "native_api_equivalent_cost.models[*].snapshot_date",
        ]
        self.assertEqual(routing["owned_snapshot_paths"], routing_paths)
        self.assertEqual(routing["preserved_snapshot_paths"], native_paths)
        self.assertEqual(native["owned_snapshot_paths"], native_paths)
        self.assertEqual(native["preserved_snapshot_paths"], routing_paths)

    def test_refresh_procedures_point_to_current_documentation_headings(self):
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        protocol = matrix["refresh_protocol"]
        self.assertIn("routing", protocol)
        self.assertIn("native_api_equivalent_cost", protocol)
        self.assertEqual(
            protocol["routing"]["documented_in"],
            "model-selection.md -- Refreshing the routing matrix",
        )
        self.assertEqual(
            protocol["native_api_equivalent_cost"]["documented_in"],
            "model-selection.md -- Refreshing native API-equivalent cost evidence",
        )


if __name__ == "__main__":
    unittest.main()
