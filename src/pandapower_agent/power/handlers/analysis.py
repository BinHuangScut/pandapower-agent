from __future__ import annotations

import copy
from typing import Any

from pandapower_agent.power.analysis_contingency import run_contingency_screening as contingency_analysis
from pandapower_agent.power.analysis_diagnostic import run_diagnostic as diagnostic_analysis
from pandapower_agent.power.analysis_pf import (
    run_ac_power_flow as analysis_run_ac_power_flow,
    run_dc_power_flow as analysis_run_dc_power_flow,
    run_three_phase_power_flow as analysis_run_three_phase_power_flow,
)
from pandapower_agent.power.analysis_sc import run_short_circuit as short_circuit_analysis
from pandapower_agent.power.analysis_topology import run_topology_analysis as topology_analysis
from pandapower_agent.power.handlers.common import ensure_net, import_pp, tool_error
from pandapower_agent.schema.tool_args import (
    RunContingencyScreeningArgs,
    RunDCPowerFlowArgs,
    RunDiagnosticArgs,
    RunOPFArgs,
    RunPowerFlowArgs,
    RunShortCircuitArgs,
    RunStateEstimationArgs,
    RunThreePhasePowerFlowArgs,
    RunTopologyAnalysisArgs,
)
from pandapower_agent.schema.types import TablePayload, ToolResult


def run_power_flow(state, args: RunPowerFlowArgs) -> ToolResult:
    ensure_net(state)
    out = analysis_run_ac_power_flow(state.working_net, algorithm=args.algorithm or "nr", enforce_q_lims=args.enforce_q_lims)
    return ToolResult(ok=True, message="AC power flow completed", data=out)


def run_dc_power_flow(state, args: RunDCPowerFlowArgs) -> ToolResult:
    ensure_net(state)
    out = analysis_run_dc_power_flow(state.working_net, calculate_voltage_angles=args.calculate_voltage_angles)
    return ToolResult(ok=True, message="DC power flow completed", data=out)


def run_three_phase_power_flow(state, args: RunThreePhasePowerFlowArgs) -> ToolResult:
    ensure_net(state)
    out = analysis_run_three_phase_power_flow(state.working_net, max_iteration=args.max_iteration)
    return ToolResult(ok=True, message="Three-phase power flow completed", data=out)


