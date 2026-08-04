from dataclasses import dataclass
from typing import Dict, Set, Tuple


ROLE_TYPES = (
    "RUN_SUPERVISOR",
    "WORKER",
    "CHECKER",
    "GO_VERIFIER",
    "RUN_VERIFIER",
    "OWNER",
)

TECHNICAL_RECEIPT_TYPES = (
    "D0_RECEIPT",
    "D1_RECEIPT",
    "D2_RECEIPT",
    "D3_RECEIPT",
)
PIN_CAPABILITY_TYPES = frozenset({"set_thread_pinned", "pin_thread", "thread_pin"})


class RunBindingError(ValueError):
    pass


@dataclass(frozen=True)
class RoleBinding:
    role_binding_id: str
    role_type: str
    run_id: str
    instance_id: str
    context_id: str
    workspace_id: str
    evidence_root: str
    capability_profile_id: str = "CAPABILITY-PROFILE-LEGACY"

    def __post_init__(self):
        if self.role_type not in ROLE_TYPES:
            raise RunBindingError(f"unknown role_type: {self.role_type}")
        for name, value in self.__dict__.items():
            if not value:
                raise RunBindingError(f"{name} is required")


@dataclass(frozen=True)
class RoleCapabilityProfile:
    profile_id: str
    role_type: str
    issuable_artifact_types: Tuple[str, ...]
    held_issuance_artifact_types: Tuple[str, ...]
    invocable_issuance_artifact_types: Tuple[str, ...]
    operational_capabilities: Tuple[str, ...] = ()

    def __post_init__(self):
        if not self.profile_id:
            raise RunBindingError("profile_id is required")
        if self.role_type not in ROLE_TYPES:
            raise RunBindingError(f"unknown role_type: {self.role_type}")
        for name in (
            "issuable_artifact_types",
            "held_issuance_artifact_types",
            "invocable_issuance_artifact_types",
            "operational_capabilities",
        ):
            values = getattr(self, name)
            if not isinstance(values, tuple) or len(values) != len(set(values)):
                raise RunBindingError(f"{name} must be a unique tuple")
            if any(not isinstance(value, str) or not value for value in values):
                raise RunBindingError(f"{name} contains an invalid capability")
        forbidden_pin = tuple(sorted(set(self.operational_capabilities) & PIN_CAPABILITY_TYPES))
        if forbidden_pin:
            raise RunBindingError(
                "PIN_CAPABILITY_FORBIDDEN: method roles cannot pin tasks: "
                + ", ".join(forbidden_pin)
            )


def supervisor_technical_capabilities(profile: RoleCapabilityProfile) -> Tuple[str, ...]:
    if profile.role_type != "RUN_SUPERVISOR":
        return ()
    claimed = (
        set(profile.issuable_artifact_types)
        | set(profile.held_issuance_artifact_types)
        | set(profile.invocable_issuance_artifact_types)
    )
    return tuple(sorted(claimed & set(TECHNICAL_RECEIPT_TYPES)))


def enforce_supervisor_capability_exclusion(profile: RoleCapabilityProfile) -> None:
    forbidden = supervisor_technical_capabilities(profile)
    if forbidden:
        raise RunBindingError(
            "Run Supervisor cannot issue, hold, or invoke technical receipt capabilities: "
            + ", ".join(forbidden)
        )


class RunSupervisorRegistry:
    """Guards the Owner rule that every Run gets a fresh Supervisor instance."""

    UNIQUE_FIELDS = (
        "role_binding_id",
        "instance_id",
        "context_id",
        "workspace_id",
        "evidence_root",
    )

    def __init__(self):
        self._bindings: Dict[str, RoleBinding] = {}
        self._used: Dict[str, Set[str]] = {
            field: set() for field in self.UNIQUE_FIELDS
        }

    def bind(self, binding: RoleBinding):
        if binding.role_type != "RUN_SUPERVISOR":
            raise RunBindingError("binding role_type must be RUN_SUPERVISOR")
        if binding.run_id in self._bindings:
            raise RunBindingError(f"Run {binding.run_id} already has a Supervisor")
        reused = [
            field
            for field in self.UNIQUE_FIELDS
            if getattr(binding, field) in self._used[field]
        ]
        if reused:
            raise RunBindingError(
                "every Run requires a fresh Supervisor binding; reused "
                + ", ".join(reused)
            )
        self._bindings[binding.run_id] = binding
        for field in self.UNIQUE_FIELDS:
            self._used[field].add(getattr(binding, field))

    def binding_for(self, run_id: str) -> RoleBinding:
        try:
            return self._bindings[run_id]
        except KeyError as exc:
            raise RunBindingError(f"Run has no Supervisor binding: {run_id}") from exc
