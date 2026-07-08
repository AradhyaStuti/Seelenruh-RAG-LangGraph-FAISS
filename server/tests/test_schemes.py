"""Tests for the rule-based scheme matcher in `server/schemes.py`.

These exist because the rule predicates are easy to subtly break (a flipped
`is` comparison, a missing state-name alias) and the production UI gives
no compile-time guarantee. Plain unit tests catch the obvious regressions."""
import schemes


def _ids(matches):
    return {m["id"] for m in matches}


def test_no_input_returns_central_universal_schemes():
    """An empty applicant should still match the no-filter central programs."""
    out = schemes.match({})
    ids = _ids(out)
    # PMSBY / PMJJBY / APY / Vishwakarma have no constraints we can fail without
    # state OR demographic info, so they should pass through.
    assert "pmsby" in ids
    assert "pmjjby" in ids
    assert "apy" in ids


def test_karnataka_woman_matches_gruha_lakshmi():
    out = schemes.match({"state": "Karnataka", "age": 35, "gender": "female", "incomeAnnual": 200000})
    ids = _ids(out)
    assert "ka-gruha-lakshmi" in ids
    # State-specific schemes from other states must NOT appear.
    assert "mh-ladki-bahin" not in ids
    assert "wb-lakshmir-bhandar" not in ids


def test_male_does_not_match_women_only_schemes():
    out = schemes.match({"state": "Karnataka", "age": 30, "gender": "male"})
    ids = _ids(out)
    assert "ka-gruha-lakshmi" not in ids
    assert "pmuy" not in ids


def test_non_farmer_does_not_match_pmkisan():
    out = schemes.match({"isFarmer": False, "age": 30})
    assert "pmkisan" not in _ids(out)


def test_farmer_matches_pmkisan():
    out = schemes.match({"isFarmer": True, "age": 30})
    assert "pmkisan" in _ids(out)


def test_student_matches_nsp():
    out = schemes.match({"isStudent": True, "age": 20})
    assert "nsp" in _ids(out)


def test_age_above_pension_window_drops_apy():
    out = schemes.match({"age": 55})  # APY enrolment window is 18-40
    assert "apy" not in _ids(out)


def test_low_income_unlocks_subsidy_schemes():
    out = schemes.match({"incomeAnnual": 50000, "age": 25, "gender": "female"})
    ids = _ids(out)
    assert "pmjay" in ids
    assert "pmuy" in ids


def test_high_income_filters_out_subsidy_schemes():
    out = schemes.match({"incomeAnnual": 1500000, "age": 25, "gender": "female"})
    ids = _ids(out)
    # PM-JAY threshold is ₹2.5 LPA; 15 LPA must NOT match.
    assert "pmjay" not in ids
    assert "pmuy" not in ids


def test_state_alias_works():
    """State predicates accept short codes (e.g. 'mh' for Maharashtra)."""
    out_full = schemes.match({"state": "Maharashtra", "age": 30, "gender": "female", "incomeAnnual": 150000})
    out_alias = schemes.match({"state": "mh", "age": 30, "gender": "female", "incomeAnnual": 150000})
    assert "mh-ladki-bahin" in _ids(out_full)
    assert "mh-ladki-bahin" in _ids(out_alias)


def test_every_scheme_has_required_metadata():
    for s in schemes.SCHEMES:
        for key in ("id", "name", "summary", "link", "level", "reasonIf"):
            assert key in s, f"scheme {s.get('id','?')} missing {key}"
        assert s["level"] in ("central", "state")
        assert s["link"].startswith("http")
