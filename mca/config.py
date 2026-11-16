"""Thresholds and artifact file names shared by every step."""

CONFLICT_THRESHOLD = 0.05
OUTLIER_IQR_FACTOR = 1.5
OUTLIER_MIN_VALUES = 4
MAX_REVISIONS = 3
YEAR_RANGE = (1900, 2100)

STATE_FILE = "state.json"
BRIEF_FILE = "brief.yaml"
SCOPE_FILE = "01_scope.json"
EXTRACTED_FILE = "02_extracted.json"
CHECKS_FILE = "03_checks.json"
DECISIONS_FILE = "03_decisions.json"
VALIDATED_FILE = "03_validated.json"
CHART_INDEX_FILE = "04_charts.json"
FINDINGS_FILE = "04_findings.json"
FEEDBACK_FILE = "05_feedback.json"
CHARTS_DIR = "charts"
OUTPUT_DIR = "out"
XLSX_NAME = "analyse.xlsx"
PPTX_NAME = "analyse.pptx"

CHART_BAR_COLOR = "#2f5d8a"
CHART_DPI = 150
