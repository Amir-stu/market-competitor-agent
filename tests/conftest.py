from pathlib import Path

import pytest

from mca.contracts import Fact, Kpi, Scope, Source


@pytest.fixture
def scope() -> Scope:
    return Scope(
        market="Testmarkt Fake-Widgets",
        geography="DACH",
        period="2025",
        currency="EUR",
        competitors=["Wettbewerber A", "Wettbewerber B", "Wettbewerber C"],
        kpis=[
            Kpi(id="umsatz", name="Umsatz", unit="Mio EUR"),
            Kpi(id="marktanteil", name="Marktanteil", unit="%"),
        ],
        sources=[
            Source(id="S1", kind="file", location="examples/sources/kennzahlen.csv"),
            Source(id="S2", kind="url", location="https://example.invalid/bericht"),
        ],
    )


def make_fact(fact_id: str, competitor: str, kpi: str, value: float, **overrides) -> Fact:
    defaults = {
        "unit": "Mio EUR" if kpi == "umsatz" else "%",
        "period": "2025",
        "source_id": "S1",
        "locator": "A1",
        "quote": f"{value}",
    }
    return Fact(id=fact_id, competitor=competitor, kpi=kpi, value=value, **{**defaults, **overrides})


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "run"
