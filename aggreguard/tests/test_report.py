"""Tests for the report generator (Product A §5.3)."""

from eval.report import build_dataframe, to_html, to_markdown, write_report

ROWS = [
    {"suite": "workspace", "model": "local", "backend": "local", "defense": "none",
     "attack": "important_instructions", "clean_utility": 0.9, "asr": 0.45,
     "utility_under_attack": 0.7},
    {"suite": "workspace", "model": "local", "backend": "local", "defense": "aggreguard",
     "attack": "important_instructions", "clean_utility": 0.88, "asr": 0.12,
     "utility_under_attack": 0.68},
]


def test_dataframe_has_stable_columns():
    df = build_dataframe(ROWS)
    for col in ["suite", "defense", "asr", "fpr", "latency_p50_ms"]:
        assert col in df.columns
    assert len(df) == 2


def test_markdown_and_html_render():
    md = to_markdown(ROWS)
    assert "ASR" in md and "important_instructions" in md
    assert "lower is better" in md
    html = to_html(ROWS)
    assert "<table" in html and "aggreguard" in html


def test_write_report_creates_files(tmp_path):
    md_path, html_path = write_report(ROWS, outdir=tmp_path)
    assert md_path.exists() and html_path.exists()
    assert md_path.read_text(encoding="utf-8").startswith("# AggreGuard")
