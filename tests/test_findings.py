import pytest

from mca.checks import apply_decisions, run_checks
from mca.contracts import Decisions, Extracted, Finding, Findings
from mca.findings import findings_errors, number_candidates
from tests.conftest import make_fact

A, B = "Wettbewerber A", "Wettbewerber B"


@pytest.fixture
def validated(scope):
    facts = [
        make_fact("F1", A, "umsatz", 1234.5),
        make_fact("F2", B, "umsatz", 80.0),
        make_fact("F3", A, "marktanteil", 23.456),
    ]
    extracted = Extracted(facts=facts)
    return apply_decisions(extracted, scope, run_checks(extracted, scope), Decisions())


def errors_for(statement, validated, fact_ids=("F1",), chart_id=None, chart_ids=frozenset()):
    finding = Finding(id="K1", headline="Titel", statement=statement, fact_ids=list(fact_ids), chart_id=chart_id)
    return findings_errors(Findings(findings=[finding]), validated, set(chart_ids))


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("12", {(12.0, 0)}),
        ("12,5", {(12.5, 1)}),
        ("12.5", {(12.5, 1)}),
        ("1.234,5", {(1234.5, 1)}),
        ("1,234.5", {(1234.5, 1)}),
        ("1.234", {(1.234, 3), (1234.0, 0)}),
    ],
)
def test_number_candidates_when_token_given_returns_both_readings(token, expected):
    assert number_candidates(token) == expected


@pytest.mark.parametrize(
    "statement",
    [
        "Wettbewerber A liegt bei 1.234,5 Mio EUR.",
        "Wettbewerber A liegt bei 1,234.5 Mio EUR.",
        "Wettbewerber A liegt bei rund 1.235 Mio EUR.",
        "Im Jahr 2025 führt Wettbewerber A.",
        "Wettbewerber A führt im Q3 laut F12.",
    ],
)
def test_findings_when_numbers_match_cited_facts_no_errors(statement, validated):
    assert errors_for(statement, validated) == []


def test_findings_when_rounded_percentage_matches_no_errors(validated):
    assert errors_for("Marktanteil 23,5 %.", validated, fact_ids=("F3",)) == []


def test_findings_when_number_not_in_cited_facts_reports_it(validated):
    errors = errors_for("Wettbewerber A wächst um 15 %.", validated)
    assert len(errors) == 1 and "15" in errors[0]


def test_findings_when_number_belongs_to_uncited_fact_reports_it(validated):
    assert errors_for("Wettbewerber B liegt bei 80 Mio EUR.", validated) != []


def test_findings_when_headline_has_unbacked_number_reports_it(validated):
    finding = Finding(id="K1", headline="A wächst 3x schneller", statement="Ohne Zahl.", fact_ids=["F1"])
    errors = findings_errors(Findings(findings=[finding]), validated, set())
    assert len(errors) == 1 and "'3'" in errors[0]


def test_findings_when_fact_id_unknown_reports_it(validated):
    errors = errors_for("Text ohne Zahl.", validated, fact_ids=("F99",))
    assert any("F99" in e for e in errors)


def test_findings_when_chart_id_unknown_reports_it(validated):
    errors = errors_for("Text ohne Zahl.", validated, chart_id="chart_x")
    assert any("chart_x" in e for e in errors)


def test_findings_when_chart_id_known_no_errors(validated):
    assert errors_for("Text ohne Zahl.", validated, chart_id="umsatz", chart_ids={"umsatz"}) == []
