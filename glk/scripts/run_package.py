import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping, Sequence

import yaml

from artifact_model import FORMAL_TYPES


FORMAL_ROOT_BY_TYPE = MappingProxyType(
    {
        "RUN_CONTRACT": "contracts",
        "GLK_METHOD_LOCK": "contracts",
        "PROVENANCE_ADAPTER_PROFILE": "contracts",
        "ROLE_BINDING": "bindings",
        "GRAPH_BASELINE": "graph",
        "CELL_MANIFEST": "manifests",
        "CELL_MANIFEST_AMENDMENT": "manifests",
        "GO_CANDIDATE_CLOSURE": "closures",
        "D0_RECEIPT": "receipts",
        "D1_RECEIPT": "receipts",
        "SUPERVISOR_ADMISSION": "admissions",
        "PREFLIGHT_ADMISSION": "admissions",
        "RUN_PACKAGE_INDEX": "indexes",
        "D2_RECEIPT": "receipts",
        "GRAPH_EVENT": "events",
        "MONITOR_CONTROL": "controls",
        "WORKER_CHECKER_WAKE_BINDING": "controls",
        "WAKE_ATTEMPT": "controls",
        "WAKE_ACK": "controls",
        "PENDING_WAKE": "controls",
        "DEVICE_CAPACITY_PROFILE": "controls",
        "CUMULATIVE_ENGINEERING_LOAD": "controls",
        "CELL_WORK_ESTIMATE": "controls",
        "CELL_CAPACITY_GATE": "controls",
        "CELL_PLAN_AMENDMENT": "controls",
        "CELL_SCOPE_EXCEEDED": "controls",
        "D3_RECEIPT": "receipts",
        "OWNER_ACCEPTANCE": "acceptance",
        "SECURITY_HANDOFF": "handoffs",
        "PROVENANCE_ATTESTATION": "attestations",
        "LIVENESS_ATTESTATION": "attestations",
    }
)
FORMAL_ROOTS = frozenset(FORMAL_ROOT_BY_TYPE.values())
STRUCTURED_SUFFIXES = frozenset({".json", ".yaml", ".yml"})


class PackageError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class LoadedRunPackage:
    root: Path
    artifacts_by_digest: Mapping[str, Mapping[str, object]]
    evidence_by_digest: Mapping[str, bytes]
    artifacts_by_type: Mapping[str, Sequence[Mapping[str, object]]]
    index_chain: Sequence[Mapping[str, object]]
    index_head_sha256: str


@dataclass(frozen=True)
class _ParsedObject:
    relative_path: str
    digest: str
    data: Mapping[str, object]


@dataclass(frozen=True)
class _IndexRecord:
    relative_path: str
    digest: str
    data: Mapping[str, object]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _is_link_like(path: Path) -> bool:
    return path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    )


def _package_root(root: Path) -> Path:
    requested = Path(root)
    if _is_link_like(requested):
        raise PackageError("SYMLINK_FORBIDDEN", str(requested))
    if not requested.is_dir():
        raise PackageError("PACKAGE_ROOT_INVALID", str(requested))
    resolved = requested.resolve(strict=True)
    for path in resolved.rglob("*"):
        if _is_link_like(path):
            raise PackageError(
                "SYMLINK_FORBIDDEN", path.relative_to(resolved).as_posix()
            )
    return resolved


def _safe_path(root: Path, raw_path) -> tuple[Path, str]:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        raise PackageError("PATH_ESCAPE", repr(raw_path))
    pure = PurePosixPath(raw_path)
    if pure.is_absolute() or Path(raw_path).is_absolute() or ".." in pure.parts:
        raise PackageError("PATH_ESCAPE", raw_path)
    relative = pure.as_posix()
    candidate = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if _is_link_like(current):
            raise PackageError("SYMLINK_FORBIDDEN", relative)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise PackageError("PATH_ESCAPE", raw_path)
    return candidate, relative


def _parse_bytes(relative: str, content: bytes):
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PackageError("ARTIFACT_PARSE_ERROR", f"{relative}: {error}") from error
    try:
        if Path(relative).suffix.lower() == ".json":
            value = json.loads(text)
        else:
            value = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as error:
        raise PackageError("ARTIFACT_PARSE_ERROR", f"{relative}: {error}") from error
    if not isinstance(value, dict):
        raise PackageError("ARTIFACT_PARSE_ERROR", f"{relative}: object required")
    return value


def _read_object_once(
    root: Path, relative: str, cache: dict[str, _ParsedObject]
) -> _ParsedObject:
    if relative in cache:
        return cache[relative]
    path, normalized = _safe_path(root, relative)
    if not path.is_file():
        raise PackageError("PACKAGE_OBJECT_MISSING", normalized)
    content = path.read_bytes()
    parsed = _ParsedObject(
        relative_path=normalized,
        digest=_sha256(content),
        data=_parse_bytes(normalized, content),
    )
    cache[normalized] = parsed
    return parsed


