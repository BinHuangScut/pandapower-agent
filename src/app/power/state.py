from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SessionState:
    base_net: Any | None = None
    working_net: Any | None = None
    current_network_name: str | None = None
    scenarios: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    rollback_net: Any | None = None
    mutation_log: list[dict[str, Any]] = field(default_factory=list)
    last_results: dict[str, Any] = field(default_factory=dict)
    active_scenario_name: str = "current"

    def has_net(self) -> bool:
        return self.working_net is not None

    def set_base_and_current(self, net: Any) -> None:
        self.base_net = copy.deepcopy(net)
        self.working_net = copy.deepcopy(net)
        self.current_network_name = getattr(net, "name", None)
        self.scenarios["base"] = copy.deepcopy(net)
        self.scenarios["current"] = copy.deepcopy(net)
        self.active_scenario_name = "current"
        self.mutation_log.clear()
        self.last_results.clear()

    def push_mutation_snapshot(self, label: str = "mutation") -> None:
        if self.working_net is None:
            return
        snapshot = copy.deepcopy(self.working_net)
        self.rollback_net = snapshot
        self.mutation_log.append({"label": label, "net": snapshot})

    def snapshot_before_mutation(self, label: str = "mutation") -> None:
        self.push_mutation_snapshot(label)

    def undo_last_mutation(self) -> bool:
        if not self.mutation_log:
            return False
        snap = self.mutation_log.pop()
        self.working_net = copy.deepcopy(snap["net"])
        self.scenarios["current"] = copy.deepcopy(self.working_net)
        self.active_scenario_name = "current"
        return True

    def save_scenario(self, name: str) -> None:
        if self.working_net is None:
            raise ValueError("No active working network")
        self.scenarios[name] = copy.deepcopy(self.working_net)
        if name == "current":
            self.active_scenario_name = "current"

    def list_scenarios(self) -> list[str]:
        return sorted(self.scenarios.keys())

    def delete_scenario(self, name: str) -> None:
        if name in {"base", "current"}:
            raise ValueError("base/current scenarios cannot be deleted")
        if name not in self.scenarios:
            raise ValueError(f"Scenario '{name}' not found")
        del self.scenarios[name]

    def load_scenario(self, name: str) -> None:
        if name not in self.scenarios:
            raise ValueError(f"Scenario '{name}' not found")
        self.working_net = copy.deepcopy(self.scenarios[name])
        self.current_network_name = getattr(self.working_net, "name", None)
        self.scenarios["current"] = copy.deepcopy(self.working_net)
        self.active_scenario_name = name

    def record_result(self, key: str, payload: dict[str, Any]) -> None:
        self.last_results[key] = copy.deepcopy(payload)

    def reset(self) -> None:
        self.base_net = None
        self.working_net = None
        self.current_network_name = None
        self.scenarios.clear()
        self.history.clear()
        self.rollback_net = None
        self.mutation_log.clear()
        self.last_results.clear()
        self.active_scenario_name = "current"
