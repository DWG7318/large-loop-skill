#!/usr/bin/env python3
import json
import hashlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

import yaml
from jsonschema import Draft202012Validator

sys.dont_write_bytecode = True
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from repository import EXCLUDED_PARTS, build_hash_manifest, sha256


VERSION = "3.1.0"
VALIDATION_SCOPE = "REPOSITORY_DISTRIBUTION"
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
    "glk/scripts/graph_kernel.py",
    "glk/scripts/artifact_model.py",
    "glk/scripts/run_model.py",
    "glk/scripts/run_package.py",
    "glk/scripts/run_control.py",
    "glk/scripts/run_validation.py",
    "glk/scripts/validate_run.py",
    "glk/scripts/validate_glk.py",
    "glk/scripts/provenance.py",
    "glk/scripts/preflight.py",
    "glk/scripts/method_lock.py",
    "glk/scripts/worker_wake.py",
    "glk/scripts/run_patrol.py",
    "glk/scripts/cell_capacity.py",
    "tools/bootstrap_run.py",
    "tools/build_release.py",
    "tools/repository.py",
    "tools/validate_glk.py",
    "glk/templates/RUN_CONTRACT.yaml",
    "glk/templates/ROLE_BINDING.yaml",
    "glk/templates/GO.yaml",
    "glk/templates/GRAPH_BASELINE.yaml",
    "glk/templates/GLK_METHOD_LOCK.yaml",
    "glk/templates/PROVENANCE_ADAPTER_PROFILE.yaml",
    "glk/templates/CELL_MANIFEST.yaml",
    "glk/templates/CELL_MANIFEST_AMENDMENT.yaml",
    "glk/templates/D0_RECEIPT.yaml",
    "glk/templates/D1_RECEIPT.yaml",
    "glk/templates/GO_CANDIDATE_CLOSURE.yaml",
    "glk/templates/SUPERVISOR_ADMISSION.yaml",
    "glk/templates/PREFLIGHT_ADMISSION.yaml",
    "glk/templates/RUN_PACKAGE_INDEX.yaml",
    "glk/templates/D2_RECEIPT.yaml",
    "glk/templates/GRAPH_EVENT.yaml",
    "glk/templates/MONITOR_CONTROL.yaml",
    "glk/templates/WORKER_CHECKER_WAKE_BINDING.yaml",
    "glk/templates/WAKE_ATTEMPT.yaml",
    "glk/templates/WAKE_ACK.yaml",
    "glk/templates/PENDING_WAKE.yaml",
    "glk/templates/DEVICE_CAPACITY_PROFILE.yaml",
    "glk/templates/CUMULATIVE_ENGINEERING_LOAD.yaml",
    "glk/templates/CELL_WORK_ESTIMATE.yaml",
    "glk/templates/CELL_CAPACITY_GATE.yaml",
    "glk/templates/CELL_PLAN_AMENDMENT.yaml",
    "glk/templates/CELL_SCOPE_EXCEEDED.yaml",
    "glk/templates/CHECKER_PROGRESS_EVENT.yaml",
    "glk/templates/SUPERVISOR_PROGRESS_EVENT.yaml",
    "glk/templates/D3_RECEIPT.yaml",
    "glk/templates/GO_CAUSAL_TRACE.yaml",
    "glk/templates/GRAPH_AMENDMENT.yaml",
    "glk/templates/FORMAL_RESOLUTION.yaml",
    "glk/templates/OWNER_ACCEPTANCE.yaml",
    "glk/templates/SECURITY_HANDOFF.yaml",
    "glk/references/artifact-authority.md",
    "glk/references/run-package-validation.md",
    "glk/references/readiness-and-liveness.md",
    "glk/references/supply-chain.md",
    "glk/references/worker-wake.md",
    "glk/references/run-patrol.md",
    "glk/references/layered-progress.md",
    "glk/references/cell-capacity.md",
]
FORBIDDEN_CURRENT = [
    "glk/templates/CELL_RECEIPT.yaml",
    "glk/templates/GO_RECEIPT.yaml",
    "glk/templates/RUN_RECEIPT.yaml",
]
NORMATIVE = [
    "SPEC.md",
    "SKILL.md",
    "README.md",
    "README.zh-CN.md",
    "docs/interpretation-test.md",
    "glk/SKILL.md",
    "glk/references/canonical-dictionary.md",
    "glk/references/artifact-authority.md",
    "glk/references/run-package-validation.md",
    "glk/references/readiness-and-liveness.md",
    "glk/references/supply-chain.md",
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
    "glk/references/worker-wake.md",
    "glk/references/run-patrol.md",
    "glk/references/layered-progress.md",
    "glk/references/cell-capacity.md",
]
TEMPLATES = {
    "RUN_CONTRACT.yaml": "run_contract",
    "GLK_METHOD_LOCK.yaml": "glk_method_lock",
    "PROVENANCE_ADAPTER_PROFILE.yaml": "provenance_adapter_profile",
    "ROLE_BINDING.yaml": "role_binding_300",
    "GO.yaml": "go",
    "GRAPH_BASELINE.yaml": "graph_baseline",
    "CELL_MANIFEST.yaml": "cell_manifest",
    "CELL_MANIFEST_AMENDMENT.yaml": "cell_manifest_amendment",
    "D0_RECEIPT.yaml": "d0_receipt",
    "D1_RECEIPT.yaml": "d1_receipt",
    "GO_CANDIDATE_CLOSURE.yaml": "go_candidate_closure",
    "SUPERVISOR_ADMISSION.yaml": "supervisor_admission",
    "PREFLIGHT_ADMISSION.yaml": "preflight_admission",
    "RUN_PACKAGE_INDEX.yaml": "run_package_index",
    "D2_RECEIPT.yaml": "d2_receipt",
    "GRAPH_EVENT.yaml": "graph_event",
    "MONITOR_CONTROL.yaml": "monitor_control",
    "WORKER_CHECKER_WAKE_BINDING.yaml": "worker_checker_wake_binding",
    "WAKE_ATTEMPT.yaml": "wake_attempt",
    "WAKE_ACK.yaml": "wake_ack",
    "PENDING_WAKE.yaml": "pending_wake",
    "DEVICE_CAPACITY_PROFILE.yaml": "device_capacity_profile",
    "CUMULATIVE_ENGINEERING_LOAD.yaml": "cumulative_engineering_load",
    "CELL_WORK_ESTIMATE.yaml": "cell_work_estimate",
    "CELL_CAPACITY_GATE.yaml": "cell_capacity_gate",
    "CELL_PLAN_AMENDMENT.yaml": "cell_plan_amendment",
    "CELL_SCOPE_EXCEEDED.yaml": "cell_scope_exceeded",
    "CHECKER_PROGRESS_EVENT.yaml": "checker_progress_event",
    "SUPERVISOR_PROGRESS_EVENT.yaml": "supervisor_progress_event",
    "D3_RECEIPT.yaml": "d3_receipt",
    "GO_CAUSAL_TRACE.yaml": "go_causal_trace",
    "GRAPH_AMENDMENT.yaml": "graph_amendment",
    "FORMAL_RESOLUTION.yaml": "formal_resolution",
    "OWNER_ACCEPTANCE.yaml": "owner_acceptance_300",
    "SECURITY_HANDOFF.yaml": "security_handoff_300",
}


