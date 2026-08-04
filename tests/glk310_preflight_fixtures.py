def valid_operational_input(module, run_id="RUN-001"):
    profiles = []
    issue = {
        "RUN_SUPERVISOR": (
            "GRAPH_EVENT", "SUPERVISOR_ADMISSION", "PREFLIGHT_ADMISSION",
            "MONITOR_CONTROL", "WORKER_CHECKER_WAKE_BINDING",
            "DEVICE_CAPACITY_PROFILE", "CUMULATIVE_ENGINEERING_LOAD",
            "CELL_WORK_ESTIMATE", "CELL_CAPACITY_GATE", "CELL_PLAN_AMENDMENT",
            "SUPERVISOR_PROGRESS_EVENT",
        ),
        "WORKER": (
            "D0_RECEIPT", "GO_CANDIDATE_CLOSURE", "WAKE_ATTEMPT",
            "PENDING_WAKE", "CELL_SCOPE_EXCEEDED",
        ),
        "CHECKER": ("D1_RECEIPT", "WAKE_ACK", "CHECKER_PROGRESS_EVENT"),
        "GO_VERIFIER": ("D2_RECEIPT",),
        "RUN_VERIFIER": ("D3_RECEIPT",),
        "OWNER": ("OWNER_ACCEPTANCE",),
    }
    for role_type in module.REQUIRED_ROLE_TYPES:
        profiles.append(
            module.RoleCapabilityProfile(
                profile_id=f"CAP-{role_type}",
                role_type=role_type,
                issuable_artifact_types=issue[role_type],
                held_issuance_artifact_types=(),
                invocable_issuance_artifact_types=(),
                operational_capabilities=(
                    module.REQUIRED_WORKER_WAKE_CAPABILITIES if role_type == "WORKER" else ()
                ),
            )
        )
    patrol = module.RunPatrolBinding(
        contract_version="3.1.0",
        run_id=run_id,
        patrol_id=f"PATROL-{run_id}",
        conversation_thread_id=f"THREAD-PATROL-{run_id}",
        conversation_host_id="HOST-TEST",
        heartbeat_id=f"HEARTBEAT-PATROL-{run_id}",
        callback_ref=f"callbacks/{run_id}/patrol.json",
        model="gpt-5.6-luna",
        reasoning_effort="xhigh",
        project_difficulty="MEDIUM",
        interval_minutes=15,
        monitor_version=1,
        prior_monitor_sha256=None,
    )
    simulation = module.validate_operational_simulation(
        observed_wake_levels=(1, 2, 3, 4),
        early_stop_cleanup=True,
        pending_wake_patrol_consumed=True,
        legal_pause_suppressed=True,
        subtask_not_subagent=True,
        actual_subagent_rejected=True,
        owner_pin_accepted=True,
        agent_pin_rejected=True,
        unknown_pin_reported_without_unpin=True,
        pin_then_unpin_violation_retained=True,
        patrol_check_ids=module.PATROL_CHECK_IDS,
        wait_all_rejected=True,
        all_role_subagent_capabilities_rejected=True,
        progress_stages=("DELIVERED", "D1_ACCEPTED", "GO_CANDIDATE_READY", "D2_VERIFIED", "RUN_VERIFIED", "OWNER_ACCEPTED"),
        capacity_results=("PASS", "SPLIT_REQUIRED", "CAPACITY_BLOCKED"),
        severe_split_counts=(3, 6, 7, 8),
        resource_safe_activation=True,
        formal_ledger_before_sha256="a" * 64,
        formal_ledger_after_sha256="a" * 64,
    )
    return module.OperationalPreflightInput(
        run_id=run_id,
        role_capability_profiles=tuple(profiles),
        worker_wake_binding_count=1,
        worker_wake_bindings_valid=True,
        patrol_bindings=(patrol,),
        patrol_heartbeat_refs=(patrol.heartbeat_id,),
        patrol_capabilities=("read_thread", "list_threads"),
        supervisor_control_operations=(),
        dispatch_gate_results=("PASS",),
        capacity_profile_current=True,
        cumulative_load_current=True,
        progress_denominator_versions_current=True,
        simulation_report=simulation,
    )
