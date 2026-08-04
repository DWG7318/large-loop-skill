import copy
import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import test_conformance_300 as cf
import test_preflight_300 as pf
import test_run_closure_300 as rc
import test_run_validation_300 as rv
from glk300_fixtures import write_json


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
METHOD_LOCK_PATH = SCRIPTS / "method_lock.py"
CANONICAL_REPOSITORY = "https://github.com/DWG7318/large-loop-skill"
CANONICAL_INVOCATION = "graph-loop-skill"
CANONICAL_VERSION = "3.0.0"


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def load_method_lock():
    if not METHOD_LOCK_PATH.is_file():
        pytest.fail("GLK 3.0 method-lock verifier is missing")
    spec = importlib.util.spec_from_file_location(
        "glk_method_lock_300_tests", METHOD_LOCK_PATH
    )
    if spec is None or spec.loader is None:
        pytest.fail("cannot load GLK 3.0 method-lock verifier")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


def _canonical_sha(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()


def _bundle_sha(root, relative_paths):
    entries = []
    for relative in sorted(relative_paths):
        content = (root / relative).read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return _canonical_sha(entries)


def _write_text(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _base_profile():
    return {
        "profile_id": "PROVENANCE-PROFILE-001",
        "adapter_contract_version": "1.0",
        "allowed_operations": [
            "resolve_binding",
            "verify_issuance",
            "verify_isolation",
            "check_liveness",
        ],
        "trust_root_refs": ["external-trust-root/GLK-RUN-001"],
        "technical_verdicts_forbidden": True,
    }


def _installation(tmp_path, *, profile=None, installation_id="INSTALL-GLK-3"):
    root = tmp_path / installation_id
    root.mkdir(parents=True)
    profile = copy.deepcopy(profile or _base_profile())
    schema_paths = ("bundle/schema/glk.schema.json",)
    adapter_paths = (
        "bundle/scripts/provenance.py",
        "bundle/scripts/run_model.py",
    )
    skill_paths = ("bundle/SKILL.md",) + adapter_paths
    validator_paths = (
        "bundle/scripts/run_validation.py",
        "bundle/scripts/validate_run.py",
    )
    _write_text(root, schema_paths[0], '{"schema":"GLK-3.0"}\n')
    _write_text(root, "bundle/SKILL.md", "# GLK 3.0 six-role no-READY\n")
    _write_text(root, adapter_paths[0], "ADAPTER_CONTRACT_VERSION = '1.0'\n")
    _write_text(root, adapter_paths[1], "ROLE_TYPES = ('RUN_SUPERVISOR', 'WORKER')\n")
    _write_text(root, validator_paths[0], "def validate_loaded_run(package, adapter): ...\n")
    _write_text(root, validator_paths[1], "def main(): ...\n")
    repository_identity_path = "bundle/repository-identity.json"
    write_json(
        root / repository_identity_path,
        {
            "canonical_repository": CANONICAL_REPOSITORY,
            "commit_sha": "1" * 64,
            "release_tag": "v3.0.0",
        },
    )
    profile_path = "bundle/adapter-profile.json"
    write_json(root / profile_path, profile)

    schema_digest = _bundle_sha(root, schema_paths)
    skill_digest = _bundle_sha(root, skill_paths)
    validator_digest = _bundle_sha(root, validator_paths)
    adapter_digest = _bundle_sha(root, adapter_paths)
    profile_digest = _canonical_sha(profile)
    lock = {
        "canonical_repository": CANONICAL_REPOSITORY,
        "invocation": CANONICAL_INVOCATION,
        "commit_sha": "1" * 64,
        "release_tag": "v3.0.0",
        "method_version": CANONICAL_VERSION,
        "schema_bundle_sha256": schema_digest,
        "skill_package_sha256": skill_digest,
        "validator_version": CANONICAL_VERSION,
        "validator_sha256": validator_digest,
        "adapter_profile_id": profile["profile_id"],
        "adapter_contract_version": profile["adapter_contract_version"],
    }
    descriptor = {
        "descriptor_version": "1.0",
        "installation_id": installation_id,
        "declared_root": str(root),
        "repository_identity_exists": True,
        "repository_identity_path": repository_identity_path,
        **lock,
        "schema_bundle_paths": schema_paths,
        "schema_bundle_sha256": schema_digest,
        "skill_package_paths": skill_paths,
        "skill_package_sha256": skill_digest,
        "validator_bundle_paths": validator_paths,
        "validator_bundle_sha256": validator_digest,
        "adapter_profile_path": profile_path,
        "adapter_profile_sha256": profile_digest,
        "adapter_contract_paths": adapter_paths,
        "adapter_contract_sha256": adapter_digest,
        "role_types": (
            "RUN_SUPERVISOR",
            "WORKER",
            "CHECKER",
            "GO_VERIFIER",
            "RUN_VERIFIER",
            "OWNER",
        ),
        "state_vocabulary": ("WAITING_GO", "ACTIVE_GO"),
    }
    return root, lock, profile, descriptor


def _verify(module, lock, profile, descriptors):
    return module.verify_method_lock(lock, profile, tuple(descriptors))


def test_canonical_installation_rehashes_only_declared_bundle_paths(tmp_path):
    module = load_method_lock()
    root, lock, profile, descriptor = _installation(tmp_path)
    poison = tmp_path / "undeclared-stale-installation"
    poison.mkdir()
    _write_text(poison, "READY-2.0.0.txt", "seven-role READY\n")
    report = _verify(module, lock, profile, (descriptor,))
    require_equal(report.status, "PASS", "canonical method lock")
    require_equal(report.reasons, (), "canonical conflicts")
    require_equal(report.checked_roots, (str(root.resolve()),), "declared roots")
    require_equal(report.matched_installation_id, "INSTALL-GLK-3", "installation")
    require_equal(report.projection_kind, "DERIVED_NON_AUTHORITATIVE", "authority")
    require_equal(report.can_advance_run, False, "transition authority")


@pytest.mark.parametrize(
    ("legacy_version", "roles", "states", "expected_reason"),
    [
        (
            "2.0.0",
            ("SUPERVISOR", "GRAPHER", "PLANNER", "WORKER", "CHECKER", "ROUTER", "VERIFICATION"),
            ("READY", "ACTIVE"),
            "R24_STALE_2_0_CONFLICT",
        ),
        (
            "2.4.0",
            ("RUN_SUPERVISOR", "WORKER", "CHECKER", "GO_VERIFIER", "RUN_VERIFIER", "OWNER"),
            ("WAITING_GO", "ACTIVE_GO"),
            "R24_STALE_2_4_CONFLICT",
        ),
        (
            "2.4.9",
            ("RUN_SUPERVISOR", "WORKER", "CHECKER", "GO_VERIFIER", "RUN_VERIFIER", "OWNER"),
            ("WAITING_GO", "ACTIVE_GO"),
            "R24_STALE_2_4_CONFLICT",
        ),
    ],
)
def test_R24_rejects_stale_installation_under_same_invocation(
    tmp_path, legacy_version, roles, states, expected_reason
):
    module = load_method_lock()
    _, lock, profile, canonical = _installation(tmp_path)
    _, _, _, legacy = _installation(tmp_path, installation_id=f"INSTALL-GLK-{legacy_version}")
    legacy["method_version"] = legacy_version
    legacy["release_tag"] = f"v{legacy_version}"
    legacy["role_types"] = roles
    legacy["state_vocabulary"] = states
    report = _verify(module, lock, profile, (canonical, legacy))
    require_equal(report.status, "GLK_SUPPLY_CHAIN_CONFLICT", "legacy conflict")
    require(expected_reason in report.reasons, f"missing {expected_reason}")
    require("R24_DUPLICATE_INVOCATION" in report.reasons, "duplicate invocation omitted")


@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("canonical_repository", "https://github.com/example/wrong", "R25_REPOSITORY_MISMATCH"),
        ("invocation", "legacy-large-loop-skill", "R25_INVOCATION_MISMATCH"),
        ("commit_sha", "2" * 64, "R25_COMMIT_MISMATCH"),
        ("release_tag", "v3.0.1", "R25_RELEASE_TAG_MISMATCH"),
        ("method_version", "3.0.1", "R25_METHOD_VERSION_MISMATCH"),
        ("skill_package_sha256", "3" * 64, "R25_SKILL_BUNDLE_DIGEST_MISMATCH"),
        ("schema_bundle_sha256", "4" * 64, "R25_SCHEMA_BUNDLE_DIGEST_MISMATCH"),
        ("validator_bundle_sha256", "5" * 64, "R25_VALIDATOR_BUNDLE_DIGEST_MISMATCH"),
        ("validator_version", "3.0.1", "R25_VALIDATOR_VERSION_MISMATCH"),
        ("adapter_profile_id", "PROVENANCE-PROFILE-WRONG", "R25_ADAPTER_PROFILE_ID_MISMATCH"),
        ("adapter_profile_sha256", "6" * 64, "R25_ADAPTER_PROFILE_DIGEST_MISMATCH"),
        ("adapter_contract_version", "2.0", "R25_ADAPTER_CONTRACT_VERSION_MISMATCH"),
        ("adapter_contract_sha256", "7" * 64, "R25_ADAPTER_CONTRACT_DIGEST_MISMATCH"),
    ],
)
def test_R25_rejects_every_locked_identity_or_bundle_drift(
    tmp_path, field, value, expected_reason
):
    module = load_method_lock()
    _, lock, profile, descriptor = _installation(tmp_path)
    descriptor[field] = value
    report = _verify(module, lock, profile, (descriptor,))
    require_equal(report.status, "GLK_SUPPLY_CHAIN_CONFLICT", f"{field} conflict")
    require(expected_reason in report.reasons, f"{field} missing {expected_reason}")
    require_equal(tuple(sorted(report.reasons)), report.reasons, "deterministic reasons")


