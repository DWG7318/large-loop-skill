import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Tuple


CANONICAL_REPOSITORY = "https://github.com/DWG7318/large-loop-skill"
CANONICAL_INVOCATION = "graph-loop-skill"
CANONICAL_METHOD_VERSION = "3.0.0"
CANONICAL_RELEASE_TAG = "v3.0.0"
CANONICAL_ADAPTER_CONTRACT_VERSION = "1.0"
SUPPLY_CHAIN_CONFLICT = "GLK_SUPPLY_CHAIN_CONFLICT"

PRESERVE_KINDS = frozenset(
    {
        "GO_DAG_TOPOLOGY",
        "GO_CAUSAL_TRACE",
        "ACTUAL_CONSUMPTION_EDGE",
        "GRAPH_AMENDMENT_HISTORY",
        "IMPACT_SLICE_HISTORY",
    }
)
REVALIDATE_KINDS = frozenset(
    {
        "RUN_CONTRACT",
        "GO_CONTRACT",
        "GRAPH_BASELINE",
        "GRAPH_AMENDMENT",
        "FORMAL_RESOLUTION",
        "CANDIDATE_INDEX",
        "EVIDENCE_INDEX",
    }
)
HISTORICAL_ONLY_KINDS = frozenset(
    {
        "ROLE_BINDING",
        "D0_RECEIPT",
        "D1_RECEIPT",
        "D2_RECEIPT",
        "D3_RECEIPT",
        "CONTROL_LEDGER",
        "VALIDATION_REPORT",
        "BOOTSTRAP_WORKSPACE",
    }
)
DISCARD_FORMAL_KINDS = frozenset(
    {
        "CELL_RECEIPT",
        "GO_RECEIPT",
        "MIXED_MUTABLE_RECEIPT",
        "SAMPLE_BOOTSTRAP_PASS",
        "PER_TEMPLATE_RUN_PASS",
        "READY_STATE",
    }
)


class MethodLockError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class MethodLockReport:
    status: str
    reasons: Tuple[str, ...]
    checked_installation_ids: Tuple[str, ...]
    checked_roots: Tuple[str, ...]
    matched_installation_id: str | None
    method_lock_digest: str
    installation_descriptor_digests: Tuple[str, ...]
    projection_kind: str
    can_advance_run: bool
    report_digest: str


@dataclass(frozen=True)
class MigrationReport:
    status: str
    source_version: str
    source_package_ref: str
    preserved_refs: Tuple[str, ...]
    revalidate_refs: Tuple[str, ...]
    historical_only_refs: Tuple[str, ...]
    discarded_formal_refs: Tuple[str, ...]
    new_draft_references: Tuple[str, ...]
    current_evidence_eligible: bool
    formal_transition_allowed: bool
    history_mutated: bool
    projection_kind: str
    report_digest: str


