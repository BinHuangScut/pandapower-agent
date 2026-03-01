from __future__ import annotations

from types import SimpleNamespace

from app.power import network_catalog as nc


def test_discover_network_entries_filters_required_and_private(monkeypatch) -> None:
    def case14():
        """IEEE 14-bus test case."""

    def case118(scale: float = 1.0):
        """IEEE 118-bus test case."""

    def needs_arg(arg):
        return arg

    fake_module = SimpleNamespace(
        case14=case14,
        case118=case118,
        needs_arg=needs_arg,
        _hidden=lambda: None,
    )
    monkeypatch.setattr(nc, "_import_networks_module", lambda: fake_module)

    names = [entry.name for entry in nc.discover_network_entries()]
    assert "case14" in names
    assert "case118" in names
    assert "needs_arg" not in names
    assert "_hidden" not in names


def test_list_available_networks_query_and_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        nc,
        "discover_network_entries",
        lambda: [
            nc.NetworkEntry(name="case14", category="ieee_case", doc="a"),
            nc.NetworkEntry(name="case118", category="ieee_case", doc="b"),
            nc.NetworkEntry(name="cigre_mv", category="cigre", doc="c"),
        ],
    )
    out = nc.list_available_networks(query="case", max_results=1)
    assert len(out) == 1
    assert out[0]["name"] in {"case14", "case118"}


def test_suggest_network_names() -> None:
    names = ["case14", "case30", "case118", "cigre_mv"]
    suggestions = nc.suggest_network_names("case1x", names, limit=3)
    assert suggestions
    assert any(name.startswith("case1") for name in suggestions)
