from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LoadBuiltinNetworkArgs(BaseModel):
    case_name: str = Field(default="case14", min_length=1)


class ListBuiltinNetworksArgs(BaseModel):
    query: str | None = Field(default=None, max_length=128)
    max_results: int = Field(default=20, ge=1, le=200)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class GetCurrentNetworkInfoArgs(BaseModel):
    pass


class RunPowerFlowArgs(BaseModel):
    algorithm: str | None = Field(default=None)
    enforce_q_lims: bool = Field(default=False)


class RunDCPowerFlowArgs(BaseModel):
    calculate_voltage_angles: bool = Field(default=True)


class RunThreePhasePowerFlowArgs(BaseModel):
    max_iteration: int = Field(default=30, ge=1, le=200)


class RunShortCircuitArgs(BaseModel):
    case: Literal["max", "min"] = Field(default="max")
    fault: Literal["3ph", "2ph", "1ph"] = Field(default="3ph")
    bus_ids: list[int] | None = None


class RunDiagnosticArgs(BaseModel):
    compact_report: bool = Field(default=True)


class RunTopologyAnalysisArgs(BaseModel):
    respect_switches: bool = Field(default=True)


class RunContingencyScreeningArgs(BaseModel):
    element_types: list[Literal["line", "trafo"]] = Field(default_factory=lambda: ["line", "trafo"])
    top_k: int = Field(default=10, ge=1, le=200)
    max_outages: int = Field(default=20, ge=1, le=1000)
    loading_threshold: float = Field(default=100.0, ge=1.0, le=500.0)
    vm_min_pu: float = Field(default=0.95, ge=0.5, le=1.2)
    vm_max_pu: float = Field(default=1.05, ge=0.8, le=1.5)


class RunOPFArgs(BaseModel):
    objective: Literal["min_cost", "min_losses"] = Field(default="min_cost")


class RunStateEstimationArgs(BaseModel):
    measurement_set: Literal["synthetic", "provided"] = Field(default="synthetic")
    init: Literal["flat", "results"] = Field(default="flat")


class PlotAnalysisResultArgs(BaseModel):
    source_tool: str | None = Field(default=None, max_length=128)
    metric: str | None = Field(default=None, max_length=128)
    chart: Literal["auto", "bar", "line"] = Field(default="auto")
    top_n: int = Field(default=20, ge=1, le=200)
    path: str = Field(default="./outputs/analysis_plot.png", min_length=1, max_length=2048)

    @field_validator("source_tool", "metric", "path")
    @classmethod
    def normalize_string(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class PlotNetworkArgs(BaseModel):
    path: str = Field(default="./outputs/network_plot.png", min_length=1, max_length=2048)
    respect_switches: bool = Field(default=True)
    library: Literal["networkx", "igraph"] = Field(default="networkx")
    bus_size: float = Field(default=1.0, gt=0.0, le=100.0)
    line_width: float = Field(default=1.0, gt=0.0, le=20.0)
    show_bus_labels: bool = Field(default=True)
    label_font_size: float = Field(default=8.0, gt=1.0, le=40.0)
    plot_loads: bool = Field(default=False)
    plot_gens: bool = Field(default=False)
    plot_sgens: bool = Field(default=False)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("path cannot be empty")
        return stripped


class SetLoadArgs(BaseModel):
    p_mw_delta: float | None = Field(default=None, ge=-1e4, le=1e4)
    q_mvar_delta: float | None = Field(default=None, ge=-1e4, le=1e4)
    bus_ids: list[int] | None = None

    @model_validator(mode="after")
    def validate_delta(self) -> "SetLoadArgs":
        if self.p_mw_delta is None and self.q_mvar_delta is None:
            raise ValueError("At least one of p_mw_delta or q_mvar_delta must be provided")
        return self


class AddDGArgs(BaseModel):
    bus_id: int = Field(ge=0)
    p_mw: float = Field(gt=0, le=1e4)
    vm_pu: float = Field(default=1.0, ge=0.8, le=1.2)
    name: str | None = Field(default=None, max_length=128)


class ToggleElementArgs(BaseModel):
    element_type: Literal["line", "load", "sgen", "gen", "trafo", "ext_grid"]
    element_id: int = Field(ge=0)
    in_service: bool


class UpdateElementParamsArgs(BaseModel):
    element_type: Literal["bus", "line", "load", "sgen", "gen", "trafo", "ext_grid"]
    element_id: int = Field(ge=0)
    fields: dict[str, float | int | str | bool]

    @field_validator("fields")
    @classmethod
    def validate_fields_not_empty(cls, v: dict[str, float | int | str | bool]) -> dict[str, float | int | str | bool]:
        if not v:
            raise ValueError("fields cannot be empty")
        return v


class CreateLoadArgs(BaseModel):
    bus_id: int = Field(ge=0)
    p_mw: float = Field(ge=0, le=1e5)
    q_mvar: float = Field(default=0.0, ge=-1e5, le=1e5)
    name: str | None = Field(default=None, max_length=128)


class CreateSgenArgs(BaseModel):
    bus_id: int = Field(ge=0)
    p_mw: float = Field(ge=0, le=1e5)
    q_mvar: float = Field(default=0.0, ge=-1e5, le=1e5)
    name: str | None = Field(default=None, max_length=128)


class CreateLineFromParametersArgs(BaseModel):
    from_bus: int = Field(ge=0)
    to_bus: int = Field(ge=0)
    length_km: float = Field(gt=0, le=1e4)
    r_ohm_per_km: float = Field(ge=0, le=1e4)
    x_ohm_per_km: float = Field(ge=0, le=1e4)
    c_nf_per_km: float = Field(ge=0, le=1e6)
    max_i_ka: float = Field(gt=0, le=1e3)
    name: str | None = Field(default=None, max_length=128)


class CreateTransformerFromParametersArgs(BaseModel):
    hv_bus: int = Field(ge=0)
    lv_bus: int = Field(ge=0)
    sn_mva: float = Field(gt=0, le=1e5)
    vn_hv_kv: float = Field(gt=0, le=1e4)
    vn_lv_kv: float = Field(gt=0, le=1e4)
    vk_percent: float = Field(gt=0, le=100)
    vkr_percent: float = Field(ge=0, le=100)
    pfe_kw: float = Field(ge=0, le=1e6)
    i0_percent: float = Field(ge=0, le=100)
    shift_degree: float = Field(default=0.0, ge=-360.0, le=360.0)
    name: str | None = Field(default=None, max_length=128)


class SaveScenarioArgs(BaseModel):
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def no_reserved_name(cls, v: str) -> str:
        if v.strip().lower() in {"current"}:
            raise ValueError("'current' is reserved")
        return v.strip()


class LoadScenarioArgs(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class ListScenariosArgs(BaseModel):
    pass


class DeleteScenarioArgs(BaseModel):
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_delete_name(cls, v: str) -> str:
        name = v.strip()
        if name in {"base", "current"}:
            raise ValueError("base/current scenarios cannot be deleted")
        return name


class UndoLastMutationArgs(BaseModel):
    pass


class CompareScenariosArgs(BaseModel):
    a: str = Field(min_length=1)
    b: str = Field(min_length=1)
    metrics: list[str] | None = None


class GetBusSummaryArgs(BaseModel):
    top_n: int = Field(default=10, ge=1, le=200)


class GetLineLoadingViolationsArgs(BaseModel):
    threshold: float = Field(default=80.0, ge=0.0, le=300.0)


class ExportArgs(BaseModel):
    export_type: Literal["summary", "results"] = Field(default="summary", alias="type")
    path: str = Field(min_length=1, max_length=2048)
