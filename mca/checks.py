"""Step 3: deterministic data checks and application of the agent's decisions."""

from collections import defaultdict
from statistics import quantiles

from mca.config import CONFLICT_THRESHOLD, OUTLIER_IQR_FACTOR, OUTLIER_MIN_VALUES
from mca.contracts import (
    Checks,
    Conflict,
    Decisions,
    DroppedFact,
    Extracted,
    Fact,
    Flag,
    Gap,
    Scope,
    TableCell,
    Validated,
)


class DecisionError(ValueError):
    """The agent's decisions are incomplete or reference unknown ids."""


def _normalise_unit(unit: str) -> str:
    return " ".join(unit.lower().split())


def _mismatch_detail(fact: Fact, scope: Scope) -> str | None:
    expected_unit = scope.kpi(fact.kpi).unit
    if _normalise_unit(fact.unit) != _normalise_unit(expected_unit):
        return f"unit '{fact.unit}' != KPI unit '{expected_unit}'"
    if fact.period.strip() != scope.period.strip():
        return f"period '{fact.period}' != scope period '{scope.period}'"
    return None


def _usable(facts: list[Fact], scope: Scope) -> list[Fact]:
    return [f for f in facts if _mismatch_detail(f, scope) is None]


def _relative_spread(values: list[float]) -> float:
    high, low = max(values), min(values)
    scale = max(abs(high), abs(low))
    return 0.0 if scale == 0 else (high - low) / scale


def _find_conflicts(usable: list[Fact]) -> list[Conflict]:
    groups: dict[tuple[str, str, str], list[Fact]] = defaultdict(list)
    for fact in usable:
        groups[(fact.competitor, fact.kpi, fact.period)].append(fact)
    candidates = [
        (key, sorted(group, key=lambda f: f.id))
        for key, group in sorted(groups.items())
        if _relative_spread([f.value for f in group]) > CONFLICT_THRESHOLD + 1e-12
    ]
    return [
        Conflict(
            id=f"K{index}",
            competitor=competitor,
            kpi=kpi,
            period=period,
            fact_ids=[f.id for f in group],
            spread=_relative_spread([f.value for f in group]),
        )
        for index, ((competitor, kpi, period), group) in enumerate(candidates, 1)
    ]


def _find_gaps(usable: list[Fact], scope: Scope) -> list[Gap]:
    covered = {(f.competitor, f.kpi) for f in usable}
    return [
        Gap(competitor=competitor, kpi=kpi.id)
        for competitor in scope.competitors
        for kpi in scope.kpis
        if (competitor, kpi.id) not in covered
    ]


def _find_outliers(usable: list[Fact]) -> list[Flag]:
    by_kpi: dict[str, list[Fact]] = defaultdict(list)
    for fact in usable:
        by_kpi[fact.kpi].append(fact)
    flags: list[Flag] = []
    for kpi_facts in by_kpi.values():
        if len(kpi_facts) < OUTLIER_MIN_VALUES:
            continue
        q1, _, q3 = quantiles([f.value for f in kpi_facts], n=4, method="inclusive")
        low, high = q1 - OUTLIER_IQR_FACTOR * (q3 - q1), q3 + OUTLIER_IQR_FACTOR * (q3 - q1)
        flags = [
            *flags,
            *(
                Flag(fact_id=f.id, kind="outlier", detail=f"{f.value} outside [{low:g}, {high:g}]")
                for f in kpi_facts
                if not low <= f.value <= high
            ),
        ]
    return flags


def run_checks(extracted: Extracted, scope: Scope) -> Checks:
    facts = sorted(extracted.facts, key=lambda f: f.id)
    usable = _usable(facts, scope)
    mismatches = [
        Flag(fact_id=f.id, kind="mismatch", detail=detail)
        for f in facts
        if (detail := _mismatch_detail(f, scope)) is not None
    ]
    return Checks(
        conflicts=_find_conflicts(usable),
        gaps=_find_gaps(usable, scope),
        flags=[*mismatches, *_find_outliers(usable)],
    )


def _decision_drops(extracted: Extracted, checks: Checks, decisions: Decisions) -> list[DroppedFact]:
    conflicts = {c.id: c for c in checks.conflicts}
    known_facts = {f.id for f in extracted.facts}
    unknown_conflicts = [r.conflict_id for r in decisions.resolutions if r.conflict_id not in conflicts]
    if unknown_conflicts:
        raise DecisionError(f"resolutions for unknown conflicts: {unknown_conflicts}")
    bad_choices = [r.conflict_id for r in decisions.resolutions if r.chosen_fact_id not in conflicts[r.conflict_id].fact_ids]
    if bad_choices:
        raise DecisionError(f"chosen fact is not part of conflict: {bad_choices}")
    unresolved = sorted(set(conflicts) - {r.conflict_id for r in decisions.resolutions})
    if unresolved:
        raise DecisionError(f"unresolved conflicts: {unresolved}")
    unknown_exclusions = [e.fact_id for e in decisions.exclusions if e.fact_id not in known_facts]
    if unknown_exclusions:
        raise DecisionError(f"exclusions for unknown facts: {unknown_exclusions}")
    losers = [
        DroppedFact(fact_id=fact_id, reason=f"Konflikt {r.conflict_id}: {r.rationale}")
        for r in decisions.resolutions
        for fact_id in conflicts[r.conflict_id].fact_ids
        if fact_id != r.chosen_fact_id
    ]
    excluded = [DroppedFact(fact_id=e.fact_id, reason=e.reason) for e in decisions.exclusions]
    return [*losers, *excluded]


def _build_table(active: list[Fact], scope: Scope) -> list[TableCell]:
    usable = sorted(_usable(active, scope), key=lambda f: f.id)
    first: dict[tuple[str, str], str] = {}
    for fact in usable:
        first.setdefault((fact.competitor, fact.kpi), fact.id)
    return [
        TableCell(competitor=competitor, kpi=kpi.id, fact_id=first.get((competitor, kpi.id)))
        for competitor in scope.competitors
        for kpi in scope.kpis
    ]


def apply_decisions(extracted: Extracted, scope: Scope, checks: Checks, decisions: Decisions) -> Validated:
    dropped = _decision_drops(extracted, checks, decisions)
    dropped_ids = {d.fact_id for d in dropped}
    active = [f for f in sorted(extracted.facts, key=lambda f: f.id) if f.id not in dropped_ids]
    return Validated(
        facts=active,
        dropped=dropped,
        checks=checks,
        table=_build_table(active, scope),
        notes=decisions.notes,
    )
