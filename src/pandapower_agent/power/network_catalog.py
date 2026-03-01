from __future__ import annotations

import difflib
import inspect
from dataclasses import dataclass
from typing import Any


def _import_networks_module() -> Any:
    import pandapower.networks as pn  # type: ignore

    return pn


def _has_required_params(func: Any) -> bool:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return True

    for p in sig.parameters.values():
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.default is inspect._empty:
            return True
    return False


def _first_doc_line(func: Any) -> str | None:
    doc = inspect.getdoc(func)
    if not doc:
        return None
    line = doc.strip().splitlines()[0].strip()
    if len(line) > 120:
        return f"{line[:117]}..."
    return line


def _category_for_name(name: str) -> str:
    low = name.lower()
    if low.startswith("case"):
        return "ieee_case"
    if "cigre" in low:
        return "cigre"
    if "mv" in low or "lv" in low:
        return "distribution"
    return "misc"


@dataclass(slots=True)
class NetworkEntry:
    name: str
    category: str | None = None
    doc: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "category": self.category,
            "doc": self.doc,
        }


def discover_network_entries() -> list[NetworkEntry]:
    pn = _import_networks_module()
    entries: list[NetworkEntry] = []

    for name, obj in inspect.getmembers(pn):
        if name.startswith("_"):
            continue
        if not callable(obj):
            continue
        if inspect.isclass(obj):
            continue
        if _has_required_params(obj):
            continue
        entries.append(NetworkEntry(name=name, category=_category_for_name(name), doc=_first_doc_line(obj)))

    entries.sort(key=lambda x: x.name.lower())
    return entries


def list_available_networks(query: str | None = None, max_results: int = 20) -> list[dict[str, str | None]]:
    query_l = query.lower() if query else None
    items = discover_network_entries()
    if query_l:
        items = [item for item in items if query_l in item.name.lower()]

    return [item.as_dict() for item in items[:max_results]]


def get_network_factory(case_name: str) -> Any | None:
    pn = _import_networks_module()
    factory = getattr(pn, case_name, None)
    if factory is None or not callable(factory):
        return None
    if _has_required_params(factory):
        return None
    return factory


def suggest_network_names(case_name: str, available_names: list[str], limit: int = 5) -> list[str]:
    if not available_names:
        return []

    close = difflib.get_close_matches(case_name, available_names, n=limit, cutoff=0.2)
    if close:
        return close

    case_low = case_name.lower()
    fallback = [name for name in available_names if case_low in name.lower()]
    return fallback[:limit]
