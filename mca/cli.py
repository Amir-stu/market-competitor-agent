"""`mca`: the deterministic commands the orchestrator and subagents call between steps."""

import argparse
import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from mca import config
from mca.charts import render_charts
from mca.checks import DecisionError, apply_decisions, run_checks
from mca.contracts import (
    ChartIndex,
    Checks,
    Decisions,
    Extracted,
    Feedback,
    Findings,
    Scope,
    Validated,
    reference_errors,
)
from mca.export import export_pptx, export_xlsx
from mca.findings import findings_errors
from mca.sources import dump_source
from mca.state import RunState, StateError, complete, next_step, record_feedback
from mca.summary import review_summary

ModelT = TypeVar("ModelT", bound=BaseModel)


class StepFailed(RuntimeError):
    """A step's artifact failed a check; the message lists every problem."""


def _out(text: str) -> None:
    sys.stdout.write(text + "\n")


def _read(run: Path, name: str, model: type[ModelT]) -> ModelT:
    return model.model_validate_json((run / name).read_text(encoding="utf-8"))


def _write(run: Path, name: str, model: BaseModel) -> None:
    (run / name).write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _require_next(run: Path, step: int) -> RunState:
    state = _read(run, config.STATE_FILE, RunState)
    if next_step(state) != step:
        raise StateError(f"this command belongs to step {step}; next step is {next_step(state)}")
    return state


def _fail_if(errors: list[str]) -> None:
    if errors:
        raise StepFailed("\n".join(errors))


def cmd_init(args: argparse.Namespace) -> None:
    brief = Path(args.brief).resolve()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run = Path(args.runs_dir).resolve() / run_id
    run.mkdir(parents=True, exist_ok=False)
    shutil.copy(brief, run / config.BRIEF_FILE)
    _write(run, config.STATE_FILE, RunState(run_id=run_id))
    _out(str(run))


def cmd_next(args: argparse.Namespace) -> None:
    step = next_step(_read(Path(args.run), config.STATE_FILE, RunState))
    _out("done" if step is None else str(step))


def cmd_check(args: argparse.Namespace) -> None:
    run = Path(args.run)
    _require_next(run, 3)
    checks = run_checks(_read(run, config.EXTRACTED_FILE, Extracted), _read(run, config.SCOPE_FILE, Scope))
    _write(run, config.CHECKS_FILE, checks)
    _out(f"{len(checks.conflicts)} conflicts, {len(checks.gaps)} gaps, {len(checks.flags)} flags")


def cmd_charts(args: argparse.Namespace) -> None:
    run = Path(args.run)
    _require_next(run, 4)
    index = render_charts(
        _read(run, config.SCOPE_FILE, Scope),
        _read(run, config.VALIDATED_FILE, Validated),
        run / config.CHARTS_DIR,
    )
    _write(run, config.CHART_INDEX_FILE, index)
    _out(", ".join(c.id for c in index.charts) or "no charts: no KPI has values")


def _validate_step_one(run: Path) -> None:
    scope = _read(run, config.SCOPE_FILE, Scope)
    _fail_if([f"open question: {q}" for q in scope.open_questions])


def _validate_step_two(run: Path) -> None:
    extracted = _read(run, config.EXTRACTED_FILE, Extracted)
    _fail_if(reference_errors(extracted, _read(run, config.SCOPE_FILE, Scope)))


def _validate_step_three(run: Path) -> None:
    validated = apply_decisions(
        _read(run, config.EXTRACTED_FILE, Extracted),
        _read(run, config.SCOPE_FILE, Scope),
        _read(run, config.CHECKS_FILE, Checks),
        _read(run, config.DECISIONS_FILE, Decisions),
    )
    _write(run, config.VALIDATED_FILE, validated)


def _validate_step_four(run: Path) -> None:
    chart_ids = {c.id for c in _read(run, config.CHART_INDEX_FILE, ChartIndex).charts}
    findings = _read(run, config.FINDINGS_FILE, Findings)
    _fail_if(findings_errors(findings, _read(run, config.VALIDATED_FILE, Validated), chart_ids))


def _validate_step_six(run: Path) -> None:
    outputs = [run / config.OUTPUT_DIR / name for name in (config.XLSX_NAME, config.PPTX_NAME)]
    _fail_if([f"missing output: {p}" for p in outputs if not p.is_file()])


