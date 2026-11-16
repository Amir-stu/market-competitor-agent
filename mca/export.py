"""Step 6: deterministic Excel and PowerPoint export. No LLM touches these files."""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from pptx import Presentation
from pptx.util import Inches, Pt

from mca.contracts import ChartIndex, Findings, Scope, Validated

GAP_LABEL = "Lücke"
SLIDE_WIDTH, SLIDE_HEIGHT = Inches(13.333), Inches(7.5)
TITLE_LAYOUT, TITLE_ONLY_LAYOUT = 0, 5
BODY_FONT_SIZE = Pt(16)


def _source_label(validated: Validated, fact_id: str) -> str:
    fact = validated.fact(fact_id)
    return f"{fact.source_id} · {fact.locator}"


def _comparison_rows(scope: Scope, validated: Validated) -> list[list]:
    header = ["Wettbewerber", *(item for k in scope.kpis for item in (f"{k.name} ({k.unit})", "Quelle"))]
    cells = {(c.competitor, c.kpi): c.fact_id for c in validated.table}

    def pair(competitor: str, kpi_id: str) -> list:
        fact_id = cells.get((competitor, kpi_id))
        if fact_id is None:
            return [None, GAP_LABEL]
        return [validated.fact(fact_id).value, _source_label(validated, fact_id)]

    body = [[c, *(v for k in scope.kpis for v in pair(c, k.id))] for c in scope.competitors]
    return [header, *body]


def _review_rows(validated: Validated) -> list[list]:
    checks = validated.checks
    return [
        ["Typ", "Detail"],
        *(["Konflikt", f"{c.id}: {c.competitor} / {c.kpi}, Fakten {', '.join(c.fact_ids)}"] for c in checks.conflicts),
        *(["Verworfen", f"{d.fact_id}: {d.reason}"] for d in validated.dropped),
        *(["Lücke", f"{g.competitor} / {g.kpi}"] for g in checks.gaps),
        *([f"Hinweis ({f.kind})", f"{f.fact_id}: {f.detail}"] for f in checks.flags),
    ]


def _sheets(scope: Scope, validated: Validated, findings: Findings) -> dict[str, list[list]]:
    fact_header = ["ID", "Wettbewerber", "KPI", "Wert", "Einheit", "Periode", "Quelle", "Fundstelle", "Zitat"]
    return {
        "Auftrag": [
            ["Feld", "Wert"],
            ["Markt", scope.market],
            ["Region", scope.geography],
            ["Zeitraum", scope.period],
            ["Währung", scope.currency],
            *(["Quelle " + s.id, s.location] for s in scope.sources),
        ],
        "Vergleich": _comparison_rows(scope, validated),
        "Fakten": [
            fact_header,
            *([f.id, f.competitor, f.kpi, f.value, f.unit, f.period, f.source_id, f.locator, f.quote] for f in validated.facts),
        ],
        "Prüfung": _review_rows(validated),
        "Kernaussagen": [
            ["ID", "Kernaussage", "Aussage", "Fakten", "Diagramm"],
            *([f.id, f.headline, f.statement, ", ".join(f.fact_ids), f.chart_id] for f in findings.findings),
        ],
    }


def export_xlsx(scope: Scope, validated: Validated, findings: Findings, path: Path) -> Path:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in _sheets(scope, validated, findings).items():
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def _add_text(slide, text: str, top: float, height: float) -> None:
    frame = slide.shapes.add_textbox(Inches(0.6), Inches(top), Inches(12.1), Inches(height)).text_frame
    frame.word_wrap = True
    for index, line in enumerate(text.splitlines()):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.font.size = BODY_FONT_SIZE


def _closing_text(scope: Scope, validated: Validated) -> str:
    sources = [f"{s.id}: {s.location}" for s in scope.sources]
    review = [" – ".join(str(v) for v in row) for row in _review_rows(validated)[1:]]
    return "\n".join([*sources, "", *(review or ["Keine offenen Prüfhinweise."])])


def export_pptx(scope: Scope, validated: Validated, findings: Findings, charts: ChartIndex, path: Path) -> Path:
    deck = Presentation()
    deck.slide_width, deck.slide_height = SLIDE_WIDTH, SLIDE_HEIGHT
    title = deck.slides.add_slide(deck.slide_layouts[TITLE_LAYOUT])
    title.shapes.title.text = f"Markt- und Wettbewerbsanalyse: {scope.market}"
    title.placeholders[1].text = f"{scope.geography} · {scope.period}"
    chart_paths = {c.id: c.path for c in charts.charts}
    for finding in findings.findings:
        slide = deck.slides.add_slide(deck.slide_layouts[TITLE_ONLY_LAYOUT])
        slide.shapes.title.text = finding.headline
        _add_text(slide, finding.statement, top=1.5, height=1.2)
        if finding.chart_id in chart_paths:
            slide.shapes.add_picture(chart_paths[finding.chart_id], Inches(0.6), Inches(2.8), height=Inches(4.0))
        cited = ", ".join(_source_label(validated, fid) for fid in finding.fact_ids)
        _add_text(slide, f"Quellen: {cited}", top=6.9, height=0.4)
    closing = deck.slides.add_slide(deck.slide_layouts[TITLE_ONLY_LAYOUT])
    closing.shapes.title.text = "Quellen & Prüfhinweise"
    _add_text(closing, _closing_text(scope, validated), top=1.5, height=5.5)
    path.parent.mkdir(parents=True, exist_ok=True)
    deck.save(path)
    return path
