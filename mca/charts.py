"""Step 4: one bar chart per KPI, drawn only from validated table values."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from mca.config import CHART_BAR_COLOR, CHART_DPI  # noqa: E402
from mca.contracts import Chart, ChartIndex, Kpi, Scope, Validated  # noqa: E402


def _draw(kpi: Kpi, labels: list[str], values: list[float], path: Path) -> None:
    figure, axes = plt.subplots(figsize=(8, 0.6 * len(labels) + 1.5))
    bars = axes.barh(labels[::-1], values[::-1], color=CHART_BAR_COLOR)
    axes.bar_label(bars, labels=[f"{v:g}" for v in values[::-1]], padding=3)
    axes.set_title(f"{kpi.name} ({kpi.unit})", loc="left")
    axes.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(path, dpi=CHART_DPI)
    plt.close(figure)


def render_charts(scope: Scope, validated: Validated, out_dir: Path) -> ChartIndex:
    out_dir.mkdir(parents=True, exist_ok=True)
    charts: list[Chart] = []
    for kpi in scope.kpis:
        cells = [c for c in validated.table if c.kpi == kpi.id and c.fact_id is not None]
        if not cells:
            continue
        facts = [validated.fact(c.fact_id) for c in cells if c.fact_id is not None]
        path = (out_dir / f"{kpi.id}.png").resolve()
        _draw(kpi, [f.competitor for f in facts], [f.value for f in facts], path)
        charts = [*charts, Chart(id=kpi.id, kpi=kpi.id, path=str(path), fact_ids=[f.id for f in facts])]
    return ChartIndex(charts=charts)