STEP_VALIDATORS: dict[int, Callable[[Path], None]] = {
    1: _validate_step_one,
    2: _validate_step_two,
    3: _validate_step_three,
    4: _validate_step_four,
    6: _validate_step_six,
}


def cmd_complete(args: argparse.Namespace) -> None:
    run = Path(args.run)
    state = _read(run, config.STATE_FILE, RunState)
    advanced = complete(state, args.step)
    STEP_VALIDATORS[args.step](run)
    _write(run, config.STATE_FILE, advanced)
    following = next_step(advanced)
    _out(f"step {args.step} complete; next: {'done' if following is None else following}")


def cmd_feedback(args: argparse.Namespace) -> None:
    run = Path(args.run)
    state = record_feedback(_read(run, config.STATE_FILE, RunState), args.decision)
    from_file = Path(args.comments_file).read_text(encoding="utf-8").splitlines() if args.comments_file else []
    comments = [c.strip() for c in [*args.comment, *from_file] if c.strip()]
    if args.decision == "changes" and not comments:
        raise StepFailed("'changes' needs at least one comment")
    _write(run, config.FEEDBACK_FILE, Feedback(decision=args.decision, comments=comments, revision=state.revisions))
    _write(run, config.STATE_FILE, state)
    _out(f"recorded '{args.decision}'; next step: {next_step(state)}")


def cmd_export(args: argparse.Namespace) -> None:
    run = Path(args.run)
    if _read(run, config.STATE_FILE, RunState).status != "approved":
        raise StateError("export needs an approved review (`mca feedback --decision approved`)")
    scope = _read(run, config.SCOPE_FILE, Scope)
    validated = _read(run, config.VALIDATED_FILE, Validated)
    findings = _read(run, config.FINDINGS_FILE, Findings)
    out = run.resolve() / config.OUTPUT_DIR
    xlsx = export_xlsx(scope, validated, findings, out / config.XLSX_NAME)
    pptx = export_pptx(scope, validated, findings, _read(run, config.CHART_INDEX_FILE, ChartIndex), out / config.PPTX_NAME)
    _out(f"{xlsx}\n{pptx}")


def cmd_summary(args: argparse.Namespace) -> None:
    run = Path(args.run)
    state = _require_next(run, 5)
    _out(
        review_summary(
            _read(run, config.SCOPE_FILE, Scope),
            _read(run, config.VALIDATED_FILE, Validated),
            _read(run, config.FINDINGS_FILE, Findings),
            _read(run, config.CHART_INDEX_FILE, ChartIndex),
            state.revisions,
        )
    )


def cmd_dump_source(args: argparse.Namespace) -> None:
    _out(dump_source(Path(args.path)))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mca", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create a run folder from a brief")
    init.add_argument("brief")
    init.add_argument("--runs-dir", default="runs")
    init.set_defaults(handler=cmd_init)
    for name, handler, text in (
        ("next", cmd_next, "print the next step number"),
        ("check", cmd_check, "step 3: run deterministic checks"),
        ("charts", cmd_charts, "step 4: render charts"),
        ("summary", cmd_summary, "step 5: print the review summary"),
        ("export", cmd_export, "step 6: write xlsx and pptx"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("run")
        sub.set_defaults(handler=handler)
    done = commands.add_parser("complete", help="validate a step's artifact and advance the run")
    done.add_argument("step", type=int, choices=sorted(STEP_VALIDATORS))
    done.add_argument("run")
    done.set_defaults(handler=cmd_complete)
    feedback = commands.add_parser("feedback", help="step 5: record the human decision")
    feedback.add_argument("run")
    feedback.add_argument("--decision", choices=("approved", "changes"), required=True)
    feedback.add_argument("--comment", action="append", default=[])
    feedback.add_argument("--comments-file", help="UTF-8 file, one comment per line")
    feedback.set_defaults(handler=cmd_feedback)
    dump = commands.add_parser("dump-source", help="print a csv/xlsx with cell references")
    dump.add_argument("path")
    dump.set_defaults(handler=cmd_dump_source)
    return parser


EXPECTED_ERRORS = (StateError, DecisionError, StepFailed, ValidationError, FileNotFoundError, ValueError)


def _force_utf8_streams() -> None:
    """Windows consoles default to cp1252, which garbles German umlauts in summaries and errors."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_streams()
    args = _parser().parse_args(argv)
    try:
        args.handler(args)
    except EXPECTED_ERRORS as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
