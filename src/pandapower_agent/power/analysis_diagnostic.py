from __future__ import annotations

from typing import Any


def _import_diagnostic_module():
    import pandapower.diagnostic as diag  # type: ignore

    return diag


def run_diagnostic(net: Any, compact_report: bool = True) -> dict[str, Any]:
    diag = _import_diagnostic_module()
    try:
        report = diag.diagnostic(net, compact_report=compact_report)
    except TypeError:
        report = diag.diagnostic(net)

    if isinstance(report, dict):
        normalized: dict[str, Any] = report
    else:
        normalized = {"raw": str(report)}

    return {"diagnostic_report": normalized}
