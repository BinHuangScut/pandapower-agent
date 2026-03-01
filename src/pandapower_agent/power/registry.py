from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pandapower_agent.power.handlers.analysis import (
    run_contingency_screening,
    run_dc_power_flow,
    run_diagnostic,
    run_opf,
    run_power_flow,
    run_short_circuit,
    run_state_estimation,
    run_three_phase_power_flow,
    run_topology_analysis,
)
from pandapower_agent.power.handlers.mutation import (
    add_dg,
    create_line_from_parameters,
    create_load,
    create_sgen,
    create_transformer_from_parameters,
    set_load,
    toggle_element,
    update_element_params,
)
from pandapower_agent.power.handlers.network import get_current_network_info, list_builtin_networks, load_builtin_network
from pandapower_agent.power.handlers.plotting import plot_analysis_result, plot_network_layout
from pandapower_agent.power.handlers.reporting import get_bus_summary, get_line_loading_violations
from pandapower_agent.power.handlers.scenario import (
    compare_scenarios,
    delete_scenario,
    list_scenarios,
    load_scenario,
    save_scenario,
    undo_last_mutation,
)
from pandapower_agent.schema.tool_args import (
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
from pandapower_agent.schema.types import ToolResult


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    args_model: Any
    handler: Callable[[Any, Any], ToolResult]
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