def canonical_sha256(value):
    def thaw(current):
        if isinstance(current, Mapping):
            return {key: thaw(item) for key, item in current.items()}
        if isinstance(current, (tuple, list)):
            return [thaw(item) for item in current]
        return current

    return hashlib.sha256(
        json.dumps(
            thaw(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def method_lock_digest(method_lock):
    fields = (
        "canonical_repository",
        "invocation",
        "commit_sha",
        "release_tag",
        "method_version",
        "schema_bundle_sha256",
        "skill_package_sha256",
        "validator_version",
        "validator_sha256",
        "adapter_profile_id",
        "adapter_contract_version",
    )
    return canonical_sha256({field: method_lock.get(field) for field in fields})


def _safe_file(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise MethodLockError("R25_DECLARED_PATH_INVALID", repr(relative))
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise MethodLockError("R25_DECLARED_PATH_ESCAPE", relative)
    candidate = root.joinpath(*pure.parts)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise MethodLockError("R25_DECLARED_PATH_ESCAPE", relative)
    if not candidate.is_file() or candidate.is_symlink():
        raise MethodLockError("R25_DECLARED_FILE_MISSING", relative)
    return candidate


def _bundle_sha256(root, relative_paths):
    if not isinstance(relative_paths, (tuple, list)) or not relative_paths:
        raise MethodLockError("R25_DECLARED_BUNDLE_EMPTY", str(relative_paths))
    normalized = tuple(relative_paths)
    if len(normalized) != len(set(normalized)):
        raise MethodLockError("R25_DECLARED_BUNDLE_DUPLICATE", repr(normalized))
    entries = []
    for relative in sorted(normalized):
        content = _safe_file(root, relative).read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return canonical_sha256(entries)


def _read_profile(root, relative):
    path = _safe_file(root, relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MethodLockError("R25_ADAPTER_PROFILE_INVALID", relative) from error
    if not isinstance(value, dict):
        raise MethodLockError("R25_ADAPTER_PROFILE_INVALID", relative)
    return value


def _add_identity_reasons(reasons, method_lock, descriptor):
    checks = (
        (
            "canonical_repository",
            CANONICAL_REPOSITORY,
            "R25_REPOSITORY_MISMATCH",
        ),
        ("invocation", CANONICAL_INVOCATION, "R25_INVOCATION_MISMATCH"),
        ("commit_sha", method_lock.get("commit_sha"), "R25_COMMIT_MISMATCH"),
        ("release_tag", CANONICAL_RELEASE_TAG, "R25_RELEASE_TAG_MISMATCH"),
        ("method_version", CANONICAL_METHOD_VERSION, "R25_METHOD_VERSION_MISMATCH"),
        ("validator_version", CANONICAL_METHOD_VERSION, "R25_VALIDATOR_VERSION_MISMATCH"),
        (
            "adapter_profile_id",
            method_lock.get("adapter_profile_id"),
            "R25_ADAPTER_PROFILE_ID_MISMATCH",
        ),
        (
            "adapter_contract_version",
            method_lock.get("adapter_contract_version"),
            "R25_ADAPTER_CONTRACT_VERSION_MISMATCH",
        ),
    )
    for field, expected, reason in checks:
        if descriptor.get(field) != expected:
            reasons.add(reason)
    if method_lock.get("canonical_repository") != CANONICAL_REPOSITORY:
        reasons.add("R25_REPOSITORY_MISMATCH")
    if method_lock.get("invocation") != CANONICAL_INVOCATION:
        reasons.add("R25_INVOCATION_MISMATCH")
    if method_lock.get("method_version") != CANONICAL_METHOD_VERSION:
        reasons.add("R25_METHOD_VERSION_MISMATCH")
    if method_lock.get("release_tag") != CANONICAL_RELEASE_TAG:
        reasons.add("R25_RELEASE_TAG_MISMATCH")


def _verify_descriptor(method_lock, adapter_profile, descriptor, reasons, checked_roots):
    _add_identity_reasons(reasons, method_lock, descriptor)
    if descriptor.get("repository_identity_exists") is not True:
        reasons.add("R25_CANONICAL_REPOSITORY_IDENTITY_MISSING")
    raw_root = descriptor.get("declared_root")
    if not isinstance(raw_root, str) or not raw_root:
        reasons.add("R25_DECLARED_ROOT_MISSING")
        return
    root = Path(raw_root).resolve(strict=False)
    if not root.is_dir() or root.is_symlink():
        reasons.add("R25_DECLARED_ROOT_MISSING")
        return
    checked_roots.add(str(root))
    try:
        repository_identity = _read_profile(
            root, descriptor.get("repository_identity_path")
        )
    except MethodLockError:
        reasons.add("R25_CANONICAL_REPOSITORY_IDENTITY_MISSING")
    else:
        if (
            repository_identity.get("canonical_repository") != CANONICAL_REPOSITORY
            or repository_identity.get("commit_sha") != method_lock.get("commit_sha")
            or repository_identity.get("release_tag") != CANONICAL_RELEASE_TAG
        ):
            reasons.add("R25_REPOSITORY_IDENTITY_MISMATCH")

    bundles = (
        (
            "schema_bundle_paths",
            "schema_bundle_sha256",
            method_lock.get("schema_bundle_sha256"),
            "R25_SCHEMA_BUNDLE_DIGEST_MISMATCH",
        ),
        (
            "skill_package_paths",
            "skill_package_sha256",
            method_lock.get("skill_package_sha256"),
            "R25_SKILL_BUNDLE_DIGEST_MISMATCH",
        ),
        (
            "validator_bundle_paths",
            "validator_bundle_sha256",
            method_lock.get("validator_sha256"),
            "R25_VALIDATOR_BUNDLE_DIGEST_MISMATCH",
        ),
    )
    for paths_field, digest_field, locked_digest, reason in bundles:
        try:
            actual_digest = _bundle_sha256(root, descriptor.get(paths_field))
        except MethodLockError:
            reasons.add(reason)
            continue
        if descriptor.get(digest_field) != actual_digest or actual_digest != locked_digest:
            reasons.add(reason)

    contract_paths = descriptor.get("adapter_contract_paths")
    skill_paths = descriptor.get("skill_package_paths")
    if (
        not isinstance(contract_paths, (tuple, list))
        or not isinstance(skill_paths, (tuple, list))
        or not contract_paths
        or any(path not in skill_paths for path in contract_paths)
    ):
        reasons.add("R25_ADAPTER_CONTRACT_NOT_SKILL_LOCKED")
    try:
        actual_contract_digest = _bundle_sha256(
            root, contract_paths
        )
    except MethodLockError:
        reasons.add("R25_ADAPTER_CONTRACT_DIGEST_MISMATCH")
    else:
        if descriptor.get("adapter_contract_sha256") != actual_contract_digest:
            reasons.add("R25_ADAPTER_CONTRACT_DIGEST_MISMATCH")

    try:
        installed_profile = _read_profile(root, descriptor.get("adapter_profile_path"))
    except MethodLockError:
        reasons.add("R25_ADAPTER_PROFILE_DIGEST_MISMATCH")
    else:
        installed_profile_digest = canonical_sha256(installed_profile)
        current_profile_digest = canonical_sha256(adapter_profile)
        if (
            descriptor.get("adapter_profile_sha256") != installed_profile_digest
            or installed_profile_digest != current_profile_digest
            or installed_profile.get("profile_id") != method_lock.get("adapter_profile_id")
            or installed_profile.get("adapter_contract_version")
            != method_lock.get("adapter_contract_version")
        ):
            reasons.add("R25_ADAPTER_PROFILE_DIGEST_MISMATCH")


def verify_method_lock(method_lock, adapter_profile, installation_descriptors):
    descriptors = tuple(installation_descriptors)
    reasons = set()
    checked_roots = set()
    checked_ids = tuple(
        sorted(str(item.get("installation_id", "")) for item in descriptors)
    )
    descriptor_digests = tuple(
        sorted(canonical_sha256(item) for item in descriptors)
    )
    same_invocation = [
        item for item in descriptors if item.get("invocation") == CANONICAL_INVOCATION
    ]
    if len(same_invocation) != 1:
        reasons.add("R24_DUPLICATE_INVOCATION")
    if not same_invocation:
        reasons.add("R25_INVOCATION_MISMATCH")
    for descriptor in same_invocation:
        version = descriptor.get("method_version")
        roles = tuple(descriptor.get("role_types", ()))
        states = tuple(descriptor.get("state_vocabulary", ()))
        if version == "2.0.0" or len(roles) == 7 or "READY" in states:
            reasons.add("R24_STALE_2_0_CONFLICT")
        elif isinstance(version, str) and version.startswith("2.4."):
            reasons.add("R24_STALE_2_4_CONFLICT")
        _verify_descriptor(
            method_lock,
            adapter_profile,
            descriptor,
            reasons,
            checked_roots,
        )

    ordered_reasons = tuple(sorted(reasons))
    matched = (
        same_invocation[0].get("installation_id")
        if len(same_invocation) == 1 and not ordered_reasons
        else None
    )
    values = {
        "status": "PASS" if not ordered_reasons else SUPPLY_CHAIN_CONFLICT,
        "reasons": ordered_reasons,
        "checked_installation_ids": checked_ids,
        "checked_roots": tuple(sorted(checked_roots)),
        "matched_installation_id": matched,
        "method_lock_digest": method_lock_digest(method_lock),
        "installation_descriptor_digests": descriptor_digests,
        "projection_kind": "DERIVED_NON_AUTHORITATIVE",
        "can_advance_run": False,
    }
    return MethodLockReport(**values, report_digest=canonical_sha256(values))


def derive_migration_report(legacy_package):
    source_version = legacy_package.get("source_version")
    if source_version != "2.4.0":
        raise MethodLockError("MIGRATION_SOURCE_VERSION_INVALID", str(source_version))
    preserved = []
    revalidate = []
    historical = []
    discarded = []
    for artifact in tuple(legacy_package.get("artifacts", ())):
        ref = artifact.get("ref")
        kind = artifact.get("kind")
        if not isinstance(ref, str) or not ref or not isinstance(kind, str):
            raise MethodLockError("MIGRATION_ARTIFACT_INVALID", repr(artifact))
        if kind in DISCARD_FORMAL_KINDS:
            discarded.append(ref)
        elif kind in PRESERVE_KINDS and artifact.get("semantically_compatible") is True:
            preserved.append(ref)
        elif kind in REVALIDATE_KINDS:
            revalidate.append(ref)
        elif kind in HISTORICAL_ONLY_KINDS or kind in PRESERVE_KINDS:
            historical.append(ref)
        else:
            historical.append(ref)
    preserved_refs = tuple(sorted(set(preserved)))
    revalidate_refs = tuple(sorted(set(revalidate)))
    historical_refs = tuple(sorted(set(historical)))
    discarded_refs = tuple(sorted(set(discarded)))
    draft_subjects = preserved_refs + revalidate_refs + historical_refs
    values = {
        "status": "DRAFT_ONLY",
        "source_version": source_version,
        "source_package_ref": legacy_package.get("package_ref", ""),
        "preserved_refs": preserved_refs,
        "revalidate_refs": revalidate_refs,
        "historical_only_refs": historical_refs,
        "discarded_formal_refs": discarded_refs,
        "new_draft_references": tuple(
            f"draft://glk-3.0-migration/{index:04d}"
            for index, _ in enumerate(draft_subjects, start=1)
        ),
        "current_evidence_eligible": False,
        "formal_transition_allowed": False,
        "history_mutated": False,
        "projection_kind": "DERIVED_NON_AUTHORITATIVE",
    }
    return MigrationReport(**values, report_digest=canonical_sha256(values))
