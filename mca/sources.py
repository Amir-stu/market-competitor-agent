"""Dump tabular sources as text with cell references, so step 2 can cite exact locators."""

import csv
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

CSV_DELIMITERS = ";,\t"


def _dump_csv(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=CSV_DELIMITERS)
    rows = csv.reader(text.splitlines(), dialect)
    return [
        f"{get_column_letter(col)}{row_number}: {value}"
        for row_number, row in enumerate(rows, 1)
        for col, value in enumerate(row, 1)
        if value.strip()
    ]


def _dump_xlsx(path: Path) -> list[str]:
    workbook = load_workbook(path, data_only=True, read_only=True)
    lines = [
        f"{sheet.title}!{cell.coordinate}: {cell.value}"
        for sheet in workbook.worksheets
        for row in sheet.iter_rows()
        for cell in row
        if cell.value is not None and hasattr(cell, "coordinate")
    ]
    workbook.close()
    return lines


def dump_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        lines = _dump_csv(path)
    elif suffix in {".xlsx", ".xlsm"}:
        lines = _dump_xlsx(path)
    else:
        raise ValueError(f"{path.name}: not tabular; open it with the Read tool and cite page numbers")
    return "\n".join([f"# {path.name}", *lines])
