from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.config import settings
from app.power.analysis_contingency import run_contingency_screening as contingency_analysis
from app.power.analysis_diagnostic import run_diagnostic as diagnostic_analysis
from app.power.analysis_pf import (
    run_ac_power_flow as analysis_run_ac_power_flow,
    run_dc_power_flow as analysis_run_dc_power_flow,
    run_three_phase_power_flow as analysis_run_three_phase_power_flow,
)
from app.power.analysis_sc import run_short_circuit as short_circuit_analysis
from app.power.analysis_topology import run_topology_analysis as topology_analysis
from app.power.metrics import diff_metrics, summarize_network_metrics
from app.power.network_catalog import get_network_factory, list_available_networks, suggest_network_names
from app.power.plotting import PLOTTABLE_SOURCE_TOOLS, build_plot_dataset
from app.power.runtime_guard import is_pandapower_related_exception, silence_library_output, suppressed_runtime_metadata
from app.power.state import SessionState
from app.schema.tool_args import (
    AddDGArgs,
    CompareScenariosArgs,
    CreateLineFromParametersArgs,
    CreateLoadArgs,
    CreateSgenArgs,
    CreateTransformerFromParametersArgs,
    DeleteScenarioArgs,
    GetBusSummaryArgs,
    GetCurrentNetworkInfoArgs,
    GetLineLoadingViolationsArgs,
    ListBuiltinNetworksArgs,
    ListScenariosArgs,
    LoadBuiltinNetworkArgs,
    LoadScenarioArgs,
    PlotAnalysisResultArgs,
    PlotNetworkArgs,
    RunContingencyScreeningArgs,
    RunDCPowerFlowArgs,
    RunDiagnosticArgs,
    RunOPFArgs,
    RunPowerFlowArgs,
    RunShortCircuitArgs,
    RunStateEstimationArgs,
    RunThreePhasePowerFlowArgs,
    RunTopologyAnalysisArgs,
    SaveScenarioArgs,
    SetLoadArgs,
    ToggleElementArgs,
    UndoLastMutationArgs,
    UpdateElementParamsArgs,
)
from app.schema.types import ScenarioDiffResult, TablePayload, ToolResult


def _import_pp():
    import pandapower as pp  # type: ignore

    return pp


def _tool_error(message: str, *, data: dict[str, Any] | None = None, next_action: str | None = None) -> ToolResult:
    payload = data.copy() if data else {}
    if next_action:
        payload["next_action"] = next_action
    return ToolResult(ok=False, message=message, data=payload)


def _public_error_message(exc: Exception) -> tuple[str, str]:
    if is_pandapower_related_exception(exc):
        return (
            "Power-system calculation failed in pandapower. Detailed error is hidden from user output.",
            "Check network prerequisites/parameters and retry.",
        )
    return str(exc), "Check tool args and current network state."


def _ensure_net(state: SessionState) -> None:
    if not state.has_net():
        raise ValueError("No network loaded. Call load_builtin_network first.")


def _safe_count(net: Any, table_name: str) -> int:
    table = getattr(net, table_name, None)
    if table is None:
        return 0
    try:
        return int(len(table.index))
    except Exception:
        try:
            return int(len(table))
        except Exception:
            return 0


def _current_network_info(net: Any, fallback_name: str | None = None) -> dict[str, Any]:
    name = None
    if hasattr(net, "name"):
        name = getattr(net, "name")
    if not name:
        try:
            name = net.get("name")
        except Exception:
            name = None
    if not name:
        try:
            name = net["name"]
        except Exception:
            name = None
    if not name:
        name = fallback_name

    return {
        "name": name,
        "bus_count": _safe_count(net, "bus"),
        "line_count": _safe_count(net, "line"),
        "load_count": _safe_count(net, "load"),
        "sgen_count": _safe_count(net, "sgen"),
        "gen_count": _safe_count(net, "gen"),
    }


def _ensure_bus_exists(net: Any, bus_id: int) -> None:
    if bus_id not in list(net.bus.index):
        raise ValueError(f"bus_id {bus_id} not found. Available bus IDs: {list(net.bus.index)[:20]}")


