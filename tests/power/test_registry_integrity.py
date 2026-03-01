from __future__ import annotations

from pandapower_agent.power.registry import TOOL_INDEX, TOOL_SPECS


def test_tool_registry_has_unique_names() -> None:
    names = [spec.name for spec in TOOL_SPECS]
    assert len(names) == len(set(names))
    assert set(names) == set(TOOL_INDEX.keys())


def test_tool_registry_includes_core_commands() -> None:
    required = {
        "list_builtin_networks",
        "load_builtin_network",
        "run_power_flow",
        "run_short_circuit",
        "run_topology_analysis",
        "run_contingency_screening",
        "plot_analysis_result",
        "plot_network_layout",
    }
    assert required.issubset(set(TOOL_INDEX.keys()))


def test_tool_specs_have_valid_schema() -> None:
    for spec in TOOL_SPECS:
        schema = spec.args_model.model_json_schema()
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"
