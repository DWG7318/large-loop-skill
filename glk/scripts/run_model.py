from dataclasses import dataclass
from typing import Dict, Set


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

    def __post_init__(self):
        for name, value in self.__dict__.items():
            if not value:
                raise RunBindingError(f"{name} is required")


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
