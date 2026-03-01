from __future__ import annotations

import argparse

from pandapower_agent.cli.dispatch import dispatch
from pandapower_agent.cli.parser import build_parser


def _parser_commands(parser) -> set[str]:
    for action in parser._actions:  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            return set(action.choices.keys())
    return set()


def test_parser_command_set_matches_dispatch_contract() -> None:
    parser = build_parser()
    command_set = _parser_commands(parser)
    assert command_set == {
        "run",
        "chat",
        "reset",
        "undo",
        "networks",
        "use",
        "tools",
        "doctor",
        "scenarios",
        "export",
        "plot",
        "plot-network",
        "config",
    }


def test_dispatch_routes_networks_command(monkeypatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["networks", "--query", "case", "--max", "5", "--format", "json"])
    captured: list[tuple[str | None, int, str]] = []

    def fake_run_networks_command(executor, query, max_results, output_format):
        _ = executor
        captured.append((query, max_results, output_format))
        return 0

    monkeypatch.setattr("pandapower_agent.cli.dispatch.run_networks_command", fake_run_networks_command)

    rc = dispatch(args, parser=parser)

    assert rc == 0
    assert captured == [("case", 5, "json")]
