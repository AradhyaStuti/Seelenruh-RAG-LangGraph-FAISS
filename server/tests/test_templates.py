"""Tests for legal document template builders."""
import pytest

import templates as tpl


# ----- RTI -----

def test_rti_unknown_kind_raises():
    with pytest.raises(ValueError):
        tpl.build("not-a-template", {})


def test_rti_contains_section_6_reference():
    out = tpl.build("rti", {
        "applicantName": "Ada",
        "applicantAddress": "1 Demo Lane",
        "publicAuthority": "Ministry of Test",
        "informationSought": "list of widgets",
    })
    body = out["body"]
    assert "Section 6" in body
    assert "Right to Information Act, 2005" in body
    assert "Public Information Officer" in body


def test_rti_bpl_branch_changes_fee_clause():
    no_bpl = tpl.build("rti", {
        "applicantName": "X",
        "applicantAddress": "Y",
        "publicAuthority": "Z",
        "informationSought": "Q",
        "isBpl": False,
    })["body"]
    bpl = tpl.build("rti", {
        "applicantName": "X",
        "applicantAddress": "Y",
        "publicAuthority": "Z",
        "informationSought": "Q",
        "isBpl": True,
    })["body"]
    assert "Indian Postal Order" in no_bpl
    assert "BPL" in bpl or "poverty line" in bpl
    assert "Indian Postal Order" not in bpl


def test_rti_returns_notes_for_user():
    out = tpl.build("rti", {
        "applicantName": "A", "applicantAddress": "B",
        "publicAuthority": "C", "informationSought": "D",
    })
    assert isinstance(out["notes"], list) and len(out["notes"]) >= 3


# ----- Consumer complaint -----

def test_consumer_picks_district_commission_for_small_claim():
    out = tpl.build("consumer_complaint", {
        "complainantName": "A", "complainantAddress": "B",
        "opposingParty": "Seller", "grievance": "defect",
        "amountPaid": "10000",
    })
    assert "DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION" in out["body"]


def test_consumer_picks_state_commission_for_medium_claim():
    out = tpl.build("consumer_complaint", {
        "complainantName": "A", "complainantAddress": "B",
        "opposingParty": "Seller", "grievance": "defect",
        "amountPaid": "6000000",  # ₹60 lakh — above district ceiling
    })
    assert "STATE CONSUMER DISPUTES REDRESSAL COMMISSION" in out["body"]


def test_consumer_picks_national_commission_for_large_claim():
    out = tpl.build("consumer_complaint", {
        "complainantName": "A", "complainantAddress": "B",
        "opposingParty": "Seller", "grievance": "defect",
        "amountPaid": "300000000",  # ₹30 crore
    })
    assert "NATIONAL CONSUMER DISPUTES REDRESSAL COMMISSION" in out["body"]


def test_consumer_cites_act_and_section_35():
    out = tpl.build("consumer_complaint", {
        "complainantName": "A", "complainantAddress": "B",
        "opposingParty": "Seller", "grievance": "defect",
        "amountPaid": "5000",
    })
    body = out["body"]
    assert "Section 35" in body
    assert "Consumer Protection Act, 2019" in body


# ----- Rent notice -----

def test_rent_notice_cites_section_106_tpa():
    out = tpl.build("rent_notice", {
        "senderName": "L", "senderAddress": "A1",
        "tenantName": "T", "propertyAddress": "A2",
    })
    body = out["body"]
    assert "Section 106" in body
    assert "Transfer of Property Act, 1882" in body


def test_rent_notice_default_period_is_15_days():
    out = tpl.build("rent_notice", {
        "senderName": "L", "senderAddress": "A1",
        "tenantName": "T", "propertyAddress": "A2",
    })
    assert "15 days" in out["body"] or "15-day" in out["body"]
