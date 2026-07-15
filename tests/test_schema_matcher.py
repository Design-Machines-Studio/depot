import unittest

from tests import schema_matches


class SchemaMatcherTests(unittest.TestCase):
    def test_pattern_is_enforced(self):
        self.assertTrue(schema_matches("case-sha256:" + "a" * 64, {
            "type": "string", "pattern": r"^case-sha256:[0-9a-f]{64}$",
        }))
        self.assertFalse(schema_matches("case-sha256:not-a-digest", {
            "type": "string", "pattern": r"^case-sha256:[0-9a-f]{64}$",
        }))

    def test_prefix_items_apply_by_position_and_items_apply_after_prefix(self):
        schema = {
            "type": "array",
            "prefixItems": [{"const": 1}, {"const": 2}],
            "items": {"const": 3},
        }
        self.assertTrue(schema_matches([1, 2, 3], schema))
        self.assertFalse(schema_matches([2, 1, 3], schema))
        self.assertFalse(schema_matches([1, 2, 4], schema))

    def test_contains_and_one_of_are_enforced(self):
        self.assertTrue(schema_matches([1, 2], {
            "type": "array", "contains": {"const": 2},
        }))
        self.assertFalse(schema_matches([1, 3], {
            "type": "array", "contains": {"const": 2},
        }))
        self.assertTrue(schema_matches("a", {
            "oneOf": [{"const": "a"}, {"const": "b"}],
        }))
        self.assertFalse(schema_matches("a", {
            "oneOf": [{"type": "string"}, {"const": "a"}],
        }))

    def test_conditional_requires_its_discriminator(self):
        schema = {
            "type": "object",
            "if": {
                "required": ["kind"],
                "properties": {"kind": {"const": "strict"}},
            },
            "then": {"required": ["proof"]},
        }
        self.assertTrue(schema_matches({}, schema))
        self.assertFalse(schema_matches({"kind": "strict"}, schema))
        self.assertTrue(schema_matches({"kind": "strict", "proof": True}, schema))


if __name__ == "__main__":
    unittest.main()
