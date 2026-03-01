from __future__ import annotations

from pandapower_agent.power.handlers.common import current_network_info, tool_error
from pandapower_agent.power.network_catalog import get_network_factory, list_available_networks, suggest_network_names
from pandapower_agent.schema.tool_args import GetCurrentNetworkInfoArgs, ListBuiltinNetworksArgs, LoadBuiltinNetworkArgs
from pandapower_agent.schema.types import TablePayload, ToolResult


def list_builtin_networks(state, args: ListBuiltinNetworksArgs) -> ToolResult:
    _ = state
    catalog = list_available_networks(query=args.query, max_results=args.max_results)
    rows = [[item.get("name", ""), item.get("category", ""), item.get("doc", "")] for item in catalog]
    table = TablePayload(title="Built-in Networks", columns=["name", "category", "doc"], rows=rows)
    return ToolResult(ok=True, message=f"Found {len(catalog)} built-in networks", data={"network_catalog": catalog}, tables=[table])


def load_builtin_network(state, args: LoadBuiltinNetworkArgs) -> ToolResult:
    catalog = list_available_networks(query=None, max_results=500)
    available_names = [str(item["name"]) for item in catalog if item.get("name")]

    factory = get_network_factory(args.case_name)
    if factory is None:
        suggestions = suggest_network_names(args.case_name, available_names, limit=5)
        msg = f"Unknown built-in network: {args.case_name}."
        return tool_error(
            msg,
            data={"suggestions": suggestions},
            next_action="Use `agent networks --query <keyword>` to browse supported networks.",
        )

    net = factory()
    if hasattr(net, "name") and not getattr(net, "name", None):
        net.name = args.case_name
    state.set_base_and_current(net)
    state.current_network_name = args.case_name
    info = current_network_info(net, fallback_name=args.case_name)
    return ToolResult(ok=True, message=f"Loaded network '{args.case_name}'", data={"case_name": args.case_name, "current_network": info})


def get_current_network_info(state, args: GetCurrentNetworkInfoArgs) -> ToolResult:
    _ = args
    if not state.has_net():
        return tool_error("No network loaded.", data={"current_network": None}, next_action="Call load_builtin_network first.")

    info = current_network_info(state.working_net, fallback_name=state.current_network_name)
    rows = [[k, v] for k, v in info.items()]
    table = TablePayload(title="Current Network Info", columns=["field", "value"], rows=rows)
    return ToolResult(ok=True, message="Current network info ready", data={"current_network": info}, tables=[table])
