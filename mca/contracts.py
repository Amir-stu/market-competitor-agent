"""Pydantic contracts for every artifact passed between pipeline steps."""

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _require_unique(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates = sorted({v for v in values if v in seen or seen.add(v)})
    if duplicates:
        raise ValueError(f"duplicate {label}: {', '.join(duplicates)}")


class Kpi(Contract):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)


class Source(Contract):
    id: str = Field(min_length=1)
    kind: Literal["file", "url"]
    location: str = Field(min_length=1)


class Scope(Contract):
    market: str = Field(min_length=1)
    geography: str = Field(min_length=1)
    period: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    competitors: list[str] = Field(min_length=1)
    kpis: list[Kpi] = Field(min_length=1)
    sources: list[Source] = Field(min_length=1)
    open_questions: list[str] = []

    @model_validator(mode="after")
    def _unique_ids(self) -> "Scope":
        _require_unique(self.competitors, "competitors")
        _require_unique((k.id for k in self.kpis), "kpi ids")
        _require_unique((s.id for s in self.sources), "source ids")
        return self

    def kpi(self, kpi_id: str) -> Kpi:
        return next(k for k in self.kpis if k.id == kpi_id)


class Fact(Contract):
    id: str = Field(min_length=1)
    competitor: str
    kpi: str
    value: float
    unit: str
    period: str
    source_id: str
    locator: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class Extracted(Contract):
    facts: list[Fact]

    @model_validator(mode="after")
    def _unique_ids(self) -> "Extracted":
        _require_unique((f.id for f in self.facts), "fact ids")
        return self


def reference_errors(extracted: Extracted, scope: Scope) -> list[str]:
    competitors = set(scope.competitors)
    kpis = {k.id for k in scope.kpis}
    sources = {s.id for s in scope.sources}
    checks = (
        ("competitor", lambda f: f.competitor, competitors),
        ("kpi", lambda f: f.kpi, kpis),
        ("source_id", lambda f: f.source_id, sources),
    )
    return [
        f"{fact.id}: unknown {label} '{getter(fact)}'"
        for fact in extracted.facts
        for label, getter, known in checks
        if getter(fact) not in known
    ]


class Conflict(Contract):
    id: str
    competitor: str
    kpi: str
    period: str
    fact_ids: list[str]
    spread: float


class Gap(Contract):
    competitor: str
    kpi: str


class Flag(Contract):
    fact_id: str
    kind: Literal["mismatch", "outlier"]
    detail: str


class Checks(Contract):
    conflicts: list[Conflict]
    gaps: list[Gap]
    flags: list[Flag]


class Resolution(Contract):
    conflict_id: str
    chosen_fact_id: str
    rationale: str = Field(min_length=1)


class Exclusion(Contract):
    fact_id: str
    reason: str = Field(min_length=1)


class Decisions(Contract):
    resolutions: list[Resolution] = []
    exclusions: list[Exclusion] = []
    notes: str = ""
    feedback_addressed: list[str] = []


class TableCell(Contract):
    competitor: str
    kpi: str
    fact_id: str | None


class DroppedFact(Contract):
    fact_id: str
    reason: str


class Validated(Contract):
    facts: list[Fact]
    dropped: list[DroppedFact]
    checks: Checks
    table: list[TableCell]
    notes: str = ""

    def fact(self, fact_id: str) -> Fact:
        return next(f for f in self.facts if f.id == fact_id)


class Chart(Contract):
    id: str
    kpi: str
    path: str
    fact_ids: list[str]


class ChartIndex(Contract):
    charts: list[Chart]


class Finding(Contract):
    id: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    fact_ids: list[str] = Field(min_length=1)
    chart_id: str | None = None


class Findings(Contract):
    findings: list[Finding] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Findings":
        _require_unique((f.id for f in self.findings), "finding ids")
        return self


class Feedback(Contract):
    decision: Literal["approved", "changes"]
    comments: list[str] = []
    revision: int
