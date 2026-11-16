import pytest
from pydantic import ValidationError

from mca.contracts import Extracted, Kpi, Scope, Source, reference_errors
from tests.conftest import make_fact


def test_scope_when_duplicate_kpi_ids_raises(scope):
    kpis = [Kpi(id="x", name="a", unit="%"), Kpi(id="x", name="b", unit="%")]
    with pytest.raises(ValidationError):
        Scope(**{**scope.model_dump(), "kpis": kpis})


def test_scope_when_duplicate_source_ids_raises(scope):
    sources = [Source(id="S1", kind="file", location="a"), Source(id="S1", kind="url", location="b")]
    with pytest.raises(ValidationError):
        Scope(**{**scope.model_dump(), "sources": sources})


def test_scope_when_no_competitors_raises(scope):
    with pytest.raises(ValidationError):
        Scope(**{**scope.model_dump(), "competitors": []})


def test_scope_when_unknown_field_raises(scope):
    with pytest.raises(ValidationError):
        Scope(**{**scope.model_dump(), "extra": 1})


def test_fact_when_quote_empty_raises():
    with pytest.raises(ValidationError):
        make_fact("F1", "Wettbewerber A", "umsatz", 1.0, quote="")


def test_extracted_when_duplicate_fact_ids_raises():
    fact = make_fact("F1", "Wettbewerber A", "umsatz", 1.0)
    with pytest.raises(ValidationError):
        Extracted(facts=[fact, fact])


def test_reference_errors_when_all_known_returns_empty(scope):
    extracted = Extracted(facts=[make_fact("F1", "Wettbewerber A", "umsatz", 1.0)])
    assert reference_errors(extracted, scope) == []


def test_reference_errors_when_unknown_refs_lists_each(scope):
    extracted = Extracted(facts=[make_fact("F1", "Wettbewerber Z", "gewinn", 1.0, source_id="S9")])
    errors = reference_errors(extracted, scope)
    assert len(errors) == 3
    assert any("Wettbewerber Z" in e for e in errors)
    assert any("gewinn" in e for e in errors)
    assert any("S9" in e for e in errors)
