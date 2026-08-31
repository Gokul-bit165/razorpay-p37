"""
Oracle rule builder.

Reads hidden GroundTruthCase fields to construct the oracle StructuredRule
for the R1 evaluation path.

BOUNDARY: This module is the ONLY module in p37.extraction that is allowed
to import GroundTruthCase or any hidden benchmark type.
It must NOT be imported by extractor.py or allocator.py.
This boundary is enforced by test_tier_b_safety.py.
"""
from __future__ import annotations

from p37.benchmark.models import GroundTruthCase

from .models import (
    AbstainReason,
    CommissionTreatment,
    NonlineAllocation,
    StructuredRule,
)

# Mapping from hidden benchmark strings to extraction enums
_NONLINE_MAP: dict[str, NonlineAllocation] = {
    "proportional":        NonlineAllocation.proportional,
    "shipping_funder":     NonlineAllocation.shipping_funder,
    "platform_absorbs":    NonlineAllocation.platform_absorbs,
    "platform_fee_funder": NonlineAllocation.platform_absorbs,  # canonical alias
    "discount_funder":     NonlineAllocation.discount_funder,
}

_COMMISSION_MAP: dict[str, CommissionTreatment] = {
    "proportional": CommissionTreatment.proportional,
    "full":         CommissionTreatment.full,
    "retained":     CommissionTreatment.retained,
}


def oracle_rule(case: GroundTruthCase) -> StructuredRule:
    """
    Build a StructuredRule from hidden GroundTruthCase fields.

    Used ONLY in the R1 evaluation path of experiments/run_tier_b.py.
    Must NOT be imported by extractor.py or allocator.py.

    The resulting StructuredRule includes funding_map (from the hidden case)
    which allows the predictor allocator to resolve nonline-funding cases.
    This is what closes the R0→R1 gap on A-type cases.
    """
    nl = _NONLINE_MAP.get(
        case.agreement.nonline_allocation_rule,
        NonlineAllocation.unknown,
    )

    # Commission treatment is stored per-transfer; all transfers share the same
    # value in the current benchmark.
    ct_raw = (
        case.transfers[0].true_commission_treatment
        if case.transfers
        else "proportional"
    )
    ct = _COMMISSION_MAP.get(ct_raw, CommissionTreatment.unknown)

    return StructuredRule(
        nonline_allocation=nl,
        commission_treatment=ct,
        recovery_order=tuple(case.agreement.recovery_order),
        funding_map=dict(case.funding_map),
        principal_bearer_verified=True,
        abstain=False,
        abstain_reason=AbstainReason.none,
        spans={},
    )