def test_R25_contract_only_validator_digest_cannot_prove_real_validator_bundle(tmp_path):
    module = load_method_lock()
    _, lock, profile, descriptor = _installation(tmp_path)
    validation = rv.load_validation()
    require(
        validation.RUN_VALIDATOR_DIGEST != lock["validator_sha256"],
        "synthetic validator accidentally equals contract digest",
    )
    descriptor["validator_bundle_sha256"] = validation.RUN_VALIDATOR_DIGEST
    report = _verify(module, lock, profile, (descriptor,))
    require_equal(report.status, "GLK_SUPPLY_CHAIN_CONFLICT", "contract-only validator")
    require(
        "R25_VALIDATOR_BUNDLE_DIGEST_MISMATCH" in report.reasons,
        "contract constant was accepted as validator implementation",
    )


def test_R25_actual_validator_source_drift_fails_even_when_descriptor_is_updated(tmp_path):
    module = load_method_lock()
    root, lock, profile, descriptor = _installation(tmp_path)
    validator_path = descriptor["validator_bundle_paths"][0]
    _write_text(root, validator_path, "def validate_loaded_run(package, adapter): return 'drift'\n")
    descriptor["validator_bundle_sha256"] = _bundle_sha(
        root, descriptor["validator_bundle_paths"]
    )
    report = _verify(module, lock, profile, (descriptor,))
    require_equal(report.status, "GLK_SUPPLY_CHAIN_CONFLICT", "validator source drift")
    require(
        "R25_VALIDATOR_BUNDLE_DIGEST_MISMATCH" in report.reasons,
        "actual validator source drift was accepted",
    )


