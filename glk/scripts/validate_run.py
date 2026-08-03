#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from provenance import (
    BindingResult,
    IsolationBindingSnapshot,
    IsolationResult,
    IssuanceResult,
    LivenessResult,
    ProvenanceError,
)
from run_model import RoleCapabilityProfile
from run_package import PackageError, load_run_package
from run_validation import (
    REPOSITORY_VALIDATION_SCOPE,
    RUN_VALIDATION_SCOPE,
    RUN_VALIDATOR_DIGEST,
    RUN_VALIDATOR_VERSION,
    add_report_digest,
    build_run_validation_output,
    validate_loaded_run,
)


class FixtureError(ValueError):
    pass


class _LocalConformanceFixtureAdapter:
    """Pure local test/simulation adapter; never a production trust provider."""

    def __init__(self, value):
        if value.get("fixture_kind") != "GLK_PROVENANCE_CONFORMANCE_FIXTURE":
            raise FixtureError("ADAPTER_FIXTURE_KIND_INVALID")
        if value.get("adapter_contract_version") != "1.0":
            raise FixtureError("ADAPTER_FIXTURE_CONTRACT_INVALID")
        bindings = value.get("bindings")
        if not isinstance(bindings, dict) or not bindings:
            raise FixtureError("ADAPTER_FIXTURE_BINDINGS_INVALID")
        dimensions = value.get("verified_dimensions")
        if not isinstance(dimensions, list):
            raise FixtureError("ADAPTER_FIXTURE_DIMENSIONS_INVALID")
        self.profile_id = value.get("profile_id")
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise FixtureError("ADAPTER_FIXTURE_PROFILE_INVALID")
        self.trusted_conformance_environment = (
            value.get("trusted_conformance_environment") is True
        )
        self._bindings = bindings
        self._verified_dimensions = tuple(dimensions)

    def _binding(self, binding_ref):
        value = self._bindings.get(binding_ref)
        if not isinstance(value, dict):
            raise ProvenanceError("BINDING_NOT_ATTESTED", str(binding_ref))
        return value

    @staticmethod
    def _common(request, status="VERIFIED"):
        return {
            "adapter_contract_version": request.adapter_contract_version,
            "request_digest": request.request_digest,
            "binding_ref": request.binding_ref,
            "run_id": request.run_id,
            "scope": request.scope,
            "artifact_sha256": request.artifact_sha256,
            "status": status,
            "evidence_ref": f"local-conformance/{request.binding_ref}.json",
            "observed_at": "2026-08-03T06:00:00Z",
        }

    def resolve_binding(self, request):
        value = self._binding(request.binding_ref)
        role_type = value.get("role_type")
        issuable = value.get("issuable_artifact_types")
        if not isinstance(issuable, list):
            raise ProvenanceError("CAPABILITY_PROFILE_INVALID", request.binding_ref)
        profile = RoleCapabilityProfile(
            profile_id=f"{self.profile_id}:{request.binding_ref}",
            role_type=role_type,
            issuable_artifact_types=tuple(issuable),
            held_issuance_artifact_types=(),
            invocable_issuance_artifact_types=(),
        )
        return BindingResult(
            **self._common(request),
            role_type=role_type,
            instance_id=f"instance/{request.binding_ref}",
            context_id=value.get("context_ref"),
            workspace_id=value.get("workspace_ref"),
            evidence_root=value.get("evidence_root"),
            capability_profile=profile,
        )

    def verify_issuance(self, request):
        value = self._binding(request.binding_ref)
        issued = value.get("issued_artifact_sha256s")
        if not isinstance(issued, list) or request.artifact_sha256 not in issued:
            raise ProvenanceError("ISSUANCE_NOT_ATTESTED", request.binding_ref)
        return IssuanceResult(**self._common(request))

    def verify_isolation(self, request):
        snapshots = []
        for binding_ref in request.binding_refs:
            value = self._binding(binding_ref)
            snapshots.append(
                IsolationBindingSnapshot(
                    binding_ref=binding_ref,
                    conversation_ref=value.get("conversation_ref"),
                    context_ref=value.get("context_ref"),
                    workspace_ref=value.get("workspace_ref"),
                    runtime_state_ref=value.get("runtime_state_ref"),
                    evidence_root=value.get("evidence_root"),
                    decision_input_ref=value.get("decision_input_ref"),
                )
            )
        return IsolationResult(
            **self._common(request),
            verified_dimensions=self._verified_dimensions,
            binding_snapshots=tuple(snapshots),
        )

    def check_liveness(self, request):
        self._binding(request.binding_ref)
        return LivenessResult(
            **self._common(request, status="LIVE"),
            deadline=request.deadline,
        )


