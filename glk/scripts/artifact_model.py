import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Tuple


ROLE_TYPES = (
    "RUN_SUPERVISOR",
    "WORKER",
    "CHECKER",
    "GO_VERIFIER",
    "RUN_VERIFIER",
    "OWNER",
)


class UnknownArtifactType(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactEnvelope:
    schema_version: str
    artifact_type: str
    artifact_id: str
    run_id: str
    graph_id: str
    graph_version: int
    candidate_id: str
    candidate_sha256: str
    issuer_binding_ref: str
    execution_context_ref: str
    evidence_refs: Tuple[str, ...]
    provenance_ref: str
    issued_at: str


@dataclass(frozen=True)
class ArtifactAuthority:
    artifact_type: str
    sole_issuer: str


def _authority(artifact_type: str, sole_issuer: str) -> ArtifactAuthority:
    return ArtifactAuthority(artifact_type=artifact_type, sole_issuer=sole_issuer)


FORMAL_TYPES: Mapping[str, ArtifactAuthority] = MappingProxyType(
    {
        "RUN_CONTRACT": _authority("RUN_CONTRACT", "LCCODING_OWNER_GATEWAY"),
        "GLK_METHOD_LOCK": _authority(
            "GLK_METHOD_LOCK", "LCCODING_OWNER_GATEWAY"
        ),
        "PROVENANCE_ADAPTER_PROFILE": _authority(
            "PROVENANCE_ADAPTER_PROFILE", "TRUSTED_EXECUTION_ENVIRONMENT"
        ),
        "ROLE_BINDING": _authority(
            "ROLE_BINDING", "TRUSTED_RUNTIME_REGISTRATION"
        ),
        "GRAPH_BASELINE": _authority("GRAPH_BASELINE", "RUN_SUPERVISOR"),
        "CELL_MANIFEST": _authority("CELL_MANIFEST", "RUN_SUPERVISOR"),
        "CELL_MANIFEST_AMENDMENT": _authority(
            "CELL_MANIFEST_AMENDMENT", "RUN_SUPERVISOR"
        ),
        "GO_CANDIDATE_CLOSURE": _authority("GO_CANDIDATE_CLOSURE", "WORKER"),
        "D0_RECEIPT": _authority("D0_RECEIPT", "WORKER"),
        "D1_RECEIPT": _authority("D1_RECEIPT", "CHECKER"),
        "SUPERVISOR_ADMISSION": _authority(
            "SUPERVISOR_ADMISSION", "RUN_SUPERVISOR"
        ),
        "PREFLIGHT_ADMISSION": _authority(
            "PREFLIGHT_ADMISSION", "RUN_SUPERVISOR"
        ),
        "RUN_PACKAGE_INDEX": _authority("RUN_PACKAGE_INDEX", "RUN_SUPERVISOR"),
        "D2_RECEIPT": _authority("D2_RECEIPT", "GO_VERIFIER"),
        "GRAPH_EVENT": _authority("GRAPH_EVENT", "RUN_SUPERVISOR"),
        "MONITOR_CONTROL": _authority("MONITOR_CONTROL", "RUN_SUPERVISOR"),
        "WORKER_CHECKER_WAKE_BINDING": _authority(
            "WORKER_CHECKER_WAKE_BINDING", "RUN_SUPERVISOR"
        ),
        "WAKE_ATTEMPT": _authority("WAKE_ATTEMPT", "WORKER"),
        "WAKE_ACK": _authority("WAKE_ACK", "CHECKER"),
        "PENDING_WAKE": _authority("PENDING_WAKE", "WORKER"),
        "DEVICE_CAPACITY_PROFILE": _authority(
            "DEVICE_CAPACITY_PROFILE", "RUN_SUPERVISOR"
        ),
        "CUMULATIVE_ENGINEERING_LOAD": _authority(
            "CUMULATIVE_ENGINEERING_LOAD", "RUN_SUPERVISOR"
        ),
        "CELL_WORK_ESTIMATE": _authority(
            "CELL_WORK_ESTIMATE", "RUN_SUPERVISOR"
        ),
        "CELL_CAPACITY_GATE": _authority(
            "CELL_CAPACITY_GATE", "RUN_SUPERVISOR"
        ),
        "CELL_PLAN_AMENDMENT": _authority(
            "CELL_PLAN_AMENDMENT", "RUN_SUPERVISOR"
        ),
        "CELL_SCOPE_EXCEEDED": _authority("CELL_SCOPE_EXCEEDED", "WORKER"),
        "D3_RECEIPT": _authority("D3_RECEIPT", "RUN_VERIFIER"),
        "OWNER_ACCEPTANCE": _authority("OWNER_ACCEPTANCE", "OWNER"),
        "SECURITY_HANDOFF": _authority("SECURITY_HANDOFF", "RUN_SUPERVISOR"),
        "PROVENANCE_ATTESTATION": _authority(
            "PROVENANCE_ATTESTATION", "TRUSTED_EXTERNAL_ADAPTER"
        ),
        "LIVENESS_ATTESTATION": _authority(
            "LIVENESS_ATTESTATION", "TRUSTED_EXTERNAL_ADAPTER"
        ),
    }
)


def is_formal_type(artifact_type: str) -> bool:
    return artifact_type in FORMAL_TYPES


def artifact_authority(artifact_type: str) -> ArtifactAuthority:
    try:
        return FORMAL_TYPES[artifact_type]
    except KeyError as error:
        raise UnknownArtifactType(artifact_type) from error


def authorized_artifact_types(sole_issuer: str) -> Tuple[str, ...]:
    return tuple(
        artifact_type
        for artifact_type, authority in FORMAL_TYPES.items()
        if authority.sole_issuer == sole_issuer
    )


def canonical_sha256(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
