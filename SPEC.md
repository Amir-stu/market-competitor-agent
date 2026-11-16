# Spec: Market & Competitor Analysis Agent (Markt- und Wettbewerbsanalyse)

Status: APPROVED 2026-11-16. Runtime decision: Claude Code agents.

## Objective

Turn the six-box diagram into a pipeline of six steps, each with its own instruction file that is spun up as a Claude Code subagent. An orchestrator skill (`/mca-run`) runs them in order. It passes outputs between them as validated JSON files, stops at a human review gate, and loops back on "Änderungen".

```
1 Auftrag ─► 2 Auswerten ─► 3 Prüfen & Vergleichen ─► 4 Diagramme & Kernaussagen ─► 5 Deine Prüfung ─► 6 Excel & PowerPoint
                                   ▲                                                    │
                                   └──────────────── Änderungen (feedback) ─────────────┘
```

User: a consultant or analyst who gets a market and a competitor list and needs a checked Excel file and a deck.

Success: on one real brief, the run produces an `.xlsx` and a `.pptx` where every number traces back to a cited source (file + sheet/cell/page, or URL). The analyst approves after at most 2 revision loops.

## Runtime split: what the LLM does vs. what code does

Claude Code subagents handle judgment: they scope the brief, read sources, resolve conflicts and write Kernaussagen. A Python CLI (`mca`) handles everything that has to be exact or enforced:

| Concern | Enforced by |
|---|---|
| Step order and the 3-revision cap | `mca complete` / `mca feedback` refuse out-of-order or over-cap moves (`state.json`) |
| Artifact shape | pydantic contracts, checked by `mca complete <step>` |
| Conflicts, gaps, outliers, units | `mca check` (pure Python) |
| Charts | `mca charts` (matplotlib from validated data) |
| Numbers inside Kernaussagen | `mca complete 4` rejects any number that isn't a cited fact's value |
| Excel/PowerPoint | `mca export` (openpyxl, python-pptx), no LLM |

**Known limit of this runtime:** the orchestrator is a prompt, so Claude decides when to call the next agent. The state machine in `mca` makes skipping a step or exceeding the cap fail loudly, but it can't force Claude to call it. A Python orchestrator would have enforced this in code. You chose this trade-off.

## Step contracts

Every step reads artifacts from `runs/<run_id>/` and writes one artifact. The orchestrator then runs `mca complete <n> <run_dir>`. If validation fails, the agent is re-spawned once with the error. If it fails again, the run halts.

| # | Box | Instruction file | Who | Writes |
|---|-----|------------------|-----|--------|
| 1 | Auftrag | `.claude/agents/mca-01-auftrag.md` | subagent | `01_scope.json`: market, geography, period, currency, competitors, KPIs, sources, open_questions |
| 2 | Auswerten | `.claude/agents/mca-02-auswerten.md` | subagent (Read, WebFetch, `mca dump-source`) | `02_extracted.json`: one fact per value, with `source_id`, `locator` and verbatim `quote` |
| 3 | Prüfen & Vergleichen | `.claude/agents/mca-03-pruefen.md` | `mca check` → subagent → `mca complete 3` | `03_checks.json` (code), `03_decisions.json` (agent: which source wins each conflict, which facts to exclude), `03_validated.json` (code applies the decisions) |
| 4 | Diagramme & Kernaussagen | `.claude/agents/mca-04-diagramme.md` | `mca charts` → subagent | `charts/*.png`, `04_charts.json`, `04_findings.json` (each statement cites fact IDs) |
| 5 | Deine Prüfung | `.claude/skills/mca-run/pruefung.md` (checklist for the human; not a subagent) | you, via the orchestrator | `05_feedback.json` written by `mca feedback` |
| 6 | Ergebnisse aufbereiten | `.claude/agents/mca-06-export.md` | subagent runs `mca export` and checks the files | `out/analyse.xlsx`, `out/analyse.pptx` |

