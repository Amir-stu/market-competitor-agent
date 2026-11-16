"""Step 5: the review summary shown to the human before "Freigegeben" or "Änderungen"."""

from mca.contracts import ChartIndex, Findings, Scope, Validated


def _table(scope: Scope, validated: Validated) -> list[str]:
    cells = {(c.competitor, c.kpi): c.fact_id for c in validated.table}

    def show(competitor: str, kpi_id: str) -> str:
        fact_id = cells.get((competitor, kpi_id))
        return "LÜCKE" if fact_id is None else f"{validated.fact(fact_id).value:g} [{fact_id}]"

    header = "| Wettbewerber | " + " | ".join(f"{k.name} ({k.unit})" for k in scope.kpis) + " |"
    divider = "|" + "---|" * (len(scope.kpis) + 1)
    rows = [f"| {c} | " + " | ".join(show(c, k.id) for k in scope.kpis) + " |" for c in scope.competitors]
    return [header, divider, *rows]


def _bullets(title: str, items: list[str]) -> list[str]:
    return ["", f"## {title}", *(f"- {item}" for item in items or ["keine"])]


def review_summary(scope: Scope, validated: Validated, findings: Findings, charts: ChartIndex, revisions: int) -> str:
    checks = validated.checks
    lines = [
        f"# Prüfvorlage: {scope.market} ({scope.geography}, {scope.period}), Revision {revisions}",
        "",
        "## Vergleich",
        *_table(scope, validated),
        *_bullets(
            "Konflikte",
            [f"{c.id}: {c.competitor} / {c.kpi}, Fakten {', '.join(c.fact_ids)}, Spanne {c.spread:.1%}" for c in checks.conflicts],
        ),
        *_bullets("Verworfene Fakten", [f"{d.fact_id}: {d.reason}" for d in validated.dropped]),
        *_bullets("Lücken", [f"{g.competitor} / {g.kpi}" for g in checks.gaps]),
        *_bullets("Hinweise", [f"{f.fact_id} ({f.kind}): {f.detail}" for f in checks.flags]),
        *_bullets(
            "Kernaussagen",
            [f"**{f.headline}**: {f.statement} [{', '.join(f.fact_ids)}]" for f in findings.findings],
        ),
        *_bullets("Diagramme", [c.path for c in charts.charts]),
    ]
    if validated.notes:
        lines = [*lines, "", "## Notizen der Prüfung", validated.notes]
    return "\n".join(lines)
