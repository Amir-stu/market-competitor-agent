from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from pptx import Presentation

from mca.charts import render_charts
from mca.checks import apply_decisions, run_checks
from mca.contracts import Decisions, Extracted, Finding, Findings
from mca.export import export_pptx, export_xlsx
from mca.sources import dump_source
from tests.conftest import make_fact

A, B, C = "Wettbewerber A", "Wettbewerber B", "Wettbewerber C"


@pytest.fixture
def validated(scope):
    facts = [
        make_fact("F1", A, "umsatz", 100.0, locator="Zeile 2"),
        make_fact("F2", B, "umsatz", 80.0),
        make_fact("F3", A, "marktanteil", 40.0, source_id="S2"),
    ]
    extracted = Extracted(facts=facts)
    return apply_decisions(extracted, scope, run_checks(extracted, scope), Decisions())


@pytest.fixture
def findings():
    return Findings(
        findings=[
            Finding(id="K1", headline="A führt beim Umsatz", statement="A: 100 Mio EUR.", fact_ids=["F1"], chart_id="umsatz"),
            Finding(id="K2", headline="Marktanteil", statement="A hält 40 %.", fact_ids=["F3"]),
        ]
    )


def test_render_charts_when_kpi_has_values_writes_png(scope, validated, tmp_path):
    index = render_charts(scope, validated, tmp_path)
    by_kpi = {c.kpi: c for c in index.charts}
    assert set(by_kpi) == {"umsatz", "marktanteil"}
    assert Path(by_kpi["umsatz"].path).stat().st_size > 0
    assert by_kpi["umsatz"].fact_ids == ["F1", "F2"]


def test_render_charts_when_kpi_has_no_values_skips_it(scope, validated, tmp_path):
    no_share = validated.model_copy(update={"table": [c for c in validated.table if c.kpi == "umsatz"]})
    assert [c.kpi for c in render_charts(scope, no_share, tmp_path).charts] == ["umsatz"]


def test_export_xlsx_when_called_writes_values_with_sources(scope, validated, findings, tmp_path):
    path = export_xlsx(scope, validated, findings, tmp_path / "a.xlsx")
    workbook = load_workbook(path)
    assert {"Auftrag", "Vergleich", "Fakten", "Prüfung", "Kernaussagen"} <= set(workbook.sheetnames)
    rows = list(workbook["Vergleich"].iter_rows(values_only=True))
    assert rows[0] == ("Wettbewerber", "Umsatz (Mio EUR)", "Quelle", "Marktanteil (%)", "Quelle")
    assert rows[1] == (A, 100.0, "S1 · Zeile 2", 40.0, "S2 · A1")
    assert rows[3] == (C, None, "Lücke", None, "Lücke")


def test_export_xlsx_every_numeric_cell_has_source(scope, validated, findings, tmp_path):
    sheet = load_workbook(export_xlsx(scope, validated, findings, tmp_path / "a.xlsx"))["Vergleich"]
    for row in sheet.iter_rows(min_row=2, values_only=True):
        for value, source in zip(row[1::2], row[2::2]):
            assert value is None or source.startswith("S")


def test_export_pptx_when_called_has_title_findings_and_sources(scope, validated, findings, tmp_path):
    charts = render_charts(scope, validated, tmp_path / "charts")
    path = export_pptx(scope, validated, findings, charts, tmp_path / "a.pptx")
    slides = Presentation(path).slides
    assert len(slides) == 1 + len(findings.findings) + 1
    titles = [s.shapes.title.text for s in slides]
    assert titles[1] == "A führt beim Umsatz"
    assert titles[-1] == "Quellen & Prüfhinweise"
    picture_counts = [sum(1 for sh in s.shapes if sh.shape_type == 13) for s in slides]
    assert picture_counts[1] == 1 and picture_counts[2] == 0


def test_dump_source_when_csv_prints_cell_refs(tmp_path):
    path = tmp_path / "k.csv"
    path.write_text("Firma;Umsatz\nWettbewerber A;100\n", encoding="utf-8")
    assert dump_source(path).splitlines() == ["# k.csv", "A1: Firma", "B1: Umsatz", "A2: Wettbewerber A", "B2: 100"]


def test_dump_source_when_xlsx_prints_sheet_cell_refs(tmp_path):
    workbook = Workbook()
    workbook.active.title = "Daten"
    workbook.active["B3"] = 42
    path = tmp_path / "k.xlsx"
    workbook.save(path)
    assert "Daten!B3: 42" in dump_source(path)


def test_dump_source_when_unsupported_raises(tmp_path):
    path = tmp_path / "k.pdf"
    path.write_bytes(b"%PDF")
    with pytest.raises(ValueError, match="Read tool"):
        dump_source(path)
