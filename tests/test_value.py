from dealintel import value


def test_range_is_ordered_and_every_number_shows_its_calculation():
    e = value.estimate()
    assert e["per_deal"]["low"] < e["per_deal"]["base"] < e["per_deal"]["high"]
    assert all("min / 60" in r[c]["calc"] for r in e["rows"] for c in value.CASES)
    assert e["per_year"]["base"] == round(e["per_deal"]["base"] * e["deals_per_year"])


def test_value_is_labelled_and_paired_with_quality_and_adoption_measures():
    e = value.estimate()
    assert "not measured savings" in e["label"].lower()
    assert {m["kind"] for m in e["measures"]} == {"value", "quality", "adoption"}
