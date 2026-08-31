"""
Tier-B clause dataset for deterministic extraction evaluation.

Two strictly separate collections:

  TIER_B_CLEAN   — canonical, unambiguous clauses.  Used for extraction accuracy.
  SAFETY_SET     — adversarial clauses.  Used for hallucination / abstention checks.

Scores from these two collections must NEVER be merged.

Each TierBClause carries a ``mapped_case_id`` that references the specific
validation case (seed=2701) whose structure the clause represents.  This
makes the extraction-to-allocation mapping concrete and auditable.

Case ID index (seed=2701, 20 cases per type, CASE_TYPES generation order):
  D1_single_line_return          case_000000 – case_000019
  D2_multi_line_clean            case_000020 – case_000039
  D3_full_refund                 case_000040 – case_000059
  A1_shipping_fee                case_000060 – case_000079
  A2_goodwill_credit             case_000080 – case_000099
  A3_discount_funded             case_000100 – case_000119
  A4_platform_fee_only           case_000120 – case_000139
  A5_proportional_cancellation   case_000140 – case_000159
  C1_commission_retained         case_000160 – case_000179
  C2_commission_full_return      case_000180 – case_000199
  B1_rounding                    case_000200 – case_000219
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import CommissionTreatment, NonlineAllocation


@dataclass(frozen=True)
class TrueStructure:
    """
    Ground-truth rule structure for a Tier-B clause.

    HIDDEN from the predictor — accessed only by the evaluator.
    """

    nonline_allocation:   NonlineAllocation
    commission_treatment: CommissionTreatment
    # recovery_order is canonical in all Tier-B clean cases (same as transfer order)


@dataclass(frozen=True)
class TierBClause:
    """
    A Tier-B extraction test case.

    Predictor receives: clause_text only.
    Evaluator accesses: true_structure, mapped_case_id.

    mapped_case_id: specific validation case ID (seed=2701) whose observable
        structure corresponds to this clause.  Used for end-to-end allocation
        evaluation and audit traceability.
    """

    clause_id:       str
    true_structure:  TrueStructure   # HIDDEN from predictor
    clause_text:     str             # predictor-visible only
    tier:            Literal["B"] = "B"
    render_seed:     int = 0
    mapped_case_id:  str | None = None


# ── Tier-B Clean Set ──────────────────────────────────────────────────────────

TIER_B_CLEAN: tuple[TierBClause, ...] = (
    # ── Commission treatment ─────────────────────────────────────────────────
    TierBClause(
        clause_id="tb_comm_retained_01",
        true_structure=TrueStructure(
            NonlineAllocation.proportional, CommissionTreatment.retained
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Commission is retained on refunds.\n"
            "Recovery order: acc_00160_0 then acc_00160_1."
        ),
        render_seed=1,
        mapped_case_id="case_000160",  # first C1_commission_retained case
    ),
    TierBClause(
        clause_id="tb_comm_retained_02",
        true_structure=TrueStructure(
            NonlineAllocation.proportional, CommissionTreatment.retained
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Commission retained.\n"
            "Recovery order: acc_00161_0 then acc_00161_1."
        ),
        render_seed=2,
        mapped_case_id="case_000161",  # second C1_commission_retained case
    ),
    TierBClause(
        clause_id="tb_comm_proportional_01",
        true_structure=TrueStructure(
            NonlineAllocation.proportional, CommissionTreatment.proportional
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Commission is returned proportionally.\n"
            "Recovery order: acc_00000_0 then acc_00000_1."
        ),
        render_seed=3,
        mapped_case_id="case_000000",  # first D1_single_line_return case
    ),
    TierBClause(
        clause_id="tb_comm_full_01",
        true_structure=TrueStructure(
            NonlineAllocation.proportional, CommissionTreatment.full
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Commission is returned in full.\n"
            "Recovery order: acc_00180_0 then acc_00180_1."
        ),
        render_seed=4,
        mapped_case_id="case_000180",  # first C2_commission_full_return case
    ),
    TierBClause(
        clause_id="tb_comm_full_02",
        true_structure=TrueStructure(
            NonlineAllocation.proportional, CommissionTreatment.full
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Full commission returned on refunds.\n"
            "Recovery order: acc_00181_0 then acc_00181_1."
        ),
        render_seed=5,
        mapped_case_id="case_000181",  # second C2_commission_full_return case
    ),
    # ── Nonline allocation ───────────────────────────────────────────────────
    TierBClause(
        clause_id="tb_nonline_proportional_01",
        true_structure=TrueStructure(
            NonlineAllocation.proportional, CommissionTreatment.unknown
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Recovery order: acc_00140_0 then acc_00140_1."
        ),
        render_seed=6,
        mapped_case_id="case_000140",  # first A5_proportional_cancellation case
    ),
    TierBClause(
        clause_id="tb_nonline_shipping_01",
        true_structure=TrueStructure(
            NonlineAllocation.shipping_funder, CommissionTreatment.unknown
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: shipping funder.\n"
            "Recovery order: acc_00060_0 then acc_00060_1."
        ),
        render_seed=7,
        mapped_case_id="case_000060",  # first A1_shipping_fee case
    ),
    TierBClause(
        clause_id="tb_nonline_platform_absorbs_01",
        true_structure=TrueStructure(
            NonlineAllocation.platform_absorbs, CommissionTreatment.unknown
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: platform absorbs.\n"
            "Recovery order: acc_00080_0 then acc_00080_1."
        ),
        render_seed=8,
        mapped_case_id="case_000080",  # first A2_goodwill_credit case
    ),
    TierBClause(
        clause_id="tb_nonline_platform_fee_01",
        true_structure=TrueStructure(
            NonlineAllocation.platform_absorbs, CommissionTreatment.unknown
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: platform fee funder.\n"
            "Recovery order: acc_00120_0 then acc_00120_1."
        ),
        render_seed=9,
        mapped_case_id="case_000120",  # first A4_platform_fee_only case
    ),
    TierBClause(
        clause_id="tb_nonline_discount_01",
        true_structure=TrueStructure(
            NonlineAllocation.discount_funder, CommissionTreatment.unknown
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: discount funder.\n"
            "Recovery order: acc_00100_0 then acc_00100_1."
        ),
        render_seed=10,
        mapped_case_id="case_000100",  # first A3_discount_funded case
    ),
    # ── Recovery order ───────────────────────────────────────────────────────
    TierBClause(
        clause_id="tb_recovery_2acct_01",
        true_structure=TrueStructure(
            NonlineAllocation.proportional, CommissionTreatment.unknown
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Recovery order: acc_00000_0 then acc_00000_1."
        ),
        render_seed=11,
        mapped_case_id="case_000000",  # first D1_single_line_return (2-account)
    ),
    TierBClause(
        clause_id="tb_recovery_3acct_01",
        true_structure=TrueStructure(
            NonlineAllocation.proportional, CommissionTreatment.unknown
        ),
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Recovery order: acc_00020_0 then acc_00020_1 then acc_00020_2."
        ),
        render_seed=12,
        mapped_case_id="case_000020",  # first D2_multi_line_clean case
    ),
)


# ── Safety Set ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SafetyClause:
    """
    Adversarial clause for hallucination / abstention checks.

    Never mixed into Tier-B accuracy metrics.
    """

    clause_id:              str
    clause_text:            str
    expected_abstain:       bool
    expected_commission:    CommissionTreatment  # expected extracted value
    expected_nonline:       NonlineAllocation    # expected extracted value
    description:            str


SAFETY_SET: tuple[SafetyClause, ...] = (
    SafetyClause(
        clause_id="ts_irrelevant_01",
        clause_text=(
            "This agreement governs intellectual property licensing between the parties. "
            "All disputes shall be resolved by arbitration in the jurisdiction of Mumbai. "
            "Neither party shall be liable for consequential damages."
        ),
        expected_abstain=False,
        expected_commission=CommissionTreatment.unknown,
        expected_nonline=NonlineAllocation.unknown,
        description=(
            "Irrelevant legal text. All extraction fields should be unknown. "
            "Must not hallucinate any rule value."
        ),
    ),
    SafetyClause(
        clause_id="ts_conflict_comm_01",
        clause_text=(
            "Refund allocation agreement:\n"
            "Non-line refund rule: proportional.\n"
            "Commission is retained on refunds.\n"
            "Commission is returned in full.\n"
            "Recovery order: acc_test_0 then acc_test_1."
        ),
        expected_abstain=True,
        expected_commission=CommissionTreatment.unknown,
        expected_nonline=NonlineAllocation.unknown,
        description=(
            "Two contradictory commission clauses (retained + full). "
            "Must abstain with reason=conflicting."
        ),
    ),
    SafetyClause(
        clause_id="ts_unsupported_phrasing_01",
        clause_text=(
            "Refund allocation agreement:\n"
            "Non-line refund rule: proportional.\n"
            "Commission is negotiated on a per-dispute basis.\n"
            "Recovery order: acc_test_0 then acc_test_1."
        ),
        expected_abstain=False,
        expected_commission=CommissionTreatment.unknown,
        expected_nonline=NonlineAllocation.proportional,
        description=(
            "Unsupported commission phrasing. Commission should be unknown, "
            "not abstain. Nonline should still be extracted correctly."
        ),
    ),
    SafetyClause(
        clause_id="ts_missing_nonline_01",
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Commission is returned proportionally.\n"
            "Recovery order: acc_test_0 then acc_test_1."
        ),
        expected_abstain=False,
        expected_commission=CommissionTreatment.proportional,
        expected_nonline=NonlineAllocation.unknown,
        description=(
            "Agreement without nonline clause. Nonline should be unknown "
            "(not abstain). Commission should still be extracted."
        ),
    ),
    SafetyClause(
        clause_id="ts_same_value_two_patterns_01",
        clause_text=(
            "Refund allocation agreement:\n"
            "Non-line refund rule: proportional.\n"
            "Commission is retained on refunds.\n"
            "Commission retained.\n"
            "Recovery order: acc_test_0 then acc_test_1."
        ),
        expected_abstain=False,
        expected_commission=CommissionTreatment.retained,
        expected_nonline=NonlineAllocation.proportional,
        description=(
            "Two matches for the same commission value (retained). "
            "Same value is NOT a conflict — must extract retained, not abstain."
        ),
    ),
)
