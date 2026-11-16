# Market & Competitor Analysis Agent

A six-step Claude Code pipeline:

1. Auftrag (brief)
2. Auswerten (extract)
3. Prüfen & Vergleichen (check and compare)
4. Diagramme & Kernaussagen (charts and key messages)
5. Deine Prüfung (your review)
6. Excel & PowerPoint

Each box has its own instruction file and runs as a subagent. The `mca` Python CLI does everything that has to be exact: it validates artifacts, enforces step order and the revision cap, runs the data checks, draws the charts and writes the Excel and PowerPoint files. An LLM never writes a number into the deliverables.

The design and acceptance criteria are in [SPEC.md](SPEC.md).

## Setup

```bash
python -m venv .venv --system-site-packages
.venv/Scripts/pip install -e . --no-deps
.venv/Scripts/python -m pytest --cov=mca
```

## Run

Open Claude Code **in this folder**, so the project agents and the `/mca-run` skill register, then run:

```
/mca-run examples/brief.example.yaml     # new run (fake demo data)
/mca-run runs/<run_id>                   # resume
```

## Files

| Box | Instruction file |
|---|---|
| 1 Auftrag | `.claude/agents/mca-01-auftrag.md` |
| 2 Auswerten | `.claude/agents/mca-02-auswerten.md` |
| 3 Prüfen & Vergleichen | `.claude/agents/mca-03-pruefen.md` |
| 4 Diagramme & Kernaussagen | `.claude/agents/mca-04-diagramme.md` |
| 5 Deine Prüfung | `.claude/skills/mca-run/pruefung.md` (human checklist) |
| 6 Excel & PowerPoint | `.claude/agents/mca-06-export.md` |
| Orchestrator | `.claude/skills/mca-run/SKILL.md` |

Each run writes everything to `runs/<id>/`:

- `01_scope.json`
- `02_extracted.json`
- `03_checks.json`, `03_decisions.json`, `03_validated.json`
- `04_charts.json`, `04_findings.json`, `charts/`
- `05_feedback.json`
- `out/analyse.xlsx`, `out/analyse.pptx`
- `state.json`
