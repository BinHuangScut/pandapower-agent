from __future__ import annotations

from pandapower_agent.power.handlers.common import current_network_info, tool_error
from pandapower_agent.power.metrics import diff_metrics, summarize_network_metrics
from pandapower_agent.schema.tool_args import (
    CompareScenariosArgs,
    DeleteScenarioArgs,
    ListScenariosArgs,
    LoadScenarioArgs,
    SaveScenarioArgs,
    UndoLastMutationArgs,
)
from pandapower_agent.schema.types import ScenarioDiffResult, TablePayload, ToolResult


def save_scenario(state, args: SaveScenarioArgs) -> ToolResult:
    current_network = state.working_net
    if current_network is None:
        return tool_error("No network loaded.")
    state.save_scenario(args.name)
    return ToolResult(ok=True, message=f"Scenario '{args.name}' saved")


def load_scenario(state, args: LoadScenarioArgs) -> ToolResult:
    state.load_scenario(args.name)
    return ToolResult(ok=True, message=f"Scenario '{args.name}' loaded")


def list_scenarios(state, args: ListScenariosArgs) -> ToolResult:
    _ = args
    names = state.list_scenarios()
    rows = [[name, "yes" if name == state.active_scenario_name else ""] for name in names]
    table = TablePayload(title="Scenarios", columns=["name", "active"], rows=rows)
    return ToolResult(ok=True, message=f"Found {len(names)} scenarios", data={"scenario_catalog": names}, tables=[table])


def delete_scenario(state, args: DeleteScenarioArgs) -> ToolResult:
    state.delete_scenario(args.name)
    return ToolResult(ok=True, message=f"Scenario '{args.name}' deleted")


def undo_last_mutation(state, args: UndoLastMutationArgs) -> ToolResult:
    _ = args
    if not state.undo_last_mutation():
        return tool_error("No mutation snapshot available to undo.")
    info = current_network_info(state.working_net)
    return ToolResult(ok=True, message="Undo successful", data={"current_network": info})


def compare_scenarios(state, args: CompareScenariosArgs) -> ToolResult:
    if args.a not in state.scenarios or args.b not in state.scenarios:
        return tool_error("Scenario not found")

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