def test_R25_adapter_contract_source_drift_is_not_authorized_by_its_descriptor(tmp_path):
    module = load_method_lock()
    root, lock, profile, descriptor = _installation(tmp_path)
    contract_path = descriptor["adapter_contract_paths"][0]
    _write_text(root, contract_path, "ADAPTER_CONTRACT_VERSION = '1.0'\nDRIFT = True\n")
    descriptor["adapter_contract_sha256"] = _bundle_sha(
        root, descriptor["adapter_contract_paths"]
    )
    report = _verify(module, lock, profile, (descriptor,))
    require_equal(report.status, "GLK_SUPPLY_CHAIN_CONFLICT", "adapter source drift")
    require(
        "R25_SKILL_BUNDLE_DIGEST_MISMATCH" in report.reasons,
        "self-consistent adapter descriptor overrode the locked Skill bundle",
    )


def test_R25_adapter_contract_sources_must_be_members_of_the_locked_skill_bundle(tmp_path):
    module = load_method_lock()
    root, lock, profile, descriptor = _installation(tmp_path)
    detached_path = "bundle/detached/provenance-contract.py"
    _write_text(root, detached_path, "ADAPTER_CONTRACT_VERSION = '1.0'\n")
    descriptor["adapter_contract_paths"] = (detached_path,)
    descriptor["adapter_contract_sha256"] = _bundle_sha(root, (detached_path,))
    report = _verify(module, lock, profile, (descriptor,))
    require_equal(report.status, "GLK_SUPPLY_CHAIN_CONFLICT", "detached adapter contract")
    require(
        "R25_ADAPTER_CONTRACT_NOT_SKILL_LOCKED" in report.reasons,
        "a self-consistent detached adapter contract became authority",
    )


