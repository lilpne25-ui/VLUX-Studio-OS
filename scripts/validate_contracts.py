from __future__ import annotations

"""Validate public JSON contracts against the schemas in ``contracts/``.

The repository avoids a heavyweight dependency for this check. This module
implements the small JSON Schema subset used by the published V0.5 contracts:
``$ref`` into ``$defs``, ``type``, ``required``, ``properties``, ``items``,
``const``, ``enum``, ``anyOf``, ``minimum`` and ``maximum``.

Usage:
    python scripts/validate_contracts.py contracts/attention-lab.v0.1.schema.json report.json
    python scripts/validate_contracts.py --defaults
"""

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class ContractError(ValueError):
    pass


TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _matches_type(value: Any, name: str) -> bool:
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    expected = TYPES.get(name)
    return expected is not None and isinstance(value, expected)


def _resolve(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise ContractError(f"unsupported_ref:{ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(value: Any, schema: dict, root: dict | None = None, path: str = "$") -> None:
    root = root or schema
    if "$ref" in schema:
        validate(value, _resolve(schema["$ref"], root), root, path)
        return
    if "anyOf" in schema:
        errors = []
        for option in schema["anyOf"]:
            try:
                validate(value, option, root, path)
                return
            except ContractError as exc:
                errors.append(str(exc))
        raise ContractError(f"{path}: no anyOf branch matched: {'; '.join(errors)}")
    if "const" in schema and value != schema["const"]:
        raise ContractError(f"{path}: expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{path}: {value!r} not in {schema['enum']!r}")
    declared = schema.get("type")
    if declared:
        names = declared if isinstance(declared, list) else [declared]
        if not any(_matches_type(value, name) for name in names):
            raise ContractError(f"{path}: expected type {names}, got {type(value).__name__}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ContractError(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], root, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                raise ContractError(f"{path}: unexpected property {key!r}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate(item, schema["items"], root, f"{path}[{index}]")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ContractError(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ContractError(f"{path}: {value} > maximum {schema['maximum']}")


def check_document(schema_path: Path, document_path: Path) -> str:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    document = json.loads(document_path.read_text(encoding="utf-8"))
    validate(document, schema)
    return f"OK {document_path.name} -> {schema_path.name}"


DEFAULTS = [
    ("attention-lab.v0.1.schema.json", "EP011-attention.json"),
    ("attention-lab.v0.1.schema.json", "EP021-attention.json"),
    ("ab-comparison.v0.1.schema.json", "EP011-vs-EP021-ab.json"),
    ("learning-gate.v0.1.schema.json", "learning-status.json"),
]

V06_DEFAULTS = [
    ("creative-review.v0.1.schema.json", "creative-review.json"),
    ("visual-defects.v0.1.schema.json", "visual-defects.json"),
    ("recommended-changes.v0.1.schema.json", "recommended-changes.json"),
    ("production-brief.v0.1.schema.json", "production-brief.json"),
    ("episode-version.v0.1.schema.json", "episode-version.json"),
    ("human-approval.v0.1.schema.json", "human-approval.json"),
    ("human-evaluation.v0.1.schema.json", "human-evaluation.json"),
    ("performance-record.v0.1.schema.json", "performance-record.json"),
    ("performance-comparison.v0.1.schema.json", "performance-comparison.json"),
]

PRODUCTION_GLOB = "production/*.json"


def defaults() -> int:
    failures = 0
    checked = 0
    for reports_root, pairs, label in (
        (ROOT / "reports" / "v05", DEFAULTS, "v05"),
        (ROOT / "reports" / "v06", V06_DEFAULTS, "v06"),
    ):
        if not reports_root.exists():
            print(f"No {label} reports directory; nothing to validate.")
            continue
        for schema_name, document_name in pairs:
            document = reports_root / document_name
            if not document.exists():
                print(f"SKIP missing {document}")
                continue
            checked += 1
            try:
                print(check_document(ROOT / "contracts" / schema_name, document))
            except ContractError as exc:
                failures += 1
                print(f"FAIL {document.name}: {exc}", file=sys.stderr)
    if not checked:
        print("No reports directories with published contracts found.")
    return 1 if failures else 0
    for document in sorted((ROOT / "data").rglob(PRODUCTION_GLOB)):
        try:
            print(check_document(
                ROOT / "contracts" / "production-manifest.v0.1.schema.json", document,
            ))
        except ContractError as exc:
            failures += 1
            print(f"FAIL {document.name}: {exc}", file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    if argv[1:2] == ["--defaults"]:
        return defaults()
    if len(argv) != 3:
        print(__doc__)
        return 2
    try:
        print(check_document(Path(argv[1]), Path(argv[2])))
    except ContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
