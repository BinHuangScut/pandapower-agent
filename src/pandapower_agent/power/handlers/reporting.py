from __future__ import annotations

from pandapower_agent.power.handlers.common import ensure_net, tool_error
from pandapower_agent.schema.tool_args import GetBusSummaryArgs, GetLineLoadingViolationsArgs
from pandapower_agent.schema.types import TablePayload, ToolResult


def get_bus_summary(state, args: GetBusSummaryArgs) -> ToolResult:
    ensure_net(state)
    net = state.working_net
    if not hasattr(net, "res_bus") or net.res_bus.empty:
        return tool_error("No bus results. Run power flow first.")

    table_df = net.res_bus[[c for c in ["vm_pu", "va_degree", "p_mw", "q_mvar"] if c in net.res_bus.columns]].copy().head(args.top_n)
    rows = [[int(idx), *[float(r[c]) for c in table_df.columns]] for idx, r in table_df.iterrows()]
    table = TablePayload(title="Bus Summary", columns=["bus", *list(table_df.columns)], rows=rows)
    return ToolResult(ok=True, message="Bus summary ready", tables=[table])


def get_line_loading_violations(state, args: GetLineLoadingViolationsArgs) -> ToolResult:
    ensure_net(state)
    net = state.working_net
    if not hasattr(net, "res_line") or net.res_line.empty:
        return tool_error("No line results. Run power flow first.")
    if "loading_percent" not in net.res_line.columns:
        return tool_error("loading_percent not found in res_line.")

    bad = net.res_line[net.res_line["loading_percent"] >= args.threshold]
    rows = [[int(idx), float(row.loading_percent)] for idx, row in bad.iterrows()]
    table = TablePayload(title="Line Loading Violations", columns=["line", "loading_percent"], rows=rows)
    violations = [{"line": line, "loading_percent": loading} for line, loading in rows]
    return ToolResult(ok=True, message=f"Found {len(rows)} violations", data={"count": len(rows), "violations": violations}, tables=[table])
