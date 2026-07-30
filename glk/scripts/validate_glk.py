#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

sys.dont_write_bytecode = True
from repository import EXCLUDED_PARTS, build_hash_manifest, sha256


VERSION = "2.4.0"
ROLES = [
    "Run Supervisor",
    "Worker",
    "Checker",
    "GO Verifier",
    "Run Verifier",
    "Owner",
]
REQUIRED = [
    ".gitattributes",
    ".github/workflows/validate.yml",
    "requirements-dev.txt",
    "agents/openai.yaml",
    "README.md",
    "README.zh-CN.md",
    "SPEC.md",
    "SKILL.md",
    "glk/SKILL.md",
    "VERSION",
    "MANIFEST.json",
    "FILE_HASHES.json",
    "MIGRATION.md",
    "CHANGELOG.md",
    "VALIDATION-REPORT.md",
    "glk/schemas/glk.schema.json",
    "glk/scripts/graph_model.py",
    "glk/scripts/run_model.py",
    "glk/scripts/bootstrap_run.py",
    "glk/scripts/build_release.py",
    "glk/scripts/repository.py",
    "glk/templates/RUN_CONTRACT.yaml",
    "glk/templates/ROLE_BINDING.yaml",
    "glk/templates/GO.yaml",
    "glk/templates/GRAPH_BASELINE.yaml",
    "glk/templates/CELL_RECEIPT.yaml",
    "glk/templates/GO_RECEIPT.yaml",
    "glk/templates/RUN_RECEIPT.yaml",
    "glk/templates/GO_CAUSAL_TRACE.yaml",
    "glk/templates/GRAPH_AMENDMENT.yaml",
    "glk/templates/FORMAL_RESOLUTION.yaml",
    "glk/templates/OWNER_ACCEPTANCE.yaml",
    "glk/templates/SECURITY_HANDOFF.yaml",
]
NORMATIVE = [
    "SPEC.md",
    "SKILL.md",
    "README.md",
    "README.zh-CN.md",
    "docs/interpretation-test.md",
    "glk/SKILL.md",
    "glk/references/canonical-dictionary.md",
    "glk/references/causal-impact.md",
    "glk/references/go-graph-construction.md",
    "glk/references/graph-amendment.md",
    "glk/references/non-goals.md",
    "glk/references/owner-acceptance.md",
    "glk/references/roles-and-isolation.md",
    "glk/references/scheduling.md",
    "glk/references/security-boundary.md",
    "glk/references/state-machine.md",
    "glk/references/verification.md",
]
TEMPLATES = {
    "RUN_CONTRACT.yaml": "run_contract",
    "ROLE_BINDING.yaml": "role_binding",
    "GO.yaml": "go",
    "GRAPH_BASELINE.yaml": "graph_baseline",
    "CELL_RECEIPT.yaml": "cell_receipt",
    "GO_RECEIPT.yaml": "go_receipt",
    "RUN_RECEIPT.yaml": "run_receipt",
    "GO_CAUSAL_TRACE.yaml": "go_causal_trace",
    "GRAPH_AMENDMENT.yaml": "graph_amendment",
    "FORMAL_RESOLUTION.yaml": "formal_resolution",
    "OWNER_ACCEPTANCE.yaml": "owner_acceptance",
    "SECURITY_HANDOFF.yaml": "security_handoff",
}


def fail(message: str):
    raise SystemExit(f"FAIL: {message}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_structure(root: Path):
    missing = [relative for relative in REQUIRED if not (root / relative).is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))


def validate_version(root: Path):
    if read(root / "VERSION").strip() != VERSION:
        fail("VERSION file does not contain version 2.4.0")
    manifest = json.loads(read(root / "MANIFEST.json"))
    if manifest.get("version") != VERSION:
        fail("MANIFEST version mismatch")
    if manifest.get("roles") != ROLES:
        fail("MANIFEST must contain exactly the six canonical roles")
    for relative in [
        "SPEC.md",
        "SKILL.md",
        "glk/SKILL.md",
        "README.md",
        "glk/examples/appointment-run.yaml",
    ]:
        if VERSION not in read(root / relative):
            fail(f"version missing from {relative}")
    if read(root / "SKILL.md") != read(root / "glk/SKILL.md"):
        fail("root and packaged Skill entrypoints differ")