def _store_result(state: SessionState, key: str, result: ToolResult) -> None:
    state.record_result(key, result.model_dump())
    try:
        Path(".agent_last_results.json").write_text(json.dumps(state.last_results, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _import_plotting_backend():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    return sns, plt


def _import_pandapower_plotting_backend():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandapower.plotting as ppplot  # type: ignore

    return ppplot, plt


def _extract_bus_label_positions(net: Any) -> list[tuple[int, float, float]]:
    bus_table = getattr(net, "bus", None)
    if bus_table is None or not hasattr(bus_table, "index") or "geo" not in getattr(bus_table, "columns", []):
        return []

    positions: list[tuple[int, float, float]] = []
    for bus_id in list(bus_table.index):
        try:
            raw_geo = bus_table.at[bus_id, "geo"]
        except Exception:
            continue
        if raw_geo is None:
            continue

        try:
            payload = json.loads(raw_geo) if isinstance(raw_geo, str) else raw_geo
            if not isinstance(payload, dict):
                continue
            coords = payload.get("coordinates")
            if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                continue
            positions.append((int(bus_id), float(coords[0]), float(coords[1])))
        except Exception:
            continue
    return positions


def _load_cached_results() -> dict[str, Any]:
    cache_file = Path(".agent_last_results.json")
    if not cache_file.exists():
        return {}
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _resolve_plot_source(
    source_results: dict[str, Any],
    requested_source: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    if requested_source:
        if requested_source not in PLOTTABLE_SOURCE_TOOLS:
            return None, None
        candidate = source_results.get(requested_source)
        if not isinstance(candidate, dict):
            return None, None
        return requested_source, candidate

    keys = list(source_results.keys())
    for tool_name in reversed(keys):
        if tool_name not in PLOTTABLE_SOURCE_TOOLS:
            continue
        candidate = source_results.get(tool_name)
        if not isinstance(candidate, dict):
            continue
        if not bool(candidate.get("ok", False)):
            continue
        data = candidate.get("data")
        if isinstance(data, dict) and data:
            return tool_name, candidate
    return None, None


def _render_plot_image(
    labels: list[str],
    values: list[float],
    title: str,
    x_label: str,
    y_label: str,
    chart: str,
    output_path: str,
) -> Path:
    sns, plt = _import_plotting_backend()
    out_path = Path(output_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    width = max(8.0, min(24.0, 0.6 * max(4, len(labels))))
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(width, 5))

    if chart == "line":
        sns.lineplot(
            x=labels,
            y=values,
            marker="o",
            linewidth=1.8,
            color="#2a6f97",
            sort=False,
            ax=ax,
        )
    else:
        sns.barplot(x=labels, y=values, color="#2a6f97", edgecolor="#1d3557", ax=ax)
        if len(values) <= 20:
            if getattr(ax, "containers", None):
                ax.bar_label(ax.containers[0], labels=[f"{value:.3g}" for value in values], padding=2, fontsize=8)

    rotate = 45 if len(labels) > 8 else 0
    plt.setp(ax.get_xticklabels(), rotation=rotate, ha="right" if rotate else "center")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    args_model: Any
    handler: Callable[[SessionState, Any], ToolResult]
    zh_example: str = ""
    en_example: str = ""
    mutating: bool = False

    def to_responses_tool(self) -> dict[str, Any]:
        schema = self.args_model.model_json_schema()
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": schema,
        }

    def to_chat_tool(self) -> dict[str, Any]:
        schema = self.args_model.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


def list_builtin_networks(state: SessionState, args: ListBuiltinNetworksArgs) -> ToolResult:
    _ = state
    catalog = list_available_networks(query=args.query, max_results=args.max_results)
    rows = [[item.get("name", ""), item.get("category", ""), item.get("doc", "")] for item in catalog]
    table = TablePayload(title="Built-in Networks", columns=["name", "category", "doc"], rows=rows)
    return ToolResult(ok=True, message=f"Found {len(catalog)} built-in networks", data={"network_catalog": catalog}, tables=[table])


def load_builtin_network(state: SessionState, args: LoadBuiltinNetworkArgs) -> ToolResult:
    catalog = list_available_networks(query=None, max_results=500)
    available_names = [str(item["name"]) for item in catalog if item.get("name")]

    factory = get_network_factory(args.case_name)
    if factory is None:
        suggestions = suggest_network_names(args.case_name, available_names, limit=5)
        msg = f"Unknown built-in network: {args.case_name}."
        return _tool_error(
            msg,
            data={"suggestions": suggestions},
            next_action="Use `agent networks --query <keyword>` to browse supported networks.",
        )

    net = factory()
    if hasattr(net, "name") and not getattr(net, "name", None):
        net.name = args.case_name
    state.set_base_and_current(net)
    state.current_network_name = args.case_name
    info = _current_network_info(net, fallback_name=args.case_name)
    return ToolResult(ok=True, message=f"Loaded network '{args.case_name}'", data={"case_name": args.case_name, "current_network": info})


def get_current_network_info(state: SessionState, args: GetCurrentNetworkInfoArgs) -> ToolResult:
    _ = args
    if not state.has_net():
        return _tool_error("No network loaded.", data={"current_network": None}, next_action="Call load_builtin_network first.")

    info = _current_network_info(state.working_net, fallback_name=state.current_network_name)
    rows = [[k, v] for k, v in info.items()]
    table = TablePayload(title="Current Network Info", columns=["field", "value"], rows=rows)
    return ToolResult(ok=True, message="Current network info ready", data={"current_network": info}, tables=[table])


def run_power_flow(state: SessionState, args: RunPowerFlowArgs) -> ToolResult:
    _ensure_net(state)
    out = analysis_run_ac_power_flow(state.working_net, algorithm=args.algorithm or "nr", enforce_q_lims=args.enforce_q_lims)
    return ToolResult(ok=True, message="AC power flow completed", data=out)


def run_dc_power_flow(state: SessionState, args: RunDCPowerFlowArgs) -> ToolResult:
    _ensure_net(state)
    out = analysis_run_dc_power_flow(state.working_net, calculate_voltage_angles=args.calculate_voltage_angles)
    return ToolResult(ok=True, message="DC power flow completed", data=out)


def run_three_phase_power_flow(state: SessionState, args: RunThreePhasePowerFlowArgs) -> ToolResult:
    _ensure_net(state)
    out = analysis_run_three_phase_power_flow(state.working_net, max_iteration=args.max_iteration)
    return ToolResult(ok=True, message="Three-phase power flow completed", data=out)


def run_short_circuit(state: SessionState, args: RunShortCircuitArgs) -> ToolResult:
    _ensure_net(state)
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
        return _tool_error(
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
        return _tool_error(
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
                    return _tool_error(
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
                return _tool_error(
                    "Short-circuit analysis failed due to network short-circuit prerequisites.",
                    next_action="If ext_grid short-circuit fields are missing, set them via update_element_params or retry with 3ph/2ph.",
                )
    rows = [[r["bus"], r["ikss_ka"], r["ip_ka"], r["ith_ka"]] for r in out["rows"]]
    table = TablePayload(title="Short Circuit Results", columns=["bus", "ikss_ka", "ip_ka", "ith_ka"], rows=rows)
    return ToolResult(ok=True, message="Short-circuit analysis completed", data=out, tables=[table])


def run_diagnostic(state: SessionState, args: RunDiagnosticArgs) -> ToolResult:
    _ensure_net(state)
    out = diagnostic_analysis(state.working_net, compact_report=args.compact_report)
    rows = [[k, str(v)] for k, v in out.get("diagnostic_report", {}).items()]
    table = TablePayload(title="Diagnostic Report", columns=["check", "detail"], rows=rows[:200])
    return ToolResult(ok=True, message="Diagnostic completed", data=out, tables=[table])


def run_topology_analysis(state: SessionState, args: RunTopologyAnalysisArgs) -> ToolResult:
    _ensure_net(state)
    out = topology_analysis(state.working_net, respect_switches=args.respect_switches)
    summary = out.get("topology_summary", {})
    rows = [[k, v] for k, v in summary.items()]
    table = TablePayload(title="Topology Summary", columns=["metric", "value"], rows=rows)
    return ToolResult(ok=True, message="Topology analysis completed", data=out, tables=[table])


def run_contingency_screening(state: SessionState, args: RunContingencyScreeningArgs) -> ToolResult:
    _ensure_net(state)
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


def set_load(state: SessionState, args: SetLoadArgs) -> ToolResult:
    _ensure_net(state)
    net = state.working_net

    target_ids = list(net.load.index)
    if args.bus_ids:
        bus_set = set(args.bus_ids)
        target_ids = [idx for idx in net.load.index if int(net.load.at[idx, "bus"]) in bus_set]

    if not target_ids:
        return _tool_error("No matching load entries found", next_action="Check bus IDs with get_current_network_info.")

    if args.p_mw_delta is not None:
        net.load.loc[target_ids, "p_mw"] = net.load.loc[target_ids, "p_mw"] + args.p_mw_delta
    if args.q_mvar_delta is not None and "q_mvar" in net.load.columns:
        net.load.loc[target_ids, "q_mvar"] = net.load.loc[target_ids, "q_mvar"] + args.q_mvar_delta

    state.save_scenario("current")
    return ToolResult(ok=True, message=f"Updated {len(target_ids)} load rows", data={"rows": len(target_ids)})


def add_dg(state: SessionState, args: AddDGArgs) -> ToolResult:
    pp = _import_pp()
    _ensure_net(state)
    net = state.working_net

    _ensure_bus_exists(net, args.bus_id)
    dg_id = pp.create_sgen(net, bus=args.bus_id, p_mw=args.p_mw, vm_pu=args.vm_pu, name=args.name or "DG")
    state.save_scenario("current")
    return ToolResult(ok=True, message="DG added", data={"sgen_id": int(dg_id)})


def toggle_element(state: SessionState, args: ToggleElementArgs) -> ToolResult:
    _ensure_net(state)
    net = state.working_net

    if not hasattr(net, args.element_type):
        return _tool_error(f"Element table '{args.element_type}' not found")

    table = getattr(net, args.element_type)
    if args.element_id not in list(table.index):
        return _tool_error(f"{args.element_type} id {args.element_id} not found")

    table.at[args.element_id, "in_service"] = args.in_service
    state.save_scenario("current")
    return ToolResult(ok=True, message=f"{args.element_type} {args.element_id} updated", data={"in_service": args.in_service})


def update_element_params(state: SessionState, args: UpdateElementParamsArgs) -> ToolResult:
    _ensure_net(state)
    net = state.working_net

    if not hasattr(net, args.element_type):
        return _tool_error(f"Element table '{args.element_type}' not found")
    table = getattr(net, args.element_type)
    if args.element_id not in list(table.index):
        return _tool_error(f"{args.element_type} id {args.element_id} not found")

    unknown = [k for k in args.fields if k not in table.columns]
    allow_dynamic_fields = args.element_type in {"ext_grid", "line", "trafo", "gen"}
    if unknown and not allow_dynamic_fields:
        return _tool_error(
            f"Unknown fields for {args.element_type}: {unknown}",
            data={"suggestions": list(table.columns[:20])},
        )

    added_fields: list[str] = []
    if unknown and allow_dynamic_fields:
        for key in unknown:
            table[key] = None
            added_fields.append(key)

    for key, value in args.fields.items():
        table.at[args.element_id, key] = value
    state.save_scenario("current")
    payload: dict[str, Any] = {"updated_fields": list(args.fields.keys())}
    if added_fields:
        payload["added_fields"] = added_fields
    return ToolResult(ok=True, message=f"Updated {args.element_type} {args.element_id}", data=payload)


def create_load(state: SessionState, args: CreateLoadArgs) -> ToolResult:
    pp = _import_pp()
    _ensure_net(state)
    net = state.working_net
    _ensure_bus_exists(net, args.bus_id)
    load_id = pp.create_load(net, bus=args.bus_id, p_mw=args.p_mw, q_mvar=args.q_mvar, name=args.name)
    state.save_scenario("current")
    return ToolResult(ok=True, message="Load created", data={"load_id": int(load_id)})


def create_sgen(state: SessionState, args: CreateSgenArgs) -> ToolResult:
    pp = _import_pp()
    _ensure_net(state)
    net = state.working_net
    _ensure_bus_exists(net, args.bus_id)
    sgen_id = pp.create_sgen(net, bus=args.bus_id, p_mw=args.p_mw, q_mvar=args.q_mvar, name=args.name)
    state.save_scenario("current")
    return ToolResult(ok=True, message="SGen created", data={"sgen_id": int(sgen_id)})


def create_line_from_parameters(state: SessionState, args: CreateLineFromParametersArgs) -> ToolResult:
    pp = _import_pp()
    _ensure_net(state)
    net = state.working_net
    _ensure_bus_exists(net, args.from_bus)
    _ensure_bus_exists(net, args.to_bus)
    line_id = pp.create_line_from_parameters(
        net,
        from_bus=args.from_bus,
        to_bus=args.to_bus,
        length_km=args.length_km,
        r_ohm_per_km=args.r_ohm_per_km,
        x_ohm_per_km=args.x_ohm_per_km,
        c_nf_per_km=args.c_nf_per_km,
        max_i_ka=args.max_i_ka,
        name=args.name,
    )
    state.save_scenario("current")
    return ToolResult(ok=True, message="Line created", data={"line_id": int(line_id)})


def create_transformer_from_parameters(state: SessionState, args: CreateTransformerFromParametersArgs) -> ToolResult:
    pp = _import_pp()
    _ensure_net(state)
    net = state.working_net
    _ensure_bus_exists(net, args.hv_bus)
    _ensure_bus_exists(net, args.lv_bus)
    tid = pp.create_transformer_from_parameters(
        net,
        hv_bus=args.hv_bus,
        lv_bus=args.lv_bus,
        sn_mva=args.sn_mva,
        vn_hv_kv=args.vn_hv_kv,
        vn_lv_kv=args.vn_lv_kv,
        vk_percent=args.vk_percent,
        vkr_percent=args.vkr_percent,
        pfe_kw=args.pfe_kw,
        i0_percent=args.i0_percent,
        shift_degree=args.shift_degree,
        name=args.name,
    )
    state.save_scenario("current")
    return ToolResult(ok=True, message="Transformer created", data={"trafo_id": int(tid)})


def save_scenario(state: SessionState, args: SaveScenarioArgs) -> ToolResult:
    _ensure_net(state)
    state.save_scenario(args.name)
    return ToolResult(ok=True, message=f"Scenario '{args.name}' saved")


def load_scenario(state: SessionState, args: LoadScenarioArgs) -> ToolResult:
    state.load_scenario(args.name)
    return ToolResult(ok=True, message=f"Scenario '{args.name}' loaded")


def list_scenarios(state: SessionState, args: ListScenariosArgs) -> ToolResult:
    _ = args
    names = state.list_scenarios()
    rows = [[name, "yes" if name == state.active_scenario_name else ""] for name in names]
    table = TablePayload(title="Scenarios", columns=["name", "active"], rows=rows)
    return ToolResult(ok=True, message=f"Found {len(names)} scenarios", data={"scenario_catalog": names}, tables=[table])


def delete_scenario(state: SessionState, args: DeleteScenarioArgs) -> ToolResult:
    state.delete_scenario(args.name)
    return ToolResult(ok=True, message=f"Scenario '{args.name}' deleted")


def undo_last_mutation(state: SessionState, args: UndoLastMutationArgs) -> ToolResult:
    _ = args
    if not state.undo_last_mutation():
        return _tool_error("No mutation snapshot available to undo.")
    info = _current_network_info(state.working_net)
    return ToolResult(ok=True, message="Undo successful", data={"current_network": info})


def compare_scenarios(state: SessionState, args: CompareScenariosArgs) -> ToolResult:
    if args.a not in state.scenarios or args.b not in state.scenarios:
        return _tool_error("Scenario not found")

    a_sum = summarize_network_metrics(state.scenarios[args.a])
    b_sum = summarize_network_metrics(state.scenarios[args.b])
    metrics = diff_metrics(a_sum, b_sum, args.metrics)

    improved: bool | None = None
    if "max_line_loading_pct" in metrics and metrics["max_line_loading_pct"]["delta"] is not None:
        improved = metrics["max_line_loading_pct"]["delta"] < 0

    diff = ScenarioDiffResult(a=args.a, b=args.b, metrics=metrics, improved=improved)
    rows = [[k, v["a"], v["b"], v["delta"]] for k, v in metrics.items()]
    table = TablePayload(title=f"Scenario Diff: {args.a} vs {args.b}", columns=["metric", "a", "b", "delta"], rows=rows)
    return ToolResult(ok=True, message="Scenario comparison completed", data=diff.model_dump(), tables=[table])


def get_bus_summary(state: SessionState, args: GetBusSummaryArgs) -> ToolResult:
    _ensure_net(state)
    net = state.working_net
    if not hasattr(net, "res_bus") or net.res_bus.empty:
        return _tool_error("No bus results. Run power flow first.")

    table_df = net.res_bus[[c for c in ["vm_pu", "va_degree", "p_mw", "q_mvar"] if c in net.res_bus.columns]].copy().head(args.top_n)
    rows = [[int(idx), *[float(r[c]) for c in table_df.columns]] for idx, r in table_df.iterrows()]
    table = TablePayload(title="Bus Summary", columns=["bus", *list(table_df.columns)], rows=rows)
    return ToolResult(ok=True, message="Bus summary ready", tables=[table])


def get_line_loading_violations(state: SessionState, args: GetLineLoadingViolationsArgs) -> ToolResult:
    _ensure_net(state)
    net = state.working_net
    if not hasattr(net, "res_line") or net.res_line.empty:
        return _tool_error("No line results. Run power flow first.")
    if "loading_percent" not in net.res_line.columns:
        return _tool_error("loading_percent not found in res_line.")

    bad = net.res_line[net.res_line["loading_percent"] >= args.threshold]
    rows = [[int(idx), float(row.loading_percent)] for idx, row in bad.iterrows()]
    table = TablePayload(title="Line Loading Violations", columns=["line", "loading_percent"], rows=rows)
    violations = [{"line": line, "loading_percent": loading} for line, loading in rows]
    return ToolResult(ok=True, message=f"Found {len(rows)} violations", data={"count": len(rows), "violations": violations}, tables=[table])


def run_opf(state: SessionState, args: RunOPFArgs) -> ToolResult:
    _ensure_net(state)
    pp = _import_pp()
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


def run_state_estimation(state: SessionState, args: RunStateEstimationArgs) -> ToolResult:
    _ensure_net(state)
    net = state.working_net
    pp = _import_pp()

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


def plot_analysis_result(state: SessionState, args: PlotAnalysisResultArgs) -> ToolResult:
    source_results = state.last_results or _load_cached_results()
    if not source_results:
        return _tool_error(
            "No analysis results available to plot.",
            next_action="Run at least one analysis tool first, then call plot_analysis_result.",
        )

    source_tool, source_payload = _resolve_plot_source(source_results, requested_source=args.source_tool)
    if source_tool is None or source_payload is None:
        available = sorted([name for name in source_results if name in PLOTTABLE_SOURCE_TOOLS])
        return _tool_error(
            f"Requested source tool '{args.source_tool}' is unavailable for plotting." if args.source_tool else "No plottable result found.",
            data={"available_source_tools": available},
            next_action="Use one of available_source_tools or rerun a supported analysis tool.",
        )

    data = source_payload.get("data")
    if not isinstance(data, dict):
        return _tool_error(
            f"Result from '{source_tool}' does not include plottable data.",
            next_action="Rerun the analysis tool to regenerate result payload.",
        )

    try:
        dataset = build_plot_dataset(source_tool, data, metric=args.metric, top_n=args.top_n)
    except ValueError as exc:
        return _tool_error(str(exc))

    chart = "bar" if args.chart == "auto" else args.chart
    try:
        plot_path = _render_plot_image(
            labels=dataset.labels,
            values=dataset.values,
            title=dataset.title,
            x_label=dataset.x_label,
            y_label=dataset.y_label,
            chart=chart,
            output_path=args.path,
        )
    except ModuleNotFoundError:
        return _tool_error(
            "Seaborn plotting dependencies are not installed.",
            next_action="Reinstall project dependencies via `pip install -e .[dev]` and retry.",
        )
    except Exception as exc:
        return _tool_error(f"Failed to render plot: {exc}")

    rows = [[label, value] for label, value in zip(dataset.labels, dataset.values)]
    preview_rows = rows[: min(20, len(rows))]
    table = TablePayload(title=f"Plot Data ({source_tool})", columns=["label", dataset.metric], rows=preview_rows)
    return ToolResult(
        ok=True,
        message=f"Plot saved to {plot_path}",
        data={
            "source_tool": source_tool,
            "metric": dataset.metric,
            "chart": chart,
            "plot_path": str(plot_path),
            "points": len(dataset.values),
            "available_metrics": dataset.available_metrics,
        },
        tables=[table],
    )


def plot_network_layout(state: SessionState, args: PlotNetworkArgs) -> ToolResult:
    _ensure_net(state)
    ppplot, plt = _import_pandapower_plotting_backend()
    net = state.working_net

    out_path = Path(args.path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        fig, ax = plt.subplots(figsize=(10, 7))
        ppplot.simple_plot(
            net,
            respect_switches=args.respect_switches,
            line_width=args.line_width,
            bus_size=args.bus_size,
            plot_loads=args.plot_loads,
            plot_gens=args.plot_gens,
            plot_sgens=args.plot_sgens,
            library=args.library,
            show_plot=False,
            ax=ax,
        )
        labels_drawn = 0
        if args.show_bus_labels:
            for bus_id, x, y in _extract_bus_label_positions(net):
                ax.text(
                    x,
                    y,
                    str(bus_id),
                    fontsize=args.label_font_size,
                    color="#111111",
                    ha="center",
                    va="center",
                    zorder=30,
                    bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.75},
                )
                labels_drawn += 1
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
    except ModuleNotFoundError:
        return _tool_error(
            "Pandapower network plotting dependencies are not installed.",
            next_action="Reinstall project dependencies via `pip install -e .[dev]` and retry.",
        )
    except Exception as exc:
        return _tool_error(f"Failed to plot network layout: {exc}")

    rows = [
        ["bus_count", _safe_count(net, "bus")],
        ["line_count", _safe_count(net, "line")],
        ["load_count", _safe_count(net, "load")],
        ["sgen_count", _safe_count(net, "sgen")],
        ["gen_count", _safe_count(net, "gen")],
    ]
    table = TablePayload(title="Network Plot Summary", columns=["metric", "value"], rows=rows)
    return ToolResult(
        ok=True,
        message=f"Network layout plot saved to {out_path}",
        data={
            "plot_path": str(out_path),
            "library": args.library,
            "respect_switches": args.respect_switches,
            "show_bus_labels": args.show_bus_labels,
            "label_font_size": args.label_font_size,
            "bus_labels_drawn": labels_drawn,
            "plot_loads": args.plot_loads,
            "plot_gens": args.plot_gens,
            "plot_sgens": args.plot_sgens,
        },
        tables=[table],
    )


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec("list_builtin_networks", "List selectable pandapower built-in networks", ListBuiltinNetworksArgs, list_builtin_networks, "列出内置网络。", "List built-in networks."),
    ToolSpec("load_builtin_network", "Load pandapower built-in test network", LoadBuiltinNetworkArgs, load_builtin_network, "加载case14。", "Load case14."),
    ToolSpec("get_current_network_info", "Get element counts and metadata of current network", GetCurrentNetworkInfoArgs, get_current_network_info, "查看当前网络规模。", "Show current network info."),
    ToolSpec("run_power_flow", "Run AC power flow", RunPowerFlowArgs, run_power_flow, "运行交流潮流。", "Run AC power flow."),
    ToolSpec("run_dc_power_flow", "Run DC power flow", RunDCPowerFlowArgs, run_dc_power_flow, "运行直流潮流。", "Run DC power flow."),
    ToolSpec("run_three_phase_power_flow", "Run three-phase power flow", RunThreePhasePowerFlowArgs, run_three_phase_power_flow, "运行三相潮流。", "Run three-phase power flow."),
    ToolSpec("run_short_circuit", "Run short-circuit analysis", RunShortCircuitArgs, run_short_circuit, "运行短路分析。", "Run short-circuit analysis."),
    ToolSpec("run_diagnostic", "Run network diagnostic checks", RunDiagnosticArgs, run_diagnostic, "运行网络诊断。", "Run diagnostic checks."),
    ToolSpec("run_topology_analysis", "Run topology analysis", RunTopologyAnalysisArgs, run_topology_analysis, "运行拓扑分析。", "Run topology analysis."),
    ToolSpec("run_contingency_screening", "Run N-1 contingency screening", RunContingencyScreeningArgs, run_contingency_screening, "执行N-1筛查。", "Run N-1 screening."),
    ToolSpec(
        "plot_analysis_result",
        "Plot selected analysis result as an image file",
        PlotAnalysisResultArgs,
        plot_analysis_result,
        "把分析结果画图到 outputs/analysis_plot.png。",
        "Plot latest analysis result to outputs/analysis_plot.png.",
    ),
    ToolSpec(
        "plot_network_layout",
        "Plot current network layout using pandapower built-in plotting",
        PlotNetworkArgs,
        plot_network_layout,
        "把当前网络拓扑画图到 outputs/network_plot.png。",
        "Plot current network layout to outputs/network_plot.png.",
    ),
    ToolSpec("set_load", "Adjust load p_mw/q_mvar for all or selected buses", SetLoadArgs, set_load, "调整负荷。", "Adjust load.", mutating=True),
    ToolSpec("add_dg", "Add distributed generation (sgen) on a bus", AddDGArgs, add_dg, "添加DG。", "Add DG.", mutating=True),
    ToolSpec("toggle_element", "Toggle element in_service status", ToggleElementArgs, toggle_element, "切换元件状态。", "Toggle element status.", mutating=True),
    ToolSpec("update_element_params", "Update selected element fields by id", UpdateElementParamsArgs, update_element_params, "修改元件参数。", "Update element parameters.", mutating=True),
    ToolSpec("create_load", "Create load element", CreateLoadArgs, create_load, "新增加载。", "Create a load.", mutating=True),
    ToolSpec("create_sgen", "Create static generation element", CreateSgenArgs, create_sgen, "新增静态电源。", "Create sgen.", mutating=True),
    ToolSpec("create_line_from_parameters", "Create line from parameters", CreateLineFromParametersArgs, create_line_from_parameters, "新增线路。", "Create line.", mutating=True),
    ToolSpec("create_transformer_from_parameters", "Create transformer from parameters", CreateTransformerFromParametersArgs, create_transformer_from_parameters, "新增变压器。", "Create transformer.", mutating=True),
    ToolSpec("save_scenario", "Save current scenario snapshot with a name", SaveScenarioArgs, save_scenario, "保存场景。", "Save scenario."),
    ToolSpec("load_scenario", "Load a saved scenario as current working scenario", LoadScenarioArgs, load_scenario, "加载场景。", "Load scenario."),
    ToolSpec("list_scenarios", "List available saved scenarios", ListScenariosArgs, list_scenarios, "列出场景。", "List scenarios."),
    ToolSpec("delete_scenario", "Delete a non-base scenario", DeleteScenarioArgs, delete_scenario, "删除场景。", "Delete scenario."),
    ToolSpec("undo_last_mutation", "Undo last mutating operation", UndoLastMutationArgs, undo_last_mutation, "回滚上一步。", "Undo last mutation."),
    ToolSpec("compare_scenarios", "Compare two saved scenarios by key metrics", CompareScenariosArgs, compare_scenarios, "对比场景。", "Compare scenarios."),
    ToolSpec("get_bus_summary", "Get bus voltage summary table", GetBusSummaryArgs, get_bus_summary, "查看母线结果。", "Show bus summary."),
    ToolSpec("get_line_loading_violations", "Get lines above loading threshold", GetLineLoadingViolationsArgs, get_line_loading_violations, "查看过载线路。", "List overloaded lines."),
    ToolSpec("run_opf", "Run optimal power flow", RunOPFArgs, run_opf, "运行最优潮流。", "Run OPF."),
    ToolSpec("run_state_estimation", "Run state estimation", RunStateEstimationArgs, run_state_estimation, "运行状态估计。", "Run state estimation."),
]

TOOL_INDEX = {spec.name: spec for spec in TOOL_SPECS}


class ToolExecutor:
    def __init__(self, state: SessionState):
        self.state = state

    @property
    def responses_tools(self) -> list[dict[str, Any]]:
        return [spec.to_responses_tool() for spec in TOOL_SPECS]

    @property
    def chat_tools(self) -> list[dict[str, Any]]:
        return [spec.to_chat_tool() for spec in TOOL_SPECS]

    def execute(self, tool_name: str, raw_args: str | dict[str, Any]) -> ToolResult:
        if tool_name not in TOOL_INDEX:
            return _tool_error(f"Tool '{tool_name}' is not allowed")

        spec = TOOL_INDEX[tool_name]
        parsed: dict[str, Any] = {}
        suppressed_meta: dict[str, object] = {}
        captured = None
        try:
            if isinstance(raw_args, str):
                parsed = json.loads(raw_args) if raw_args else {}
            else:
                parsed = copy.deepcopy(raw_args)
            args_model = spec.args_model.model_validate(parsed)

            if spec.mutating:
                self.state.push_mutation_snapshot(tool_name)

            with silence_library_output() as capture:
                captured = capture
                result = spec.handler(self.state, args_model)
            if captured is not None:
                suppressed_meta = suppressed_runtime_metadata(captured)

            if spec.mutating and not result.ok:
                self.state.undo_last_mutation()
            _store_result(self.state, tool_name, result)
            history_entry: dict[str, Any] = {"tool": tool_name, "args": parsed, "ok": result.ok, "message": result.message}
            if suppressed_meta:
                history_entry["suppressed_runtime"] = suppressed_meta
            self.state.history.append(history_entry)
            return result
        except Exception as exc:
            if spec.mutating:
                self.state.undo_last_mutation()
            if captured is not None and not suppressed_meta:
                suppressed_meta = suppressed_runtime_metadata(captured)
            public_message, next_action = _public_error_message(exc)
            err = _tool_error(public_message, next_action=next_action)
            _store_result(self.state, tool_name, err)
            history_entry = {
                "tool": tool_name,
                "args": parsed,
                "ok": False,
                "message": err.message,
                "internal_error": f"{exc.__class__.__name__}: {exc}",
            }
            if suppressed_meta:
                history_entry["suppressed_runtime"] = suppressed_meta
            self.state.history.append(history_entry)
            return err


def default_bootstrap_if_needed(executor: ToolExecutor) -> ToolResult | None:
    if executor.state.has_net():
        return None
    return executor.execute("load_builtin_network", {"case_name": settings.default_network})
