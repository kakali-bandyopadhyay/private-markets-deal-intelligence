from dealintel import dashboard
from dealintel.data import load


def test_dashboard_shows_labels_the_human_decision_and_the_blocked_contrast():
    html = dashboard.build(load())
    assert "Synthetic companies, documents and figures" in html
    assert "Human IC decision" in html and "PROCEED" in html
    assert "Project Osier is blocked at the gate" in html
    assert "not investment-grade" in html.lower()
