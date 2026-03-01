from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from pandapower_agent.power.state import SessionState
from pandapower_agent.power.executor import ToolExecutor


def _fake_catalog(query: str | None = None, max_results: int = 20):
    items = [
        {"name": "case14", "category": "ieee_case", "doc": "14-bus"},
        {"name": "case118", "category": "ieee_case", "doc": "118-bus"},
    ]
    if query:
        items = [item for item in items if query.lower() in item["name"].lower()]
    return items[:max_results]


def test_list_builtin_networks_tool(monkeypatch) -> None:
    state = SessionState()
    executor = ToolExecutor(state)
    monkeypatch.setattr("pandapower_agent.power.handlers.network.list_available_networks", _fake_catalog)

    result = executor.execute("list_builtin_networks", {"query": "118", "max_results": 10})
    assert result.ok
    assert result.data["network_catalog"][0]["name"] == "case118"


def test_load_builtin_network_returns_suggestions(monkeypatch) -> None:
    state = SessionState()
    executor = ToolExecutor(state)
    monkeypatch.setattr("pandapower_agent.power.handlers.network.list_available_networks", _fake_catalog)
    monkeypatch.setattr("pandapower_agent.power.handlers.network.get_network_factory", lambda case_name: None)

    result = executor.execute("load_builtin_network", {"case_name": "case1x"})
    assert not result.ok
    assert "suggestions" in result.data
    assert result.data["suggestions"]


def test_get_current_network_info_tool_with_active_net() -> None:
    state = SessionState()
    state.working_net = SimpleNamespace(
        name="case14",
        bus=pd.DataFrame(index=[0, 1, 2]),
        line=pd.DataFrame(index=[0, 1]),
        load=pd.DataFrame(index=[0]),
        sgen=pd.DataFrame(index=[0, 1]),
        gen=pd.DataFrame(index=[]),
    )
    executor = ToolExecutor(state)

    result = executor.execute("get_current_network_info", {})
    assert result.ok
    assert result.data["current_network"]["bus_count"] == 3


def test_get_current_network_info_without_net() -> None:
    state = SessionState()
    executor = ToolExecutor(state)

    result = executor.execute("get_current_network_info", {})
    assert not result.ok
    assert result.data["current_network"] is None


def test_get_current_network_info_uses_state_name_fallback() -> None:
    state = SessionState()
    state.current_network_name = "case2848rte"
    state.working_net = SimpleNamespace(
        name=None,
        bus=pd.DataFrame(index=[0, 1]),
        line=pd.DataFrame(index=[0]),
        load=pd.DataFrame(index=[]),
        sgen=pd.DataFrame(index=[]),
        gen=pd.DataFrame(index=[]),
    )
    executor = ToolExecutor(state)

    result = executor.execute("get_current_network_info", {})
    assert result.ok
    assert result.data["current_network"]["name"] == "case2848rte"
