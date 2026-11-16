"""End-to-end path through the `mca` CLI, with hand-written agent outputs standing in for the subagents."""

import json
import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook

from mca.cli import main

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
BRIEF = PROJECT_ROOT / "examples" / "brief.example.yaml"


def place(run: Path, name: str) -> None:
    shutil.copy(FIXTURES / name, run / name)


@pytest.fixture
def run(tmp_path, capsys) -> Path:
    assert main(["init", str(BRIEF), "--runs-dir", str(tmp_path)]) == 0
    return Path(capsys.readouterr().out.strip())


def through_step_two(run: Path) -> None:
    for step, name in ((1, "01_scope.json"), (2, "02_extracted.json")):
        place(run, name)
        assert main(["complete", str(step), str(run)]) == 0


def through_step_four(run: Path) -> None:
    through_step_two(run)
    assert main(["check", str(run)]) == 0
    place(run, "03_decisions.json")
    assert main(["complete", "3", str(run)]) == 0
    assert main(["charts", str(run)]) == 0
    place(run, "04_findings.json")
    assert main(["complete", "4", str(run)]) == 0


def test_init_when_called_creates_run_with_brief_and_state(run, capsys):
    assert (run / "brief.yaml").exists()
    assert main(["next", str(run)]) == 0
    assert capsys.readouterr().out.strip() == "1"


def test_full_run_when_approved_exports_xlsx_and_pptx(run, capsys):
    through_step_four(run)
    assert main(["summary", str(run)]) == 0
    summary = capsys.readouterr().out
    assert "K1" in summary and "Wettbewerber C / mitarbeiter" in summary
    assert main(["feedback", str(run), "--decision", "approved"]) == 0
    assert main(["export", str(run)]) == 0
    assert main(["complete", "6", str(run)]) == 0
    sheet = load_workbook(run / "out" / "analyse.xlsx")["Vergleich"]
    assert sheet["B2"].value == 120 and sheet["C2"].value == "S1 · B2"
    assert (run / "out" / "analyse.pptx").stat().st_size > 0
    capsys.readouterr()
    main(["next", str(run)])
    assert capsys.readouterr().out.strip() == "done"


def test_complete_when_out_of_order_fails(run, capsys):
    place(run, "02_extracted.json")
    assert main(["complete", "2", str(run)]) == 1
    assert "next step is 1" in capsys.readouterr().err


def test_complete_one_when_open_questions_fails(run, capsys):
    scope = json.loads((FIXTURES / "01_scope.json").read_text(encoding="utf-8"))
    (run / "01_scope.json").write_text(json.dumps({**scope, "open_questions": ["Welche Region?"]}), encoding="utf-8")
    assert main(["complete", "1", str(run)]) == 1
    assert "Welche Region?" in capsys.readouterr().err


def test_complete_one_when_contract_broken_fails(run, capsys):
    (run / "01_scope.json").write_text(json.dumps({"market": "x"}), encoding="utf-8")
    assert main(["complete", "1", str(run)]) == 1
    assert "competitors" in capsys.readouterr().err


def test_complete_two_when_unknown_competitor_fails(run, capsys):
    place(run, "01_scope.json")
    main(["complete", "1", str(run)])
    data = json.loads((FIXTURES / "02_extracted.json").read_text(encoding="utf-8"))
    data["facts"][0]["competitor"] = "Wettbewerber Z"
    (run / "02_extracted.json").write_text(json.dumps(data), encoding="utf-8")
    assert main(["complete", "2", str(run)]) == 1
    assert "Wettbewerber Z" in capsys.readouterr().err


def test_complete_three_when_conflict_unresolved_fails(run, capsys):
    through_step_two(run)
    main(["check", str(run)])
    (run / "03_decisions.json").write_text("{}", encoding="utf-8")
    assert main(["complete", "3", str(run)]) == 1
    assert "unresolved" in capsys.readouterr().err


def test_complete_four_when_number_invented_fails(run, capsys):
    through_step_two(run)
    main(["check", str(run)])
    place(run, "03_decisions.json")
    main(["complete", "3", str(run)])
    main(["charts", str(run)])
    data = json.loads((FIXTURES / "04_findings.json").read_text(encoding="utf-8"))
    data["findings"][0]["statement"] = "Wettbewerber A wächst um 12 % pro Jahr."
    (run / "04_findings.json").write_text(json.dumps(data), encoding="utf-8")
    assert main(["complete", "4", str(run)]) == 1
    assert "'12'" in capsys.readouterr().err


def test_feedback_when_changes_writes_comments_and_returns_to_step_three(run, capsys):
    through_step_four(run)
    assert main(["feedback", str(run), "--decision", "changes", "--comment", "F09 nicht verwerfen"]) == 0
    feedback = json.loads((run / "05_feedback.json").read_text(encoding="utf-8"))
    assert feedback == {"decision": "changes", "comments": ["F09 nicht verwerfen"], "revision": 1}
    capsys.readouterr()
    main(["next", str(run)])
    assert capsys.readouterr().out.strip() == "3"


def test_feedback_when_comments_file_reads_one_per_line(run):
    through_step_four(run)
    comments = run / "comments.txt"
    comments.write_text("A1 zu vage\n\nK1: \"Bericht\" bevorzugen\n", encoding="utf-8")
    assert main(["feedback", str(run), "--decision", "changes", "--comments-file", str(comments)]) == 0
    feedback = json.loads((run / "05_feedback.json").read_text(encoding="utf-8"))
    assert feedback["comments"] == ["A1 zu vage", 'K1: "Bericht" bevorzugen']


def test_feedback_when_changes_without_comment_fails(run, capsys):
    through_step_four(run)
    assert main(["feedback", str(run), "--decision", "changes"]) == 1
    assert "comment" in capsys.readouterr().err


def test_export_when_not_approved_fails(run, capsys):
    through_step_four(run)
    assert main(["export", str(run)]) == 1
    assert "approved" in capsys.readouterr().err


def test_check_when_step_two_not_done_fails(run, capsys):
    assert main(["check", str(run)]) == 1


def test_complete_six_when_files_missing_fails(run, capsys):
    through_step_four(run)
    main(["feedback", str(run), "--decision", "approved"])
    assert main(["complete", "6", str(run)]) == 1


def test_dump_source_when_csv_prints_locators(capsys):
    assert main(["dump-source", str(PROJECT_ROOT / "examples" / "sources" / "kennzahlen.csv")]) == 0
    assert "B2: 120" in capsys.readouterr().out


def test_dump_source_when_pdf_fails(tmp_path, capsys):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"%PDF")
    assert main(["dump-source", str(path)]) == 1
