import pytest

from mca.checks import DecisionError, apply_decisions, run_checks
from mca.contracts import Decisions, Exclusion, Extracted, Resolution
from tests.conftest import make_fact

A, B, C = "Wettbewerber A", "Wettbewerber B", "Wettbewerber C"


def full_facts():
    return [
        make_fact("F1", A, "umsatz", 100.0),
        make_fact("F2", B, "umsatz", 80.0),
        make_fact("F3", C, "umsatz", 60.0),
        make_fact("F4", A, "marktanteil", 40.0),
        make_fact("F5", B, "marktanteil", 30.0),
        make_fact("F6", C, "marktanteil", 20.0),
    ]


def replace_fact(facts, fact):
    return [f for f in facts if f.id != fact.id] + [fact]


def cell(validated, competitor, kpi):
    return next(c for c in validated.table if c.competitor == competitor and c.kpi == kpi)


def validate(extracted, scope, decisions=None):
    return apply_decisions(extracted, scope, run_checks(extracted, scope), decisions or Decisions())


def test_checks_when_clean_data_returns_no_findings(scope):
    checks = run_checks(Extracted(facts=full_facts()), scope)
    assert checks.conflicts == [] and checks.gaps == [] and checks.flags == []


def test_checks_when_values_differ_over_threshold_reports_conflict(scope):
    facts = [*full_facts(), make_fact("F7", A, "umsatz", 110.0, source_id="S2")]
    checks = run_checks(Extracted(facts=facts), scope)
    assert len(checks.conflicts) == 1
    assert set(checks.conflicts[0].fact_ids) == {"F1", "F7"}
    assert checks.conflicts[0].spread == pytest.approx(10 / 110)


def test_checks_when_values_differ_within_threshold_no_conflict(scope):
    facts = [*full_facts(), make_fact("F7", A, "umsatz", 104.0, source_id="S2")]
    assert run_checks(Extracted(facts=facts), scope).conflicts == []


def test_checks_when_values_differ_exactly_at_threshold_no_conflict(scope):
    facts = [*full_facts(), make_fact("F7", A, "umsatz", 95.0, source_id="S2")]
    assert run_checks(Extracted(facts=facts), scope).conflicts == []


def test_checks_when_both_zero_no_conflict(scope):
    facts = [make_fact("F1", A, "umsatz", 0.0), make_fact("F2", A, "umsatz", 0.0, source_id="S2")]
    assert run_checks(Extracted(facts=facts), scope).conflicts == []


def test_checks_when_cell_missing_reports_gap(scope):
    facts = [f for f in full_facts() if f.id != "F6"]
    gaps = run_checks(Extracted(facts=facts), scope).gaps
    assert [(g.competitor, g.kpi) for g in gaps] == [(C, "marktanteil")]


def test_checks_when_unit_differs_flags_mismatch_and_gap(scope):
    facts = replace_fact(full_facts(), make_fact("F1", A, "umsatz", 100.0, unit="Tsd EUR"))
    checks = run_checks(Extracted(facts=facts), scope)
    assert [(f.fact_id, f.kind) for f in checks.flags] == [("F1", "mismatch")]
    assert [(g.competitor, g.kpi) for g in checks.gaps] == [(A, "umsatz")]


def test_checks_when_unit_differs_only_in_case_no_flag(scope):
    facts = replace_fact(full_facts(), make_fact("F1", A, "umsatz", 100.0, unit=" mio eur "))
    assert run_checks(Extracted(facts=facts), scope).flags == []


def test_checks_when_period_differs_flags_mismatch_without_conflict(scope):
    facts = [*full_facts(), make_fact("F7", A, "umsatz", 50.0, period="2024")]
    checks = run_checks(Extracted(facts=facts), scope)
    assert [(f.fact_id, f.kind) for f in checks.flags] == [("F7", "mismatch")]
    assert checks.conflicts == []