def run_short_circuit(state, args: RunShortCircuitArgs) -> ToolResult:
    ensure_net(state)
    net = state.working_net
    out: dict[str, Any]

    def _maybe_fill_ext_grid_defaults() -> list[dict[str, Any]]:
        if not hasattr(net, "ext_grid") or net.ext_grid.empty:
            return []

        updates: list[dict[str, Any]] = []
        per_case_fields: dict[str, float] = (
            {"s_sc_max_mva": 1000.0, "rx_max": 0.1}
            if args.case == "max"
            else {"s_sc_min_mva": 500.0, "rx_min": 0.1}
        )
        if args.fault == "1ph":
            if args.case == "max":
                per_case_fields |= {"x0x_max": 1.0, "r0x0_max": 0.1}
            else:
                per_case_fields |= {"x0x_min": 1.0, "r0x0_min": 0.1}

        for field, default_value in per_case_fields.items():
            if field not in net.ext_grid.columns:
                net.ext_grid[field] = default_value
                updates.append({"field": field, "value": default_value, "reason": "missing_column"})
                continue
            missing_mask = net.ext_grid[field].isna()
            if bool(missing_mask.any()):
                net.ext_grid.loc[missing_mask, field] = default_value
                updates.append(
                    {
                        "field": field,
                        "value": default_value,
                        "reason": "filled_na",
                        "rows": int(missing_mask.sum()),
                    }
                )
        return updates

    def _is_ext_grid_sc_param_error(err: Exception) -> bool:
        msg = str(err)
        keywords = ("s_sc_", "rx_", "x0x_", "r0x0_", "external grid", "ext_grid")
        return any(k in msg for k in keywords)

    def _is_zero_sequence_data_error(message: str) -> bool:
        return any(k in message for k in ("r0_ohm_per_km", "x0_ohm_per_km", "vk0_percent", "vkr0_percent"))

    def _is_generator_sc_data_error(message: str) -> bool:
        return any(k in message for k in ("vn_kv", "rdss_ohm", "xdss_pu", "pg_percent", "cos_phi"))

    def _zero_sequence_error_result(auto_updates: list[dict[str, Any]]) -> ToolResult:
        payload: dict[str, Any] = {
            "missing_prerequisites": [
                "line.r0_ohm_per_km",
                "line.x0_ohm_per_km",
                "transformer zero-sequence parameters (if applicable)",
            ],
        }
        if auto_updates:
            payload["auto_filled_ext_grid_fields"] = auto_updates
        return tool_error(
            "1ph short-circuit requires zero-sequence network data not present in current model.",
            data=payload,
            next_action="Provide zero-sequence parameters, or run 3ph/2ph short-circuit instead.",
        )

    def _generator_data_error_result(auto_updates: list[dict[str, Any]]) -> ToolResult:
        payload: dict[str, Any] = {
            "missing_prerequisites": [
                "gen.vn_kv",
                "gen.rdss_ohm",
                "other generator short-circuit parameters as required by pandapower",
            ],
        }
        if auto_updates:
            payload["auto_filled_ext_grid_fields"] = auto_updates
        return tool_error(
            "Generator short-circuit parameters are missing in current model.",
            data=payload,
            next_action=(
                "Provide required generator short-circuit fields via update_element_params, "
                "or rerun with generators temporarily excluded."
            ),
        )

    def _try_run_with_generators_excluded(auto_updates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
        if not hasattr(net, "gen") or net.gen.empty or "in_service" not in net.gen.columns:
            return None, None
        net_copy = copy.deepcopy(net)
        net_copy.gen.loc[:, "in_service"] = False
        try:
            fallback_out = short_circuit_analysis(net_copy, case=args.case, fault=args.fault, bus_ids=args.bus_ids)
        except Exception as fallback_exc:
            return None, str(fallback_exc)

        notes = list(fallback_out.get("notes", []))
        notes.append("Generator short-circuit parameters missing; calculated with generators excluded.")
        fallback_out["notes"] = notes
        fallback_out["fallback"] = {"excluded_generators": int(len(net_copy.gen.index))}
        if auto_updates:
            fallback_out["auto_filled_ext_grid_fields"] = auto_updates
        return fallback_out, None

    try:
        out = short_circuit_analysis(net, case=args.case, fault=args.fault, bus_ids=args.bus_ids)
    except Exception as exc:
        auto_updates = _maybe_fill_ext_grid_defaults() if _is_ext_grid_sc_param_error(exc) else []
        if auto_updates:
            try:
                out = short_circuit_analysis(net, case=args.case, fault=args.fault, bus_ids=args.bus_ids)
                out["notes"] = [
                    "Auto-filled ext_grid short-circuit defaults for missing fields.",
                ]
                out["auto_filled_ext_grid_fields"] = auto_updates
            except Exception as retry_exc:
                msg = str(retry_exc)
                if args.fault == "1ph" and _is_zero_sequence_data_error(msg):
                    return _zero_sequence_error_result(auto_updates)
                if _is_generator_sc_data_error(msg):
                    fallback_out, fallback_error = _try_run_with_generators_excluded(auto_updates)
                    if fallback_out is not None:
                        out = fallback_out
                    elif args.fault == "1ph" and fallback_error and _is_zero_sequence_data_error(fallback_error):
                        return _zero_sequence_error_result(auto_updates)
                    else:
                        return _generator_data_error_result(auto_updates)
                else:
                    return tool_error(
                        "Short-circuit analysis failed after auto-filling ext_grid defaults.",
                        data={"auto_filled_ext_grid_fields": auto_updates},
                        next_action="Check network short-circuit prerequisites (generator/line/trafo short-circuit parameters).",
                    )
        else:
            msg = str(exc)
            if args.fault == "1ph" and _is_zero_sequence_data_error(msg):
                return _zero_sequence_error_result(auto_updates)
            if _is_generator_sc_data_error(msg):
                fallback_out, fallback_error = _try_run_with_generators_excluded(auto_updates)
                if fallback_out is not None:
                    out = fallback_out
                elif args.fault == "1ph" and fallback_error and _is_zero_sequence_data_error(fallback_error):
                    return _zero_sequence_error_result(auto_updates)
                else:
                    return _generator_data_error_result(auto_updates)
            else:
                return tool_error(
                    "Short-circuit analysis failed due to network short-circuit prerequisites.",
                    next_action="If ext_grid short-circuit fields are missing, set them via update_element_params or retry with 3ph/2ph.",
                )
    rows = [[r["bus"], r["ikss_ka"], r["ip_ka"], r["ith_ka"]] for r in out["rows"]]
    table = TablePayload(title="Short Circuit Results", columns=["bus", "ikss_ka", "ip_ka", "ith_ka"], rows=rows)
    return ToolResult(ok=True, message="Short-circuit analysis completed", data=out, tables=[table])


def run_diagnostic(state, args: RunDiagnosticArgs) -> ToolResult:
    ensure_net(state)
    out = diagnostic_analysis(state.working_net, compact_report=args.compact_report)
    rows = [[k, str(v)] for k, v in out.get("diagnostic_report", {}).items()]
    table = TablePayload(title="Diagnostic Report", columns=["check", "detail"], rows=rows[:200])
    return ToolResult(ok=True, message="Diagnostic completed", data=out, tables=[table])


def run_topology_analysis(state, args: RunTopologyAnalysisArgs) -> ToolResult:
    ensure_net(state)
    out = topology_analysis(state.working_net, respect_switches=args.respect_switches)
    summary = out.get("topology_summary", {})
    rows = [[k, v] for k, v in summary.items()]
    table = TablePayload(title="Topology Summary", columns=["metric", "value"], rows=rows)
    return ToolResult(ok=True, message="Topology analysis completed", data=out, tables=[table])


def run_contingency_screening(state, args: RunContingencyScreeningArgs) -> ToolResult:
    ensure_net(state)
    out = contingency_analysis(
        state.working_net,
        element_types=args.element_types,
        top_k=args.top_k,
        max_outages=args.max_outages,
        loading_threshold=args.loading_threshold,
        vm_min_pu=args.vm_min_pu,
        vm_max_pu=args.vm_max_pu,
    )
    ranking = out.get("contingency_ranking", [])
    rows = [
        [
            item.get("element_type"),
            item.get("element_id"),
            item.get("severity"),
            item.get("line_violations"),
            item.get("voltage_violations"),
            item.get("max_line_loading_pct"),
        ]
        for item in ranking
    ]
    table = TablePayload(
        title="N-1 Screening Ranking",
        columns=["element_type", "element_id", "severity", "line_viol", "vm_viol", "max_loading_pct"],
        rows=rows,
    )
    return ToolResult(ok=True, message="Contingency screening completed", data=out, tables=[table])


def run_opf(state, args: RunOPFArgs) -> ToolResult:
    ensure_net(state)
    pp = import_pp()
    net = state.working_net
    pp.runopp(net)
    objective = getattr(net, "res_cost", None)
    out = {
        "machine_summary": {
            "opf_objective": float(objective) if objective is not None else None,
            "opf_success": True,
            "objective_type": args.objective,
        }
    }
    return ToolResult(ok=True, message="OPF completed", data=out)


def run_state_estimation(state, args: RunStateEstimationArgs) -> ToolResult:
    ensure_net(state)
    net = state.working_net
    pp = import_pp()

    import pandapower.estimation as est  # type: ignore

    if args.measurement_set == "synthetic":
        if not hasattr(net, "measurement") or net.measurement.empty:
            if not hasattr(net, "res_bus") or net.res_bus.empty:
                pp.runpp(net)
            for bus_idx in list(net.bus.index)[: min(10, len(net.bus.index))]:
                vm = float(net.res_bus.at[bus_idx, "vm_pu"]) if "vm_pu" in net.res_bus.columns else 1.0
                pp.create_measurement(net, "v", "bus", vm, 0.01, int(bus_idx))

    converged = bool(est.estimate(net, init=args.init))
    out = {
        "machine_summary": {
            "state_estimation_converged": converged,
            "measurement_set": args.measurement_set,
            "init": args.init,
        }
    }
    return ToolResult(ok=True, message="State estimation finished", data=out)
