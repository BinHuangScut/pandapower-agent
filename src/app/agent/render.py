from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from app.schema.types import ToolResult

console = Console()


def render_tool_result(result: ToolResult) -> None:
    status = "OK" if result.ok else "ERROR"
    console.print(f"[{ 'green' if result.ok else 'red' }]{status}[/]: {result.message}")

    for t in result.tables:
        table = Table(title=t.title)
        for col in t.columns:
            table.add_column(str(col))
        for row in t.rows:
            table.add_row(*[str(x) for x in row])
        console.print(table)

    if result.data and not result.tables:
        console.print(result.data)

    for w in result.warnings:
        console.print(f"[yellow]Warning:[/] {w}")


def render_json(data: Any) -> None:
    console.print(json.dumps(data, ensure_ascii=False, indent=2))


def render_table(title: str, columns: list[str], rows: list[list[Any]]) -> None:
    table = Table(title=title)
    for col in columns:
        table.add_column(str(col))
    for row in rows:
        table.add_row(*[str(x) for x in row])
    console.print(table)


def render_agent_reply(text: str) -> None:
    message = text.strip()
    if not message:
        return
    console.print(f"assistant> {message}")


def render_tool_traces(tool_traces: list[dict[str, Any]]) -> None:
    if not tool_traces:
        return

    table = Table(title="Debug Tool Traces")
    table.add_column("tool")
    table.add_column("ok")
    table.add_column("args")
    table.add_column("message")

    for trace in tool_traces:
        args = trace.get("args")
        if not args:
            args_text = "-"
        else:
            args_text = json.dumps(args, ensure_ascii=False)
            if len(args_text) > 120:
                args_text = f"{args_text[:117]}..."
        table.add_row(
            str(trace.get("tool", "")),
            "yes" if bool(trace.get("ok")) else "no",
            args_text,
            str(trace.get("message", "")),
        )

    console.print(table)