def _load_index_records(root: Path) -> tuple[_IndexRecord, ...]:
    index_root = root / FORMAL_ROOT_BY_TYPE["RUN_PACKAGE_INDEX"]
    if not index_root.is_dir():
        raise PackageError("INDEX_MISSING", index_root.relative_to(root).as_posix())
    records = []
    digests = set()
    for path in sorted(index_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in STRUCTURED_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        digest = _sha256(content)
        if digest in digests:
            raise PackageError("DUPLICATE_INDEX_DIGEST", relative)
        data = _parse_bytes(relative, content)
        if data.get("artifact_type") != "RUN_PACKAGE_INDEX":
            raise PackageError("INDEX_TYPE_INVALID", relative)
        records.append(_IndexRecord(relative, digest, data))
        digests.add(digest)
    if not records:
        raise PackageError("INDEX_MISSING", "no RUN_PACKAGE_INDEX artifact")
    return tuple(records)


def _ordered_index_chain(records: tuple[_IndexRecord, ...]) -> tuple[_IndexRecord, ...]:
    by_digest = {record.digest: record for record in records}
    children: dict[str, list[str]] = {}
    roots = []
    for record in records:
        version = record.data.get("index_version")
        prior = record.data.get("prior_index_sha256")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise PackageError("INDEX_VERSION_INVALID", record.relative_path)
        if prior is None:
            roots.append(record.digest)
            continue
        if not isinstance(prior, str) or len(prior) != 64:
            raise PackageError("INDEX_PRIOR_INVALID", record.relative_path)
        if prior not in by_digest:
            raise PackageError("INDEX_PRIOR_NOT_FOUND", record.relative_path)
        children.setdefault(prior, []).append(record.digest)
    for parent, descendants in children.items():
        if len(descendants) > 1:
            raise PackageError("INDEX_FORK", by_digest[parent].relative_path)
    if len(roots) != 1:
        raise PackageError("MULTIPLE_INDEX_HEADS", f"root_count={len(roots)}")

    chain = []
    current = roots[0]
    visited = set()
    expected_version = 1
    while True:
        if current in visited:
            raise PackageError("INDEX_CYCLE", by_digest[current].relative_path)
        visited.add(current)
        record = by_digest[current]
        if record.data["index_version"] != expected_version:
            raise PackageError(
                "INDEX_VERSION_GAP",
                f"{record.relative_path}: expected {expected_version}",
            )
        chain.append(record)
        descendants = children.get(current, [])
        if not descendants:
            break
        current = descendants[0]
        expected_version += 1
    if len(visited) != len(records):
        raise PackageError("MULTIPLE_INDEX_HEADS", "disconnected index chain")
    return tuple(chain)


def _entry_map(entries, label: str):
    if not isinstance(entries, list):
        raise PackageError("INDEX_INVENTORY_INVALID", f"{label} must be an array")
    indexed = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PackageError("INDEX_INVENTORY_INVALID", f"{label} entry")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise PackageError("INDEX_INVENTORY_INVALID", f"{label} path")
        if path in indexed:
            raise PackageError("DUPLICATE_INDEX_PATH", path)
        indexed[path] = entry
    return indexed


def _validate_indexed_formal_artifacts(
    root: Path, head: Mapping[str, object], cache: dict[str, _ParsedObject]
) -> dict[str, _ParsedObject]:
    entries = _entry_map(head.get("formal_artifacts"), "formal_artifacts")
    parsed = {}
    for raw_path, entry in entries.items():
        path, relative = _safe_path(root, raw_path)
        if (
            entry.get("artifact_type") == "RUN_PACKAGE_INDEX"
            or PurePosixPath(relative).parts[0] == "indexes"
        ):
            raise PackageError("INDEX_SELF_LISTED", relative)
        if not path.is_file():
            raise PackageError("PACKAGE_OBJECT_MISSING", relative)
        item = _read_object_once(root, relative, cache)
        expected_digest = entry.get("sha256")
        if item.digest != expected_digest:
            raise PackageError("DIGEST_MISMATCH", relative)
        artifact_type = item.data.get("artifact_type")
        if artifact_type == "RUN_PACKAGE_INDEX":
            raise PackageError("INDEX_SELF_LISTED", relative)
        if artifact_type not in FORMAL_TYPES:
            raise PackageError("UNKNOWN_FORMAL_TYPE", f"{relative}: {artifact_type}")
        if entry.get("artifact_type") != artifact_type:
            raise PackageError("INDEX_ARTIFACT_TYPE_MISMATCH", relative)
        expected_root = FORMAL_ROOT_BY_TYPE[artifact_type]
        if PurePosixPath(relative).parts[0] != expected_root:
            raise PackageError("UNKNOWN_FORMAL_ROOT", relative)
        parsed[relative] = item
    return parsed


def _scan_formal_artifacts(
    root: Path, cache: dict[str, _ParsedObject]
) -> dict[str, _ParsedObject]:
    discovered = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in STRUCTURED_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        first_part = PurePosixPath(relative).parts[0]
        if first_part in {"indexes", "evidence"}:
            continue
        item = _read_object_once(root, relative, cache)
        artifact_type = item.data.get("artifact_type")
        if artifact_type in FORMAL_TYPES:
            expected_root = FORMAL_ROOT_BY_TYPE[artifact_type]
            if first_part != expected_root:
                raise PackageError("UNKNOWN_FORMAL_ROOT", relative)
            discovered[relative] = item
        elif first_part in FORMAL_ROOTS:
            if artifact_type is None:
                raise PackageError("MISSING_ARTIFACT_TYPE", relative)
            raise PackageError("UNKNOWN_FORMAL_TYPE", f"{relative}: {artifact_type}")
    return discovered


def _referenced_evidence(value) -> set[str]:
    references = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if (key == "evidence_refs" or key.endswith("_evidence_refs")) and isinstance(
                item, (list, tuple)
            ):
                references.update(
                    ref
                    for ref in item
                    if isinstance(ref, str) and ref.startswith("evidence/")
                )
            references.update(_referenced_evidence(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            references.update(_referenced_evidence(item))
    return references


def _load_evidence(
    root: Path,
    head: Mapping[str, object],
    formal: Mapping[str, _ParsedObject],
    index_chain: tuple[_IndexRecord, ...],
) -> Mapping[str, bytes]:
    entries = _entry_map(head.get("evidence_objects"), "evidence_objects")
    indexed_paths = set()
    by_digest = {}
    for raw_path, entry in entries.items():
        path, relative = _safe_path(root, raw_path)
        if PurePosixPath(relative).parts[0] != "evidence":
            raise PackageError("UNKNOWN_EVIDENCE_ROOT", relative)
        if not path.is_file():
            raise PackageError("PACKAGE_OBJECT_MISSING", relative)
        content = path.read_bytes()
        digest = _sha256(content)
        if digest != entry.get("sha256"):
            raise PackageError("DIGEST_MISMATCH", relative)
        indexed_paths.add(relative)
        by_digest[digest] = content

    evidence_root = root / "evidence"
    physical_paths = set()
    if evidence_root.is_dir():
        physical_paths = {
            path.relative_to(root).as_posix()
            for path in evidence_root.rglob("*")
            if path.is_file()
        }
    extra = physical_paths - indexed_paths
    if extra:
        raise PackageError("EXTRA_UNINDEXED_EVIDENCE", sorted(extra)[0])
    missing = indexed_paths - physical_paths
    if missing:
        raise PackageError("PACKAGE_OBJECT_MISSING", sorted(missing)[0])

    referenced = set()
    for item in formal.values():
        referenced.update(_referenced_evidence(item.data))
    for record in index_chain:
        referenced.update(_referenced_evidence(record.data))
    unindexed = referenced - indexed_paths
    if unindexed:
        raise PackageError("UNINDEXED_REFERENCED_EVIDENCE", sorted(unindexed)[0])
    unreferenced = indexed_paths - referenced
    if unreferenced:
        raise PackageError("UNREFERENCED_EVIDENCE", sorted(unreferenced)[0])
    return MappingProxyType(by_digest)


def load_run_package(root: Path) -> LoadedRunPackage:
    """Scan canonical roots, parse once, recompute hashes, and verify one index chain."""
    package_root = _package_root(Path(root))
    index_records = _load_index_records(package_root)
    ordered_indexes = _ordered_index_chain(index_records)
    head = ordered_indexes[-1]
    cache: dict[str, _ParsedObject] = {}
    indexed_formal = _validate_indexed_formal_artifacts(
        package_root, head.data, cache
    )
    discovered_formal = _scan_formal_artifacts(package_root, cache)
    indexed_paths = set(indexed_formal)
    discovered_paths = set(discovered_formal)
    omitted = indexed_paths - discovered_paths
    if omitted:
        raise PackageError("PACKAGE_OBJECT_MISSING", sorted(omitted)[0])
    extra = discovered_paths - indexed_paths
    if extra:
        raise PackageError("EXTRA_UNINDEXED_FORMAL_ARTIFACT", sorted(extra)[0])

    evidence = _load_evidence(
        package_root, head.data, discovered_formal, ordered_indexes
    )
    artifacts_by_digest = {}
    artifacts_by_type: dict[str, list[Mapping[str, object]]] = {}
    for item in discovered_formal.values():
        frozen = _freeze(item.data)
        if item.digest in artifacts_by_digest:
            raise PackageError("DUPLICATE_ARTIFACT_DIGEST", item.relative_path)
        artifacts_by_digest[item.digest] = frozen
        artifacts_by_type.setdefault(item.data["artifact_type"], []).append(frozen)
    frozen_indexes = []
    for record in ordered_indexes:
        frozen = _freeze(record.data)
        artifacts_by_digest[record.digest] = frozen
        artifacts_by_type.setdefault("RUN_PACKAGE_INDEX", []).append(frozen)
        frozen_indexes.append(frozen)
    return LoadedRunPackage(
        root=package_root,
        artifacts_by_digest=MappingProxyType(artifacts_by_digest),
        evidence_by_digest=evidence,
        artifacts_by_type=MappingProxyType(
            {artifact_type: tuple(items) for artifact_type, items in artifacts_by_type.items()}
        ),
        index_chain=tuple(frozen_indexes),
        index_head_sha256=head.digest,
    )
