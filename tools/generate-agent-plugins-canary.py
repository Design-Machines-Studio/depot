#!/usr/bin/env python3
"""Generate and validate Depot's allowlisted Agent Plugins v1 canary.

Agent Plugins 1.0.0 is a Working Draft. This tool proves only fixed-location
skill discovery for craft-developer. Craft MCP portability is unsupported by
the current format/runtime contract, so this tool never generates mcp.json.

The official plugin schema is vendored byte-for-byte from SCHEMA_URL. Routine
generation and validation are offline; schema retrieval is intentionally not
implemented here.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = REPO_ROOT / "plugins"
SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
SCHEMA_PATH = REPO_ROOT / "tools" / "schemas" / "agent-plugins" / "1.0.0" / "plugin.schema.json"
SCHEMA_SHA256 = "0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883"
CANARY_PLUGINS = ("craft-developer",)
SUPPORTED_METADATA = (
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
)
ALLOWED_FIELDS = frozenset({"$schema", "name", *SUPPORTED_METADATA, "extensions"})
AUTHOR_FIELDS = frozenset({"name", "email", "url"})
NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


class CanaryError(ValueError):
    """A focused canary generation or validation error."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CanaryError(f"missing {path.relative_to(REPO_ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise CanaryError(f"invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}") from exc
    if type(document) is not dict:
        raise CanaryError(f"{path.relative_to(REPO_ROOT)} must contain a JSON object")
    return document


def dump_json(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def generated_is_stale(actual: str, expected: str) -> bool:
    return actual != expected


def validate_vendored_schema() -> None:
    try:
        schema_bytes = SCHEMA_PATH.read_bytes()
    except FileNotFoundError as exc:
        raise CanaryError(f"missing {SCHEMA_PATH.relative_to(REPO_ROOT)}") from exc

    digest = hashlib.sha256(schema_bytes).hexdigest()
    if digest != SCHEMA_SHA256:
        raise CanaryError(f"vendored schema digest mismatch: expected {SCHEMA_SHA256}, found {digest}")

    schema = load_json(SCHEMA_PATH)
    properties = schema.get("properties")
    if schema.get("$id") != SCHEMA_URL:
        raise CanaryError("vendored schema $id does not match the Agent Plugins v1 identifier")
    if type(properties) is not dict or set(properties) != ALLOWED_FIELDS:
        raise CanaryError("vendored schema closed top-level field set changed")
    if schema.get("required") != ["$schema", "name"] or schema.get("additionalProperties") is not False:
        raise CanaryError("vendored schema required or closed-object contract changed")
    if properties["$schema"].get("const") != SCHEMA_URL:
        raise CanaryError("vendored schema identifier constraint changed")
    author = properties.get("author", {})
    if set(author.get("properties", {})) != AUTHOR_FIELDS or author.get("additionalProperties") is not False:
        raise CanaryError("vendored schema closed author field set changed")


def canonical_path(plugin_name: str) -> Path:
    return PLUGINS_DIR / plugin_name / ".claude-plugin" / "plugin.json"


def generated_path(plugin_name: str) -> Path:
    return PLUGINS_DIR / plugin_name / "plugin.json"


def expected_manifest(canonical: dict[str, Any]) -> dict[str, Any]:
    if "name" not in canonical:
        raise CanaryError("canonical Claude manifest is missing name")
    manifest: dict[str, Any] = {"$schema": SCHEMA_URL, "name": canonical["name"]}
    for field in SUPPORTED_METADATA:
        if field in canonical:
            manifest[field] = canonical[field]
    return manifest


def manifest_errors(manifest: Any, canonical: dict[str, Any]) -> list[str]:
    if type(manifest) is not dict:
        return ["manifest must be a JSON object"]

    errors: list[str] = []
    missing = {"$schema", "name"} - set(manifest)
    unknown = set(manifest) - ALLOWED_FIELDS
    if missing:
        errors.append(f"missing required fields: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"unknown top-level fields: {', '.join(sorted(unknown))}")

    if "$schema" in manifest and manifest["$schema"] != SCHEMA_URL:
        errors.append(f"$schema must be {SCHEMA_URL}")

    name = manifest.get("name")
    if "name" in manifest and (
        type(name) is not str or not 1 <= len(name) <= 64 or NAME_PATTERN.fullmatch(name) is None
    ):
        errors.append("name does not satisfy Agent Plugins v1 syntax")

    for field in ("version", "description", "homepage", "repository", "license"):
        if field in manifest and type(manifest[field]) is not str:
            errors.append(f"{field} must be a string")

    if "keywords" in manifest:
        keywords = manifest["keywords"]
        if type(keywords) is not list or any(type(item) is not str for item in keywords):
            errors.append("keywords must be an array of strings")

    if "author" in manifest:
        author = manifest["author"]
        if type(author) is not dict:
            errors.append("author must be an object")
        else:
            unknown_author = set(author) - AUTHOR_FIELDS
            if unknown_author:
                errors.append(f"unknown author fields: {', '.join(sorted(unknown_author))}")
            for field, value in author.items():
                if field in AUTHOR_FIELDS and type(value) is not str:
                    errors.append(f"author.{field} must be a string")

    if "extensions" in manifest:
        extensions = manifest["extensions"]
        if type(extensions) is not dict or any(type(value) is not dict for value in extensions.values()):
            errors.append("extensions must be an object whose values are objects")

    try:
        expected = expected_manifest(canonical)
    except CanaryError as exc:
        errors.append(str(exc))
    else:
        if manifest != expected:
            errors.append("manifest metadata does not match the canonical Claude manifest")
    return errors


def discover_skills(plugin_name: str) -> list[str]:
    skills_dir = PLUGINS_DIR / plugin_name / "skills"
    if not skills_dir.is_dir():
        raise CanaryError(f"{plugin_name}: fixed skills/ directory is missing")

    skills: list[str] = []
    for child in sorted(skills_dir.iterdir()):
        skill_file = child / "SKILL.md"
        if not child.is_dir() or not skill_file.is_file():
            continue
        text = skill_file.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0] != "---":
            raise CanaryError(f"{skill_file.relative_to(REPO_ROOT)} lacks frontmatter")
        try:
            closing = lines[1:].index("---") + 1
        except ValueError as exc:
            raise CanaryError(f"{skill_file.relative_to(REPO_ROOT)} has unclosed frontmatter") from exc
        names = [line.removeprefix("name:").strip() for line in lines[1:closing] if line.startswith("name:")]
        if names != [child.name]:
            raise CanaryError(f"{skill_file.relative_to(REPO_ROOT)} name must match its directory")
        skills.append(child.name)

    if not skills:
        raise CanaryError(f"{plugin_name}: no immediate skills/*/SKILL.md entries found")
    return skills


def validate_canary(plugin_name: str, manifest: dict[str, Any], canonical: dict[str, Any]) -> list[str]:
    if plugin_name not in CANARY_PLUGINS:
        raise CanaryError(f"{plugin_name}: not in the explicit Agent Plugins canary allowlist")
    errors = manifest_errors(manifest, canonical)
    if canonical.get("name") != plugin_name:
        errors.append("canonical manifest name does not match the allowlisted plugin")
    if manifest.get("name") != plugin_name:
        errors.append("generated manifest name does not match the allowlisted plugin")
    if (PLUGINS_DIR / plugin_name / "mcp.json").exists():
        errors.append("portable mcp.json must remain absent for the Craft skills-only canary")
    if errors:
        raise CanaryError(f"{plugin_name}: " + "; ".join(errors))
    return discover_skills(plugin_name)


def generate() -> None:
    validate_vendored_schema()
    for plugin_name in CANARY_PLUGINS:
        canonical = load_json(canonical_path(plugin_name))
        manifest = expected_manifest(canonical)
        skills = validate_canary(plugin_name, manifest, canonical)
        path = generated_path(plugin_name)
        content = dump_json(manifest)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            print(f"OK    {path.relative_to(REPO_ROOT)} already current")
        else:
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(REPO_ROOT)}")
        print(f"OK    {plugin_name} skills discoverable: {', '.join(skills)}")


def check() -> None:
    validate_vendored_schema()
    for plugin_name in CANARY_PLUGINS:
        canonical = load_json(canonical_path(plugin_name))
        manifest = load_json(generated_path(plugin_name))
        skills = validate_canary(plugin_name, manifest, canonical)
        actual = generated_path(plugin_name).read_text(encoding="utf-8")
        expected = dump_json(expected_manifest(canonical))
        if generated_is_stale(actual, expected):
            raise CanaryError(f"stale {generated_path(plugin_name).relative_to(REPO_ROOT)}")
        print(f"OK    {generated_path(plugin_name).relative_to(REPO_ROOT)} matches canonical metadata")
        print(f"OK    {plugin_name} skills discoverable: {', '.join(skills)}")
    print(f"PASS  Agent Plugins canary ({len(CANARY_PLUGINS)} allowlisted plugin)")


def self_test() -> None:
    canonical = load_json(canonical_path(CANARY_PLUGINS[0]))
    valid = expected_manifest(canonical)
    cases: dict[str, tuple[dict[str, Any], str]] = {}

    for required in ("$schema", "name"):
        candidate = copy.deepcopy(valid)
        del candidate[required]
        cases[f"missing {required}"] = (candidate, "missing required fields")
    for field, value, expected_error in (
        ("$schema", "https://example.invalid/schema.json", "$schema must be"),
        ("capabilities", {}, "unknown top-level fields"),
        *((field, 1, f"{field} must be a string") for field in (
            "version", "description", "homepage", "repository", "license"
        )),
        ("keywords", "craft", "keywords must be an array of strings"),
        ("keywords", ["craft", 5], "keywords must be an array of strings"),
        ("author", "Design Machines", "author must be an object"),
        ("name", "Invalid--Name", "name does not satisfy"),
    ):
        candidate = copy.deepcopy(valid)
        candidate[field] = value
        cases[f"invalid {field}"] = (candidate, expected_error)
    candidate = copy.deepcopy(valid)
    candidate["author"]["company"] = "Design Machines"
    cases["unknown author member"] = (candidate, "unknown author fields")
    candidate = copy.deepcopy(valid)
    candidate["author"]["url"] = 5
    cases["invalid author member type"] = (candidate, "author.url must be a string")
    candidate = copy.deepcopy(valid)
    candidate["description"] += " changed"
    cases["canonical metadata mismatch"] = (candidate, "does not match the canonical")

    failures = []
    for label, (candidate, expected_error) in cases.items():
        errors = manifest_errors(candidate, canonical)
        if not any(expected_error in error for error in errors):
            failures.append(label)
    expected_text = dump_json(valid)
    if not generated_is_stale(expected_text + "\n", expected_text):
        failures.append("stale generated output")

    renamed_canonical = copy.deepcopy(canonical)
    renamed_canonical["name"] = "renamed-plugin"
    try:
        validate_canary(CANARY_PLUGINS[0], expected_manifest(renamed_canonical), renamed_canonical)
    except CanaryError as exc:
        if "canonical manifest name does not match" not in str(exc):
            failures.append("canonical allowlist identity")
    else:
        failures.append("canonical allowlist identity")
    if failures:
        raise CanaryError("self-test failed to reject: " + ", ".join(failures))
    print(f"PASS  Agent Plugins canary rejection self-test ({len(cases) + 2} cases)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="validate schema, output freshness, metadata, and skills")
    mode.add_argument("--self-test", action="store_true", help="exercise focused rejection cases in memory")
    args = parser.parse_args()

    try:
        if args.check:
            check()
        elif args.self_test:
            validate_vendored_schema()
            self_test()
        else:
            generate()
    except (CanaryError, OSError, TypeError) as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