def test_R24_duplicate_invocation_and_missing_repository_identity_fail_closed(tmp_path):
    module = load_method_lock()
    _, lock, profile, first = _installation(tmp_path, installation_id="INSTALL-A")
    _, _, _, second = _installation(tmp_path, installation_id="INSTALL-B")
    duplicate = _verify(module, lock, profile, (first, second))
    require("R24_DUPLICATE_INVOCATION" in duplicate.reasons, "duplicate invocation accepted")
    first["repository_identity_exists"] = False
    missing_identity = _verify(module, lock, profile, (first,))
    require(
        "R25_CANONICAL_REPOSITORY_IDENTITY_MISSING" in missing_identity.reasons,
        "missing repository identity accepted",
    )
    first["repository_identity_exists"] = True
    first["declared_root"] = str(tmp_path / "does-not-exist")
    missing_root = _verify(module, lock, profile, (first,))
    require("R25_DECLARED_ROOT_MISSING" in missing_root.reasons, "missing root accepted")


def test_R25_repository_identity_requires_resolved_local_evidence(tmp_path):
    module = load_method_lock()
    root, lock, profile, descriptor = _installation(tmp_path)
    descriptor["repository_identity_path"] = "bundle/missing-identity.json"
    missing = _verify(module, lock, profile, (descriptor,))
    require(
        "R25_CANONICAL_REPOSITORY_IDENTITY_MISSING" in missing.reasons,
        "self-reported repository existence was trusted",
    )
    descriptor["repository_identity_path"] = "bundle/repository-identity.json"
    write_json(
        root / descriptor["repository_identity_path"],
        {
            "canonical_repository": "https://github.com/example/wrong",
            "commit_sha": lock["commit_sha"],
            "release_tag": lock["release_tag"],
        },
    )
    mismatched = _verify(module, lock, profile, (descriptor,))
    require(
        "R25_REPOSITORY_IDENTITY_MISMATCH" in mismatched.reasons,
        "mismatched local repository identity was accepted",
    )


def _migration_input():
    return {
        "source_version": "2.4.0",
        "package_ref": "history/GLK-2.4.0-RUN-001",
        "artifacts": [
            {"ref": "graph/topology", "kind": "GO_DAG_TOPOLOGY", "semantically_compatible": True},
            {"ref": "graph/causal", "kind": "GO_CAUSAL_TRACE", "semantically_compatible": True},
            {"ref": "contracts/run", "kind": "RUN_CONTRACT", "semantically_compatible": True},
            {"ref": "bindings/worker", "kind": "ROLE_BINDING", "semantically_compatible": False},
            {"ref": "receipts/d1", "kind": "D1_RECEIPT", "proven_3_0": False},
            {"ref": "legacy/cell", "kind": "CELL_RECEIPT", "mutable": True},
            {"ref": "legacy/go", "kind": "GO_RECEIPT", "mutable": True},
            {"ref": "legacy/mixed", "kind": "MIXED_MUTABLE_RECEIPT", "mutable": True},
            {"ref": "bootstrap/pass", "kind": "SAMPLE_BOOTSTRAP_PASS", "state": "READY"},
            {"ref": "template/pass", "kind": "PER_TEMPLATE_RUN_PASS", "state": "PASS"},
            {"ref": "ready/state", "kind": "READY_STATE", "state": "READY"},
        ],
    }


