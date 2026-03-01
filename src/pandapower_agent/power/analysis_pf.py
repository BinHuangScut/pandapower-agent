from __future__ import annotations

from typing import Any

from pandapower_agent.power.metrics import summarize_network_metrics


def _import_pp():
    import pandapower as pp  # type: ignore

    return pp


def run_ac_power_flow(net: Any, algorithm: str = "nr", enforce_q_lims: bool = False) -> dict[str, Any]:
    pp = _import_pp()
    pp.runpp(net, algorithm=algorithm, enforce_q_lims=enforce_q_lims)
    return {
        "mode": "ac",
        "machine_summary": summarize_network_metrics(net),
    }


def run_dc_power_flow(net: Any, calculate_voltage_angles: bool = True) -> dict[str, Any]:
    pp = _import_pp()
    pp.rundcpp(net, calculate_voltage_angles=calculate_voltage_angles)
    return {
        "mode": "dc",
        "machine_summary": summarize_network_metrics(net),
    }


def run_three_phase_power_flow(net: Any, max_iteration: int = 30) -> dict[str, Any]:
    pp = _import_pp()
    runpp_3ph = getattr(pp, "runpp_3ph", None)
    if runpp_3ph is None:
        raise RuntimeError("This pandapower version does not provide runpp_3ph")
    runpp_3ph(net, max_iteration=max_iteration)
    return {
        "mode": "3ph",
        "machine_summary": summarize_network_metrics(net),
    }