def fail(message: str):
    raise SystemExit(f"FAIL: {message}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_structure(root: Path):
    missing = [relative for relative in REQUIRED if not (root / relative).is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))
    legacy = [relative for relative in FORBIDDEN_CURRENT if (root / relative).exists()]
    if legacy:
        fail("legacy mixed receipt templates are not current formal types: " + ", ".join(legacy))


def validate_version(root: Path):
    if read(root / "VERSION").strip() != VERSION:
        fail("VERSION file does not contain version 3.1.0")
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
    scheduling_text = combined.replace("GO_CANDIDATE_READY", "")
    forbidden = ["READY", "exactly one ACTIVE", "one-at-a-time", "Grapher", "Planner", "Router"]
    found = [marker for marker in forbidden if marker in scheduling_text]
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
        "strictest source disposition",
        "same current artifact",
        "D0/D1/D2",
        "reachability alone",
        "CONFIRMED",
        "UNAFFECTED",
        "current-validity",
        "full-graph replay",
        "Worker-only",
        "WAKE_ACK",
        "PENDING_WAKE",
        "gpt-5.6-luna",
        "UNAUTHORIZED_THREAD_PIN",
        "PIN_PROVENANCE_UNKNOWN",
        "DELIVERED",
        "GO_CANDIDATE_READY",
        "DEVICE_CAPACITY_PROFILE",
        "CUMULATIVE_ENGINEERING_LOAD",
        "CELL_CAPACITY_GATE",
        "SPLIT_REQUIRED",
        "CELL_OVERSIZE_SEVERE",
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
        if filename == "GRAPH_AMENDMENT.yaml":
            if not instance["impact_seeds"]:
                fail("graph amendment requires typed impact seeds")
            source_items = [
                item
                for item in instance["impact_slice"]
                if item["go_id"] == instance["source_go"]
            ]
            if (
                len(source_items) != 1
                or source_items[0]["disposition"]
                != instance["source_disposition"]
            ):
                fail("graph amendment source disposition is inconsistent")
            seed_kinds = {seed["kind"] for seed in instance["impact_seeds"]}
            if seed_kinds & {"CANDIDATE", "CLAIM_OR_OUTPUT"} and (
                instance["source_disposition"] not in {"REWORK", "QUARANTINE"}
                or not source_items[0]["invalidated_candidate_refs"]
                or not source_items[0]["invalidated_receipt_refs"]
            ):
                fail("artifact-invalidating seed requires deep source invalidation")