def test_migration_is_draft_only_classification_and_never_upgrades_2_4_trust(tmp_path):
    module = load_method_lock()
    legacy = _migration_input()
    before = copy.deepcopy(legacy)
    report = module.derive_migration_report(legacy)
    require_equal(legacy, before, "historical mutation")
    require_equal(report.status, "DRAFT_ONLY", "migration status")
    require_equal(report.current_evidence_eligible, False, "current evidence")
    require_equal(report.formal_transition_allowed, False, "formal transition")
    require_equal(report.history_mutated, False, "history mutation flag")
    require_equal(report.preserved_refs, ("graph/causal", "graph/topology"), "preserved")
    require_equal(report.revalidate_refs, ("contracts/run",), "revalidate")
    require_equal(
        report.historical_only_refs,
        ("bindings/worker", "receipts/d1"),
        "historical-only",
    )
    require_equal(
        report.discarded_formal_refs,
        (
            "bootstrap/pass",
            "legacy/cell",
            "legacy/go",
            "legacy/mixed",
            "ready/state",
            "template/pass",
        ),
        "discarded constructs",
    )
    require(all(ref.startswith("draft://") for ref in report.new_draft_references), "formal refs emitted")


def _locked_preflight_case(tmp_path, method_module):
    case = cf.build_conformance_case(tmp_path / "run")
    package_module, _, _ = rv.load_prerequisites()
    initial = package_module.load_run_package(case.root)
    profile = json.loads(json.dumps(dict(initial.artifacts_by_type["PROVENANCE_ADAPTER_PROFILE"][0])))
    _, lock_values, _, descriptor = _installation(
        tmp_path, profile=profile, installation_id="INSTALL-PREFLIGHT"
    )
    lock_path, lock = cf._record(case.root, "GLK_METHOD_LOCK")
    lock.update(lock_values)
    write_json(lock_path, lock)
    case = cf.rebuild_conformance_indexes(case)
    _, validation_report, loaded = rc._validate(case)
    require_equal(validation_report.status, "PASS", "locked preflight package")
    preflight = pf.load_preflight()
    simulation = preflight.simulate_run(
        loaded,
        validation_report,
        case.root / "simulation",
        pf._scenario(),
    )
    adapter = pf._readiness_adapter(preflight, loaded)
    return preflight, loaded, validation_report, simulation, adapter, descriptor


def test_preflight_recomputes_method_lock_without_duplicating_validator_or_provenance(tmp_path):
    method_module = load_method_lock()
    preflight, loaded, validation_report, simulation, adapter, descriptor = (
        _locked_preflight_case(tmp_path, method_module)
    )
    report = preflight.derive_preflight_report(
        loaded,
        validation_report,
        adapter,
        dict(loaded.artifacts_by_type["GLK_METHOD_LOCK"][0]),
        simulation,
        current_holds=(),
        observation_deadline="2026-08-03T23:59:59Z",
        installation_descriptors=(descriptor,),
    )
    require_equal(report.status, "PREFLIGHT_PASS", "locked preflight")
    require_equal(len(report.method_lock_report_digest), 64, "method lock report digest")
    bad = copy.deepcopy(descriptor)
    bad["canonical_repository"] = "https://github.com/example/wrong"
    failed = preflight.derive_preflight_report(
        loaded,
        validation_report,
        pf._readiness_adapter(preflight, loaded),
        dict(loaded.artifacts_by_type["GLK_METHOD_LOCK"][0]),
        simulation,
        current_holds=(),
        observation_deadline="2026-08-03T23:59:59Z",
        installation_descriptors=(bad,),
    )
    require_equal(failed.status, "PREFLIGHT_FAIL", "supply-chain conflict preflight")
    require("GLK_SUPPLY_CHAIN_CONFLICT" in failed.failure_codes, "preflight ignored lock conflict")
    require_equal(
        tuple(name for name, _ in adapter.calls).count("verify_issuance"),
        0,
        "method lock duplicated provenance issuance",
    )


@pytest.mark.parametrize("installation_descriptors", [None, ()])
def test_preflight_requires_a_declared_installation_for_method_lock_verification(
    tmp_path, installation_descriptors
):
    method_module = load_method_lock()
    preflight, loaded, validation_report, simulation, adapter, _ = (
        _locked_preflight_case(tmp_path, method_module)
    )
    report = preflight.derive_preflight_report(
        loaded,
        validation_report,
        adapter,
        dict(loaded.artifacts_by_type["GLK_METHOD_LOCK"][0]),
        simulation,
        current_holds=(),
        observation_deadline="2026-08-03T23:59:59Z",
        installation_descriptors=installation_descriptors,
    )
    require_equal(report.status, "PREFLIGHT_FAIL", "unverified preflight")
    require(
        "GLK_SUPPLY_CHAIN_CONFLICT" in report.failure_codes,
        "preflight passed without a declared canonical installation",
    )
