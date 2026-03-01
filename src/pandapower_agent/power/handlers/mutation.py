from __future__ import annotations

from pandapower_agent.power.handlers.common import ensure_bus_exists, ensure_net, import_pp, tool_error
from pandapower_agent.schema.tool_args import (
    AddDGArgs,
    CreateLineFromParametersArgs,
    CreateLoadArgs,
    CreateSgenArgs,
    CreateTransformerFromParametersArgs,
    SetLoadArgs,
    ToggleElementArgs,
    UpdateElementParamsArgs,
)
from pandapower_agent.schema.types import ToolResult


def set_load(state, args: SetLoadArgs) -> ToolResult:
    ensure_net(state)
    net = state.working_net

    target_ids = list(net.load.index)
    if args.bus_ids:
        bus_set = set(args.bus_ids)
        target_ids = [idx for idx in net.load.index if int(net.load.at[idx, "bus"]) in bus_set]

    if not target_ids:
        return tool_error("No matching load entries found", next_action="Check bus IDs with get_current_network_info.")

    if args.p_mw_delta is not None:
        net.load.loc[target_ids, "p_mw"] = net.load.loc[target_ids, "p_mw"] + args.p_mw_delta
    if args.q_mvar_delta is not None and "q_mvar" in net.load.columns:
        net.load.loc[target_ids, "q_mvar"] = net.load.loc[target_ids, "q_mvar"] + args.q_mvar_delta

    state.save_scenario("current")
    return ToolResult(ok=True, message=f"Updated {len(target_ids)} load rows", data={"rows": len(target_ids)})


def add_dg(state, args: AddDGArgs) -> ToolResult:
    pp = import_pp()
    ensure_net(state)
    net = state.working_net

    ensure_bus_exists(net, args.bus_id)
    dg_id = pp.create_sgen(net, bus=args.bus_id, p_mw=args.p_mw, vm_pu=args.vm_pu, name=args.name or "DG")
    state.save_scenario("current")
    return ToolResult(ok=True, message="DG added", data={"sgen_id": int(dg_id)})


def toggle_element(state, args: ToggleElementArgs) -> ToolResult:
    ensure_net(state)
    net = state.working_net

    if not hasattr(net, args.element_type):
        return tool_error(f"Element table '{args.element_type}' not found")

    table = getattr(net, args.element_type)
    if args.element_id not in list(table.index):
        return tool_error(f"{args.element_type} id {args.element_id} not found")

    table.at[args.element_id, "in_service"] = args.in_service
    state.save_scenario("current")
    return ToolResult(ok=True, message=f"{args.element_type} {args.element_id} updated", data={"in_service": args.in_service})


def update_element_params(state, args: UpdateElementParamsArgs) -> ToolResult:
    ensure_net(state)
    net = state.working_net

    if not hasattr(net, args.element_type):
        return tool_error(f"Element table '{args.element_type}' not found")
    table = getattr(net, args.element_type)
    if args.element_id not in list(table.index):
        return tool_error(f"{args.element_type} id {args.element_id} not found")

    unknown = [k for k in args.fields if k not in table.columns]
    allow_dynamic_fields = args.element_type in {"ext_grid", "line", "trafo", "gen"}
    if unknown and not allow_dynamic_fields:
        return tool_error(
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
    payload: dict[str, object] = {"updated_fields": list(args.fields.keys())}
    if added_fields:
        payload["added_fields"] = added_fields
    return ToolResult(ok=True, message=f"Updated {args.element_type} {args.element_id}", data=payload)


def create_load(state, args: CreateLoadArgs) -> ToolResult:
    pp = import_pp()
    ensure_net(state)
    net = state.working_net
    ensure_bus_exists(net, args.bus_id)
    load_id = pp.create_load(net, bus=args.bus_id, p_mw=args.p_mw, q_mvar=args.q_mvar, name=args.name)
    state.save_scenario("current")
    return ToolResult(ok=True, message="Load created", data={"load_id": int(load_id)})


def create_sgen(state, args: CreateSgenArgs) -> ToolResult:
    pp = import_pp()
    ensure_net(state)
    net = state.working_net
    ensure_bus_exists(net, args.bus_id)
    sgen_id = pp.create_sgen(net, bus=args.bus_id, p_mw=args.p_mw, q_mvar=args.q_mvar, name=args.name)
    state.save_scenario("current")
    return ToolResult(ok=True, message="SGen created", data={"sgen_id": int(sgen_id)})


def create_line_from_parameters(state, args: CreateLineFromParametersArgs) -> ToolResult:
    pp = import_pp()
    ensure_net(state)
    net = state.working_net
    ensure_bus_exists(net, args.from_bus)
    ensure_bus_exists(net, args.to_bus)
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


def create_transformer_from_parameters(state, args: CreateTransformerFromParametersArgs) -> ToolResult:
    pp = import_pp()
    ensure_net(state)
    net = state.working_net
    ensure_bus_exists(net, args.hv_bus)
    ensure_bus_exists(net, args.lv_bus)
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