Deterministic checks in step 3:
- a fact whose unit or period doesn't match its KPI/scope is flagged as `mismatch`
- a conflict when two sources give the same competitor/KPI/period values that differ by more than 5%
- a gap for each competitor × KPI cell that has no value
- an outlier flag for values outside the IQR fence (1.5×IQR, needs at least 4 values), which is shown and never auto-deleted
- every fact's `source_id` exists in the scope

`mca complete 3` fails while any conflict is unresolved.

## Tech Stack

Python ≥3.12 (3.13 on this machine), pydantic v2, openpyxl, python-pptx, matplotlib, pyyaml, pytest + pytest-cov. Claude Code (subagents + project skill).

## Commands

```
Install:  python -m venv .venv --system-site-packages && .venv/Scripts/pip install -e . --no-deps
Run:      claude   (opened in this folder)   →   /mca-run examples/brief.example.yaml
Resume:   /mca-run runs/<run_id>
Test:     .venv/Scripts/python -m pytest --cov=mca --cov-fail-under=80
```

## Project Structure

```
market-competitor-agent/
  SPEC.md
  .claude/agents/mca-0N-*.md   instruction files for boxes 1, 2, 3, 4, 6 (subagents)
  .claude/skills/mca-run/      orchestrator (SKILL.md) + box 5 checklist (pruefung.md)
  mca/
    config.py      thresholds and file names
    contracts.py   pydantic models for every artifact
    state.py       run state machine (order, revisions, cap)
    checks.py      step-3 checks + apply decisions
    findings.py    step-4 citation and number guard
    charts.py      step-4 matplotlib
    export.py      step-6 xlsx + pptx
    sources.py     dump xlsx/csv to text with cell locators
    summary.py     step-5 review summary
    cli.py         `mca` entry point
  tests/
  examples/        obviously fake fixture data ("Wettbewerber A/B/C")
  runs/            gitignored
```

## Boundaries

- Always: validate every artifact through `mca complete`, keep a source ref on every number, write all run state to `runs/<id>/`.
- Ask first: open web search (step 2 fetches only the URLs listed in the brief), new dependencies, any GitHub push.
- Never: let an LLM type a figure into Excel/PPT, delete outliers silently, skip the human gate.

## Success Criteria (EARS)

- WHEN `/mca-run <brief>` is invoked THE SYSTEM SHALL run steps 1–4 in order and pause at step 5.
- IF step N is completed before step N−1 THEN THE SYSTEM SHALL refuse with an error.
- IF an artifact fails its contract THEN `mca complete` SHALL exit non-zero with the validation error.
- IF any conflict is unresolved THEN THE SYSTEM SHALL refuse to complete step 3.
- IF a Kernaussage cites an unknown fact ID THEN THE SYSTEM SHALL refuse to complete step 4.
- IF a Kernaussage contains a number that is not a cited fact's value THEN THE SYSTEM SHALL refuse to complete step 4.
- WHEN the reviewer chooses "Änderungen" THE SYSTEM SHALL reset progress to after step 2 and rerun steps 3 and 4 with the comments.
- IF 3 revisions have been requested THEN THE SYSTEM SHALL refuse a fourth and halt for a decision.
- WHEN the reviewer chooses "Freigegeben" THE SYSTEM SHALL produce `analyse.xlsx` and `analyse.pptx`.
- THE SYSTEM SHALL write a source reference next to every numeric cell in the xlsx.

## Plan (build order)

1. Contracts + state machine (TDD)
2. Step-3 checks + decisions (TDD, exhaustive known-input tests)
3. Findings guard, charts, export, source dump (TDD)
4. CLI
5. Six agent files + orchestrator skill
6. End-to-end test: the scripted path on fixture data with hand-written agent outputs
7. **Live run on one real brief.** Not done until this passes. Blocked on: which market, which competitors, which source files.

## Open Questions

1. Which real brief will the first live run use? (blocks step 7)
2. Is there a corporate PowerPoint template? (default layout for now)