def validate_validator_bundle(root: Path):
    manifest = json.loads(read(root / "MANIFEST.json"))
    bundle = manifest.get("run_validator_bundle")
    if not isinstance(bundle, dict):
        fail("MANIFEST run validator bundle is missing")
    paths = bundle.get("paths")
    if paths != ["glk/scripts/run_validation.py", "glk/scripts/validate_run.py"]:
        fail("MANIFEST run validator bundle paths are invalid")
    entries = [
        {"path": relative, "sha256": sha256(root / relative)}
        for relative in paths
    ]
    actual = hashlib.sha256(
        json.dumps(entries, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    if bundle.get("sha256") != actual:
        fail("MANIFEST run validator bundle digest mismatch")
    lock = yaml.safe_load(read(root / "glk/templates/GLK_METHOD_LOCK.yaml"))
    if lock.get("validator_sha256") != actual:
        fail("method lock does not bind the real Run validator bundle")


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


def validate_repository(root: Path):
    validate_structure(root)
    validate_version(root)
    validate_semantics(root)
    validate_templates(root)
    validate_validator_bundle(root)
    validate_hygiene(root)
    validate_hashes(root)


def validate_release_zip(source: Path):
    prefix = f"GLK-{VERSION}"
    with zipfile.ZipFile(source) as archive:
        bad_member = archive.testzip()
        if bad_member:
            fail(f"ZIP integrity failed at {bad_member}")
        members = archive.infolist()
        if not members:
            fail("release ZIP is empty")
        for member in members:
            relative = PurePosixPath(member.filename)
            unix_mode = member.external_attr >> 16
            if (
                "\\\\" in member.filename
                or relative.is_absolute()
                or ".." in relative.parts
                or not relative.parts
                or relative.parts[0] != prefix
            ):
                fail(f"release ZIP path is outside {prefix}: {member.filename}")
            if unix_mode & 0o170000 == 0o120000:
                fail(f"release ZIP contains a symbolic link: {member.filename}")
        with tempfile.TemporaryDirectory(prefix="glk-validate-") as temporary:
            archive.extractall(temporary)
            validate_repository(Path(temporary) / prefix)


def main():
    source = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
    if source.is_file():
        if source.suffix.lower() != ".zip":
            fail("repository distribution input must be a directory or ZIP archive")
        validate_release_zip(source)
    else:
        validate_repository(source)
    print(
        "PASS: GLK 3.1.0 scope=REPOSITORY_DISTRIBUTION "
        "structure, semantics, schema, hashes, and hygiene are valid."
    )


if __name__ == "__main__":
    main()