def validate_semantics(root: Path):
    combined = "\n".join(read(root / relative) for relative in NORMATIVE)
    forbidden = ["READY", "exactly one ACTIVE", "one-at-a-time", "Grapher", "Planner", "Router"]
    found = [marker for marker in forbidden if marker in combined]
    if found:
        fail("forbidden normative semantics: " + ", ".join(found))
    required = [
        "Run Supervisor",
        "Worker",
        "Checker",
        "GO Verifier",
        "Run Verifier",
        "Owner",
        "fresh Run Supervisor instance",
        "WAITING_GO",
        "ACTIVE_GO",
        "maximal safe ACTIVE_GO set",
        "arbitrary serialization",
        "fake dependency",
        "LOOP_OWNER_ACCEPTED",
        "GO_CAUSAL_TRACE",
        "CAUSAL_SOURCE",
        "DOWNSTREAM_SYMPTOM",
        "source_claim_or_output_refs",
        "actual consumption",
        "incident evidence",
        "explicit symptom set",
        "typed `CANDIDATE`, `EVIDENCE`, or `CLAIM_OR_OUTPUT`",
        "reachability alone",
        "CONFIRMED",
        "UNAFFECTED",
        "current-validity",
        "full-graph replay",
    ]
    missing = [marker for marker in required if marker not in combined]
    if missing:
        fail("required semantics missing: " + ", ".join(missing))


def validate_templates(root: Path):
    schema = json.loads(read(root / "glk/schemas/glk.schema.json"))
    for filename, definition in TEMPLATES.items():
        instance = yaml.safe_load(read(root / "glk/templates" / filename))
        wrapper = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/$defs/{definition}",
            "$defs": schema["$defs"],
        }
        errors = sorted(
            Draft202012Validator(wrapper).iter_errors(instance),
            key=lambda error: list(error.path),
        )
        if errors:
            fail(f"schema validation failed for {filename}: {errors[0].message}")
        if filename == "GO_CAUSAL_TRACE.yaml":
            if instance["source_go"] in instance["symptom_go_ids"]:
                fail("causal trace source cannot be a symptom")
            if instance["observed_at_go"] not in instance["symptom_go_ids"]:
                fail("causal trace observation must be an explicit symptom")
            trace_evidence = set(instance["source_evidence_refs"])
            if any(
                step["confirmation_status"] != "CONFIRMED"
                or not step["incident_evidence_refs"]
                or not set(step["incident_evidence_refs"]).issubset(trace_evidence)
                for step in instance["causal_path"]
            ):
                fail("causal trace path requires confirmed incident evidence")
        if filename == "GRAPH_AMENDMENT.yaml" and not instance["impact_seeds"]:
            fail("graph amendment requires typed impact seeds")


def tracked_files(root: Path):
    if not (root / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return [Path(line) for line in result.stdout.splitlines() if line]


def validate_hygiene(root: Path):
    candidates = tracked_files(root)
    if candidates is None:
        candidates = [path.relative_to(root) for path in root.rglob("*") if path.is_file()]
    bad = [
        path.as_posix()
        for path in candidates
        if any(part in EXCLUDED_PARTS for part in path.parts) or path.suffix == ".pyc"
    ]
    if bad:
        fail("cache or generated artifacts found: " + ", ".join(bad))


def validate_hashes(root: Path):
    declared = json.loads(read(root / "FILE_HASHES.json"))
    if declared.get("algorithm") != "sha256" or declared.get("version") != VERSION:
        fail("hash manifest metadata is invalid")
    expected = build_hash_manifest(root)["files"]
    actual = declared.get("files", {})
    if set(expected) != set(actual):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        fail(f"hash manifest path mismatch; missing={missing}, extra={extra}")
    mismatches = [
        relative
        for relative, digest in actual.items()
        if sha256(root / relative) != digest
    ]
    if mismatches:
        fail("hash mismatch: " + ", ".join(mismatches))


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
    validate_structure(root)
    validate_version(root)
    validate_semantics(root)
    validate_templates(root)
    validate_hygiene(root)
    validate_hashes(root)
    print("PASS: GLK 2.4.0 structure, semantics, schema, hashes, and hygiene are valid.")


if __name__ == "__main__":
    main()
