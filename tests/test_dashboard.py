from dealintel import dashboard
from dealintel.data import load


def test_dashboard_shows_labels_the_human_decision_and_the_blocked_contrast():
    html = dashboard.build(load())
    assert "Synthetic companies, documents and figures" in html
    assert "Human IC decision" in html and "PROCEED" in html
    assert "Project Osier is blocked at the gate" in html
    assert "not investment-grade" in html.lower()


def test_dashboard_reports_every_run_separately():
    html = dashboard.build(load())
    for run in ("Held-out run 1", "Held-out run 2", "Held-out run 3", "Model mode, development set"):
        assert run in html
    assert "4/10" in html and "7/10" in html


def test_committed_dashboard_is_not_stale():
    """docs/index.html must be regenerated (python -m dealintel dashboard) whenever its inputs change."""
    from dealintel.data import ROOT
    on_disk = (ROOT / "docs" / "index.html").read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert on_disk == dashboard.build(load()), "docs/index.html is stale: run python -m dealintel dashboard"
