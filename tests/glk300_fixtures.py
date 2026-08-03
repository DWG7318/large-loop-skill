import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml


FORMAL_ROOT_BY_TYPE = {
    "GLK_METHOD_LOCK": "contracts",
    "PROVENANCE_ADAPTER_PROFILE": "contracts",
    "ROLE_BINDING": "bindings",
    "GRAPH_BASELINE": "graph",
    "CELL_MANIFEST": "manifests",
    "GO_CANDIDATE_CLOSURE": "closures",
    "D0_RECEIPT": "receipts",
    "D1_RECEIPT": "receipts",
    "SUPERVISOR_ADMISSION": "admissions",
    "D2_RECEIPT": "receipts",
    "GRAPH_EVENT": "events",
    "MONITOR_CONTROL": "controls",
    "D3_RECEIPT": "receipts",
    "OWNER_ACCEPTANCE": "acceptance",
}


@dataclass(frozen=True)
class RunFixture:
    root: Path
    index_path: Path
    formal_paths: tuple[Path, ...]
    evidence_paths: tuple[Path, ...]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def write_yaml(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def read_index(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_index(path: Path, value) -> None:
    write_yaml(path, value)


def _candidate_hash(candidate_id: str) -> str:
    return sha256_bytes(candidate_id.encode("utf-8"))


def _artifact(artifact_type: str, artifact_id: str, candidate_id: str, evidence_ref: str):
    return {
        "schema_version": "3.0.0",
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "run_id": "RUN-001",
        "graph_id": "GRAPH-RUN-001",
        "graph_version": 1,
        "candidate_id": candidate_id,
        "candidate_sha256": _candidate_hash(candidate_id),
        "issuer_binding_ref": f"BINDING-{artifact_type}",
        "execution_context_ref": f"CONTEXT-{artifact_type}",
        "evidence_refs": [evidence_ref],
        "provenance_ref": f"attestations/{artifact_id}.json",
        "issued_at": "2026-08-03T03:00:00Z",
    }


def _add_artifact(root: Path, artifact_type: str, artifact_id: str, candidate_id: str):
    evidence_ref = f"evidence/{artifact_id}.json"
    artifact = _artifact(artifact_type, artifact_id, candidate_id, evidence_ref)
    formal_root = FORMAL_ROOT_BY_TYPE[artifact_type]
    artifact_path = root / formal_root / f"{artifact_id}.json"
    evidence_path = root / evidence_ref
    write_json(artifact_path, artifact)
    write_json(evidence_path, {"artifact_id": artifact_id, "result": "PASS"})
    return artifact_path, evidence_path


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _index_document(
    root: Path,
    formal_paths: tuple[Path, ...],
    evidence_paths: tuple[Path, ...],
    *,
    version: int,
    prior_index_sha256: str | None,
    suffix: str,
):
    artifact_id = f"RUN-PACKAGE-INDEX-RUN-001-{suffix}"
    index_evidence = root / f"evidence/package/{artifact_id}.json"
    if not index_evidence.exists():
        write_json(index_evidence, {"index_version": version, "result": "RECORDED"})
    all_evidence = tuple(
        sorted(path for path in (root / "evidence").rglob("*") if path.is_file())
    )
    formal_entries = []
    ledger_heads = {}
    for path in sorted(formal_paths):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        digest = sha256_file(path)
        formal_entries.append(
            {
                "path": _relative(root, path),
                "sha256": digest,
                "artifact_type": artifact["artifact_type"],
            }
        )
        ledger_heads[artifact["artifact_id"]] = digest
    return {
        "schema_version": "3.0.0",
        "artifact_type": "RUN_PACKAGE_INDEX",
        "artifact_id": artifact_id,
        "run_id": "RUN-001",
        "graph_id": "GRAPH-RUN-001",
        "graph_version": 1,
        "candidate_id": f"RUN-PACKAGE-RUN-001-{suffix}",
        "candidate_sha256": _candidate_hash(f"RUN-PACKAGE-RUN-001-{suffix}"),
        "issuer_binding_ref": "ROLE-RUN-001-SUPERVISOR",
        "execution_context_ref": "CONTEXT-RUN-001-SUPERVISOR",
        "evidence_refs": [_relative(root, index_evidence)],
        "provenance_ref": f"attestations/{artifact_id}.json",
        "issued_at": "2026-08-03T03:30:00Z",
        "index_id": "RUN-PACKAGE-INDEX-RUN-001",
        "index_version": version,
        "prior_index_sha256": prior_index_sha256,
        "formal_artifacts": formal_entries,
        "evidence_objects": [
            {"path": _relative(root, path), "sha256": sha256_file(path)}
            for path in all_evidence
        ],
        "ledger_heads": ledger_heads,
    }


def append_index(
    fixture: RunFixture,
    *,
    version: int,
    prior_index_sha256: str | None,
    suffix: str,
) -> Path:
    document = _index_document(
        fixture.root,
        fixture.formal_paths,
        fixture.evidence_paths,
        version=version,
        prior_index_sha256=prior_index_sha256,
        suffix=suffix,
    )
    path = fixture.root / "indexes" / f"RUN_PACKAGE_INDEX-{suffix}.yaml"
    write_index(path, document)
    return path


def write_valid_run(tmp_path: Path, cells_per_go: int = 2, go_count: int = 2) -> RunFixture:
    root = tmp_path / "run-package"
    root.mkdir(parents=True)
    formal_paths = []
    evidence_paths = []

    base = [
        ("GLK_METHOD_LOCK", "METHOD-LOCK-RUN-001-V1", "METHOD-GLK-3.0.0"),
        (
            "PROVENANCE_ADAPTER_PROFILE",
            "PROVENANCE-PROFILE-RUN-001-V1",
            "PROVENANCE-PROFILE-001",
        ),
        ("ROLE_BINDING", "ROLE-BINDING-SUPERVISOR-V1", "ROLE-RUN-001-SUPERVISOR"),
        ("GRAPH_BASELINE", "GRAPH-BASELINE-RUN-001-V1", "GRAPH-RUN-001-V1"),
    ]
    for artifact_type, artifact_id, candidate_id in base:
        formal, evidence = _add_artifact(root, artifact_type, artifact_id, candidate_id)
        formal_paths.append(formal)
        evidence_paths.append(evidence)

    for go_number in range(1, go_count + 1):
        go_id = f"GO-{go_number:03d}"
        manifest_id = f"CELL-MANIFEST-{go_id}-V1"
        formal, evidence = _add_artifact(root, "CELL_MANIFEST", manifest_id, manifest_id)
        formal_paths.append(formal)
        evidence_paths.append(evidence)
        for cell_number in range(1, cells_per_go + 1):
            cell_id = f"{go_id}-CELL-{cell_number:03d}"
            candidate_id = f"CANDIDATE-{cell_id}-V1"
            for receipt_type in ("D0_RECEIPT", "D1_RECEIPT"):
                receipt_id = f"{receipt_type.removesuffix('_RECEIPT')}-{cell_id}-V1"
                formal, evidence = _add_artifact(
                    root, receipt_type, receipt_id, candidate_id
                )
                formal_paths.append(formal)
                evidence_paths.append(evidence)
        closure_id = f"GO-CANDIDATE-CLOSURE-{go_id}-V1"
        formal, evidence = _add_artifact(
            root, "GO_CANDIDATE_CLOSURE", closure_id, f"CANDIDATE-{go_id}-V1"
        )
        formal_paths.append(formal)
        evidence_paths.append(evidence)
        d2_id = f"D2-{go_id}-V1"
        formal, evidence = _add_artifact(
            root, "D2_RECEIPT", d2_id, f"CANDIDATE-{go_id}-V1"
        )
        formal_paths.append(formal)
        evidence_paths.append(evidence)

    tail = [
        ("SUPERVISOR_ADMISSION", "SUPERVISOR-ADMISSION-D2-V1", "CANDIDATE-GO-001-V1"),
        ("GRAPH_EVENT", "GRAPH-EVENT-RUN-001-V1", "GRAPH-RUN-001-V1"),
        ("MONITOR_CONTROL", "MONITOR-CONTROL-RUN-001-V1", "MONITOR-RUN-001-V1"),
        ("D3_RECEIPT", "D3-RUN-001-V1", "CANDIDATE-RUN-001-V1"),
        ("OWNER_ACCEPTANCE", "OWNER-ACCEPTANCE-RUN-001-V1", "CANDIDATE-RUN-001-V1"),
    ]
    for artifact_type, artifact_id, candidate_id in tail:
        formal, evidence = _add_artifact(root, artifact_type, artifact_id, candidate_id)
        formal_paths.append(formal)
        evidence_paths.append(evidence)

    frozen_formal = tuple(sorted(formal_paths))
    frozen_evidence = tuple(sorted(evidence_paths))
    fixture = RunFixture(
        root=root,
        index_path=root / "indexes" / "RUN_PACKAGE_INDEX-v1.yaml",
        formal_paths=frozen_formal,
        evidence_paths=frozen_evidence,
    )
    document = _index_document(
        root,
        frozen_formal,
        frozen_evidence,
        version=1,
        prior_index_sha256=None,
        suffix="v1",
    )
    write_index(fixture.index_path, document)
    return fixture
