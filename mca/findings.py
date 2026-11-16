"""Step 4 guard: every Kernaussage cites known facts, and every number in it is a cited value."""

import re
from decimal import ROUND_HALF_UP, Decimal

from mca.config import YEAR_RANGE
from mca.contracts import Fact, Finding, Findings, Validated

NUMBER_TOKEN = re.compile(r"(?<![\w.,])\d[\d.,]*")
ENGLISH_FORMATS = (re.compile(r"^\d{1,3}(,\d{3})+(\.\d+)?$"), re.compile(r"^\d+(\.\d+)?$"))
GERMAN_FORMATS = (re.compile(r"^\d{1,3}(\.\d{3})+(,\d+)?$"), re.compile(r"^\d+(,\d+)?$"))
MATCH_TOLERANCE = 1e-9


def _reading(token: str, thousands: str, decimal: str) -> tuple[float, int]:
    plain = token.replace(thousands, "").replace(decimal, ".")
    decimals = len(plain.split(".")[1]) if "." in plain else 0
    return float(plain), decimals


def number_candidates(token: str) -> set[tuple[float, int]]:
    """All (value, decimal places) readings of a token in English or German notation."""
    readings: set[tuple[float, int]] = set()
    if any(p.match(token) for p in ENGLISH_FORMATS):
        readings = {*readings, _reading(token, ",", ".")}
    if any(p.match(token) for p in GERMAN_FORMATS):
        readings = {*readings, _reading(token, ".", ",")}
    return readings


def _round_half_up(value: float, decimals: int) -> float:
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _is_year(token: str) -> bool:
    return token.isdigit() and YEAR_RANGE[0] <= int(token) <= YEAR_RANGE[1]


def _matches(candidates: set[tuple[float, int]], facts: list[Fact]) -> bool:
    return any(
        abs(_round_half_up(fact.value, decimals) - value) < MATCH_TOLERANCE
        for value, decimals in candidates
        for fact in facts
    )


def _unbacked_numbers(finding: Finding, cited: list[Fact]) -> list[str]:
    text = f"{finding.headline}\n{finding.statement}"
    tokens = [t.rstrip(".,") for t in NUMBER_TOKEN.findall(text)]
    return [
        token
        for token in tokens
        if not _is_year(token) and not _matches(number_candidates(token), cited)
    ]


def _finding_errors(finding: Finding, validated: Validated, chart_ids: set[str]) -> list[str]:
    active = {f.id: f for f in validated.facts}
    unknown = [fid for fid in finding.fact_ids if fid not in active]
    cited = [active[fid] for fid in finding.fact_ids if fid in active]
    errors = [f"{finding.id}: cites unknown or dropped fact '{fid}'" for fid in unknown]
    if finding.chart_id is not None and finding.chart_id not in chart_ids:
        errors = [*errors, f"{finding.id}: unknown chart '{finding.chart_id}'"]
    return [
        *errors,
        *(f"{finding.id}: number '{n}' is not a value of a cited fact" for n in _unbacked_numbers(finding, cited)),
    ]


def findings_errors(findings: Findings, validated: Validated, chart_ids: set[str]) -> list[str]:
    return [error for finding in findings.findings for error in _finding_errors(finding, validated, chart_ids)]