def test_checks_when_value_far_outside_iqr_flags_outlier(scope):
    names = [f"Wettbewerber {letter}" for letter in "ABCDE"]
    wide_scope = scope.model_copy(update={"competitors": names})
    values = [10.0, 11.0, 12.0, 13.0, 500.0]
    facts = [make_fact(f"U{i}", name, "umsatz", v) for i, (name, v) in enumerate(zip(names, values), 1)]
    flags = run_checks(Extracted(facts=facts), wide_scope).flags
    assert [(f.fact_id, f.kind) for f in flags] == [("U5", "outlier")]


def test_checks_when_fewer_than_four_values_no_outlier(scope):
    facts = [make_fact("F1", A, "umsatz", 1.0), make_fact("F2", B, "umsatz", 1000.0)]
    assert all(f.kind != "outlier" for f in run_checks(Extracted(facts=facts), scope).flags)


def conflicted() -> Extracted:
    return Extracted(facts=[*full_facts(), make_fact("F7", A, "umsatz", 110.0, source_id="S2")])


def test_apply_when_conflict_unresolved_raises(scope):
    with pytest.raises(DecisionError, match="unresolved"):
        validate(conflicted(), scope)


def test_apply_when_conflict_resolved_uses_chosen_fact(scope):
    extracted = conflicted()
    conflict_id = run_checks(extracted, scope).conflicts[0].id
    decisions = Decisions(resolutions=[Resolution(conflict_id=conflict_id, chosen_fact_id="F7", rationale="neuer")])
    validated = validate(extracted, scope, decisions)
    assert cell(validated, A, "umsatz").fact_id == "F7"
    assert {f.id for f in validated.facts} == {"F2", "F3", "F4", "F5", "F6", "F7"}
    assert [d.fact_id for d in validated.dropped] == ["F1"]


def test_apply_when_resolution_picks_fact_outside_conflict_raises(scope):
    extracted = conflicted()
    conflict_id = run_checks(extracted, scope).conflicts[0].id
    decisions = Decisions(resolutions=[Resolution(conflict_id=conflict_id, chosen_fact_id="F2", rationale="x")])
    with pytest.raises(DecisionError):
        validate(extracted, scope, decisions)


def test_apply_when_resolution_names_unknown_conflict_raises(scope):
    decisions = Decisions(resolutions=[Resolution(conflict_id="K99", chosen_fact_id="F1", rationale="x")])
    with pytest.raises(DecisionError):
        validate(Extracted(facts=full_facts()), scope, decisions)


def test_apply_when_exclusion_unknown_fact_raises(scope):
    decisions = Decisions(exclusions=[Exclusion(fact_id="F99", reason="x")])
    with pytest.raises(DecisionError):
        validate(Extracted(facts=full_facts()), scope, decisions)


def test_apply_when_fact_excluded_cell_becomes_empty(scope):
    decisions = Decisions(exclusions=[Exclusion(fact_id="F6", reason="veraltet")])
    validated = validate(Extracted(facts=full_facts()), scope, decisions)
    assert cell(validated, C, "marktanteil").fact_id is None
    assert validated.dropped[0].reason == "veraltet"


def test_apply_when_mismatched_fact_keeps_it_out_of_table(scope):
    facts = replace_fact(full_facts(), make_fact("F1", A, "umsatz", 100.0, unit="Tsd EUR"))
    assert cell(validate(Extracted(facts=facts), scope), A, "umsatz").fact_id is None


def test_apply_when_agreeing_duplicates_table_uses_lowest_id(scope):
    facts = [*full_facts(), make_fact("F0", A, "umsatz", 101.0, source_id="S2")]
    assert cell(validate(Extracted(facts=facts), scope), A, "umsatz").fact_id == "F0"


def test_apply_table_covers_every_competitor_kpi_pair(scope):
    validated = validate(Extracted(facts=full_facts()), scope)
    assert len(validated.table) == len(scope.competitors) * len(scope.kpis)
