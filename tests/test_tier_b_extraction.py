"""
Tests for Tier-B deterministic rule extraction.

Covers:
- Canonical commission phrases extraction + source spans
- Principal-bearer clause verification
- Canonical nonline phrases extraction
- Recovery order parsing
- Source span exact substring validation
- ExtractionError on invalid span
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from p37.extraction.extractor import extract
from p37.extraction.models import (
    AbstainReason,
    CommissionTreatment,
    ExtractionError,
    NonlineAllocation,
    SourceSpan,
    StructuredRule,
)
from p37.extraction.tier_b_dataset import SAFETY_SET, TIER_B_CLEAN


def test_tier_b_clean_clauses_extraction():
    """All clean Tier-B clauses must extract expected values with valid source spans."""
    for clause in TIER_B_CLEAN:
        rule = extract(clause.clause_text)
        assert not rule.abstain, f"Clause {clause.clause_id} unexpectedly abstained"
        assert rule.abstain_reason == AbstainReason.none

        ts = clause.true_structure
        if ts.nonline_allocation != NonlineAllocation.unknown:
            assert (
                rule.nonline_allocation == ts.nonline_allocation
            ), f"Nonline mismatch for {clause.clause_id}: got {rule.nonline_allocation}, expected {ts.nonline_allocation}"

        if ts.commission_treatment != CommissionTreatment.unknown:
            assert (
                rule.commission_treatment == ts.commission_treatment
            ), f"Commission mismatch for {clause.clause_id}: got {rule.commission_treatment}, expected {ts.commission_treatment}"

        # Verify all spans validate against the text
        for field_name, span in rule.spans.items():
            assert span.validate(
                clause.clause_text
            ), f"Invalid span for field '{field_name}' in {clause.clause_id}: {span}"


def test_principal_bearer_verified():
    """Standard 4-line principal bearer clause should be verified."""
    text = (
        "Refund allocation agreement:\n"
        "Goods: refund bears with the fulfilling vendor.\n"
        "Shipping: refund bears with the shipping-funding party.\n"
        "Platform fee: refund bears with the platform.\n"
        "Discount adjustments: refund bears with the party that funded the discount.\n"
        "Non-line refund rule: proportional.\n"
        "Recovery order: acc_1 then acc_2."
    )
    rule = extract(text)
    assert rule.principal_bearer_verified is True


def test_principal_bearer_unverified():
    """Missing any required principal line sets principal_bearer_verified to False."""
    text = (
        "Refund allocation agreement:\n"
        "Goods: refund bears with the fulfilling vendor.\n"
        "Non-line refund rule: proportional.\n"
        "Recovery order: acc_1 then acc_2."
    )
    rule = extract(text)
    assert rule.principal_bearer_verified is False


def test_recovery_order_extraction():
    """Recovery order parsing handles multiple accounts properly."""
    text = (
        "Refund allocation agreement:\n"
        "Recovery order: acc_alpha then acc_beta then acc_gamma."
    )
    rule = extract(text)
    assert rule.recovery_order == ("acc_alpha", "acc_beta", "acc_gamma")
    assert "recovery_order" in rule.spans
    assert rule.spans["recovery_order"].validate(text)


def test_source_span_validation_logic():
    """SourceSpan.validate strictly verifies exact slice bounds."""
    text = "Non-line refund rule: shipping funder."
    span_valid = SourceSpan("nonline_allocation", text, 0, len(text))
    assert span_valid.validate(text) is True

    span_wrong_start = SourceSpan("nonline_allocation", text, 1, len(text))
    assert span_wrong_start.validate(text) is False

    span_wrong_text = SourceSpan("nonline_allocation", "wrong text", 0, len("wrong text"))
    assert span_wrong_text.validate(text) is False

    span_out_of_bounds = SourceSpan("nonline_allocation", text, 0, len(text) + 10)
    assert span_out_of_bounds.validate(text) is False


def test_safety_set_clauses():
    """Safety set clauses must exhibit expected abstention or unknown values."""
    for clause in SAFETY_SET:
        rule = extract(clause.clause_text)
        if clause.expected_abstain:
            assert rule.abstain is True, f"Expected {clause.clause_id} to abstain"
        else:
            assert rule.abstain is False, f"Expected {clause.clause_id} NOT to abstain"
            if clause.expected_nonline == NonlineAllocation.unknown:
                assert (
                    rule.nonline_allocation == NonlineAllocation.unknown
                ), f"Hallucinated nonline for {clause.clause_id}: {rule.nonline_allocation}"
            elif clause.expected_nonline is not None:
                assert rule.nonline_allocation == clause.expected_nonline

            if clause.expected_commission == CommissionTreatment.unknown:
                assert (
                    rule.commission_treatment == CommissionTreatment.unknown
                ), f"Hallucinated commission for {clause.clause_id}: {rule.commission_treatment}"
            elif clause.expected_commission is not None:
                assert rule.commission_treatment == clause.expected_commission
