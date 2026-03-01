from __future__ import annotations

from typing import Any

from pandapower_agent.agent.render import render_json, render_table
from pandapower_agent.power.registry import TOOL_SPECS


def _tool_schema_keys(schema: dict[str, Any]) -> str:
    props = schema.get("properties", {})
    keys = list(props.keys())
    return ", ".join(keys) if keys else "-"


def run_tools_command(output_format: str) -> int:
    items: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        schema = spec.args_model.model_json_schema()
        items.append(
            {
                "name": spec.name,
                "description": spec.description,
                "args": list(schema.get("properties", {}).keys()),
                "zh_example": spec.zh_example,
                "en_example": spec.en_example,
            }
        )

    if output_format == "json":
        render_json({"tools": items})
        return 0

    rows = []
    for spec in TOOL_SPECS:
        schema = spec.args_model.model_json_schema()
        rows.append([spec.name, spec.description, _tool_schema_keys(schema), spec.zh_example, spec.en_example])
    render_table("Tool Catalog", ["tool", "description", "key_args", "zh_example", "en_example"], rows)
    return 0