def _read_adapter_fixture(path):
    requested = Path(path)
    if not requested.is_file():
        raise FixtureError(f"ADAPTER_FIXTURE_NOT_FOUND: {requested}")
    value = json.loads(requested.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FixtureError("ADAPTER_FIXTURE_OBJECT_REQUIRED")
    return _LocalConformanceFixtureAdapter(value)


def _error_output(run_root, *, error_scope, code, detail):
    return add_report_digest(
        {
            "scope": RUN_VALIDATION_SCOPE,
            "scope_boundaries": {
                "validate_glk": REPOSITORY_VALIDATION_SCOPE,
                "validate_run": RUN_VALIDATION_SCOPE,
            },
            "status": "ERROR",
            "technical_validation_status": "NOT_RUN",
            "report_authority": "DERIVED_NON_AUTHORITATIVE",
            "validator": {
                "version": RUN_VALIDATOR_VERSION,
                "digest": RUN_VALIDATOR_DIGEST,
            },
            "package": {
                "root": Path(run_root).resolve(strict=False).as_posix(),
                "index_head_sha256": None,
            },
            "layers": [],
            "issues": [],
            "holds": [],
            "formal_state": {"projection_kind": "UNAVAILABLE"},
            "error": {
                "scope": error_scope,
                "code": code,
                "detail": str(detail),
            },
        }
    )


def _emit(value):
    sys.stdout.write(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


def _parser():
    parser = argparse.ArgumentParser(description="Validate one complete GLK Run package")
    parser.add_argument("run_root")
    parser.add_argument("--adapter-fixture", required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if not args.json_output:
        _emit(
            _error_output(
                args.run_root,
                error_scope="INVOCATION",
                code="JSON_OUTPUT_REQUIRED",
                detail="--json is required",
            )
        )
        sys.stderr.write("validate_run requires --json\n")
        return 2
    try:
        adapter = _read_adapter_fixture(args.adapter_fixture)
    except (FixtureError, json.JSONDecodeError, OSError, UnicodeError) as error:
        code = str(error).split(":", 1)[0] if str(error) else type(error).__name__
        _emit(
            _error_output(
                args.run_root,
                error_scope="INVOCATION",
                code=code,
                detail=error,
            )
        )
        sys.stderr.write(f"validate_run adapter fixture error: {error}\n")
        return 2
    try:
        package = load_run_package(Path(args.run_root))
    except PackageError as error:
        _emit(
            _error_output(
                args.run_root,
                error_scope="PACKAGE_INTEGRITY",
                code=error.code,
                detail=error.detail,
            )
        )
        sys.stderr.write(f"validate_run package load error: {error}\n")
        return 2
    report = validate_loaded_run(package, adapter)
    output = build_run_validation_output(
        package,
        report,
        trusted_conformance_environment=adapter.trusted_conformance_environment,
        adapter_profile_id=adapter.profile_id,
    )
    _emit(output)
    if output["status"] == "PASS":
        return 0
    sys.stderr.write(
        f"validate_run did not PASS: {len(output['issues'])} validation issue(s); "
        f"environment={output['conformance_environment']['status']}\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
