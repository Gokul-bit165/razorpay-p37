"""
Tier-C clause dataset for natural-language extraction boundary evaluation.

PURPOSE: Qualitative failure-mode categorisation, NOT a statistical benchmark.
n=15 clauses are designed to categorise where deterministic regex extraction
breaks down, defining the linguistic boundary where LLMs become necessary.

IMPORTANT: Do NOT compute or report a bare "Tier-C accuracy %" from this set.
The meaningful output is per-category failure counts, which map to specific
linguistic failure modes.  See experiments/run_tier_c.py.

Categories (TierCFailureCategory):
  canonical_succeeds      - Regex handles this correctly (control cases).
  synonym_variation       - Phrasing synonym for a known concept; regex fails.
  passive_voice           - Passive / inverted sentence structure; regex fails.
  negation                - Negated or conditional statement; regex fails.
  multi_clause_precedence - Rule in multiple clauses with precedence logic.
  amendment_conflict      - Amendment clause changes an earlier base clause.

Each TierCClause carries:
  - clause_text:               The agreement text shown to the predictor.
  - failure_category:          Expected extraction outcome category.
  - expected_nonline:          What the regex extractor will return.
  - canonical_equivalent:      The Tier-B canonical form of the same rule.
  - regex_expected_to_succeed: True if regex should extract correctly.
  - description:               Human-readable note on what makes this clause hard.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import CommissionTreatment, NonlineAllocation, TierCFailureCategory


@dataclass(frozen=True)
class TierCClause:
    """
    A Tier-C natural-language extraction test clause.

    Predictor receives: clause_text only.
    Evaluator uses: failure_category, expected_nonline, regex_expected_to_succeed.
    """

    clause_id:                 str
    clause_text:               str
    failure_category:          TierCFailureCategory
    expected_nonline:          NonlineAllocation   # what regex extractor returns
    expected_commission:       CommissionTreatment  # what regex extractor returns
    canonical_equivalent:      str                 # Tier-B phrase this maps to semantically
    regex_expected_to_succeed: bool                # False = expected regex failure
    description:               str


TIER_C_CLAUSES: tuple[TierCClause, ...] = (

    # ── Control: canonical succeeds (2 cases) ─────────────────────────────────

    TierCClause(
        clause_id="tc_ctrl_01",
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: proportional.\n"
            "Commission is retained on refunds.\n"
            "Recovery order: acc_ctrl_0 then acc_ctrl_1."
        ),
        failure_category=TierCFailureCategory.canonical_succeeds,
        expected_nonline=NonlineAllocation.proportional,
        expected_commission=CommissionTreatment.retained,
        canonical_equivalent="Non-line refund rule: proportional.",
        regex_expected_to_succeed=True,
        description=(
            "Control: fully canonical Tier-B clause. "
            "Regex must extract correctly. Used to verify the extractor is still working."
        ),
    ),

    TierCClause(
        clause_id="tc_ctrl_02",
        clause_text=(
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            "Non-line refund rule: shipping funder.\n"
            "Commission retained.\n"
            "Recovery order: acc_ctrl_0 then acc_ctrl_1."
        ),
        failure_category=TierCFailureCategory.canonical_succeeds,
        expected_nonline=NonlineAllocation.shipping_funder,
        expected_commission=CommissionTreatment.retained,
        canonical_equivalent="Non-line refund rule: shipping funder.",
        regex_expected_to_succeed=True,
        description=(
            "Control: canonical shipping funder + commission retained. "
            "Regex must extract correctly."
        ),
    ),

    # ── Synonym variation (4 cases) ───────────────────────────────────────────

    TierCClause(
        clause_id="tc_syn_01",
        clause_text=(
            "Refund policy:\n"
            "For cancellations, the carrier settlement pool bears the loss.\n"
            "Merchant commission is not returned on refunds.\n"
            "Repayment sequence: acc_syn_0 prior to acc_syn_1."
        ),
        failure_category=TierCFailureCategory.synonym_variation,
        expected_nonline=NonlineAllocation.unknown,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: shipping funder.",
        regex_expected_to_succeed=False,
        description=(
            "'carrier settlement pool' is a synonym for shipping_funder. "
            "'Merchant commission is not returned' means retained. "
            "'Repayment sequence: X prior to Y' is a synonym for recovery order. "
            "All three fields fail to extract."
        ),
    ),

    TierCClause(
        clause_id="tc_syn_02",
        clause_text=(
            "Refund terms:\n"
            "Non-line losses are absorbed by the marketplace operator.\n"
            "Platform service fees are waived on reversals.\n"
            "Repayment priority: acc_syn_0, then acc_syn_1."
        ),
        failure_category=TierCFailureCategory.synonym_variation,
        expected_nonline=NonlineAllocation.unknown,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: platform absorbs.",
        regex_expected_to_succeed=False,
        description=(
            "'marketplace operator absorbs' is a synonym for platform_absorbs. "
            "'Platform service fees are waived on reversals' maps to commission returned. "
            "Regex fails on non-canonical phrasing."
        ),
    ),

    TierCClause(
        clause_id="tc_syn_03",
        clause_text=(
            "Refund allocation:\n"
            "Promotional concession losses fall on the promotional fund account.\n"
            "Earned commissions remain with Razorpay upon refund.\n"
            "Settlement order: acc_syn_0 before acc_syn_1."
        ),
        failure_category=TierCFailureCategory.synonym_variation,
        expected_nonline=NonlineAllocation.unknown,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: discount funder.",
        regex_expected_to_succeed=False,
        description=(
            "'Promotional concession losses' maps to discount_funder. "
            "'Earned commissions remain' maps to commission retained. "
            "Neither phrase matches canonical patterns."
        ),
    ),

    TierCClause(
        clause_id="tc_syn_04",
        clause_text=(
            "Cancellation policy:\n"
            "Any non-order-line refund is shared across all linked accounts "
            "in proportion to their original transfer amounts.\n"
            "Commission is returned in proportion to the refund.\n"
            "Accounts are settled starting with acc_syn_0, proceeding to acc_syn_1."
        ),
        failure_category=TierCFailureCategory.synonym_variation,
        expected_nonline=NonlineAllocation.unknown,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: proportional.",
        regex_expected_to_succeed=False,
        description=(
            "'shared across all linked accounts in proportion to their original transfer amounts' "
            "semantically means proportional but does not match 'proportional' keyword. "
            "'Commission is returned in proportion' is close but not exact match."
        ),
    ),

    # ── Passive voice (2 cases) ───────────────────────────────────────────────

    TierCClause(
        clause_id="tc_passive_01",
        clause_text=(
            "Refund obligations:\n"
            "Non-line refunds shall be borne by the party providing the shipping service.\n"
            "The commission component will be withheld by the platform on all reversals.\n"
            "Settlement: acc_passive_0, followed by acc_passive_1."
        ),
        failure_category=TierCFailureCategory.passive_voice,
        expected_nonline=NonlineAllocation.unknown,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: shipping funder.",
        regex_expected_to_succeed=False,
        description=(
            "Passive voice: 'shall be borne by' does not match active 'shipping funder'. "
            "'will be withheld' maps to retained but doesn't match commission patterns. "
            "Both fields fail."
        ),
    ),

    TierCClause(
        clause_id="tc_passive_02",
        clause_text=(
            "Platform agreement:\n"
            "All non-line losses are to be absorbed by the platform partner. "
            "Commission amounts will be reimbursed proportionally upon refund."
        ),
        failure_category=TierCFailureCategory.passive_voice,
        expected_nonline=NonlineAllocation.unknown,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: platform absorbs.",
        regex_expected_to_succeed=False,
        description=(
            "'are to be absorbed by the platform partner' is passive form of platform_absorbs. "
            "'will be reimbursed proportionally' maps to commission proportional. "
            "Neither matches canonical patterns."
        ),
    ),

    # ── Negation (2 cases) ────────────────────────────────────────────────────

    TierCClause(
        clause_id="tc_neg_01",
        clause_text=(
            "Refund policy:\n"
            "Non-line amounts are not distributed proportionally. "
            "The shipping partner bears the cost of all non-line refunds. "
            "Commission will not be returned to the merchant on any refund."
        ),
        failure_category=TierCFailureCategory.negation,
        expected_nonline=NonlineAllocation.unknown,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: shipping funder.",
        regex_expected_to_succeed=False,
        description=(
            "Negation + synonym: 'The shipping partner bears the cost' semantically means "
            "shipping_funder, but 'shipping partner' is not in the canonical vocab. "
            "Regex returns unknown for nonline. "
            "'Commission will not be returned' maps to retained semantically but "
            "doesn't match any commission pattern — both fields are unknown."
        ),
    ),

    TierCClause(
        clause_id="tc_neg_02",
        clause_text=(
            "Terms of service amendment:\n"
            "Non-line refund rule: proportional.\n"
            "Note: This clause does not apply when the refund reason is 'goodwill'.\n"
            "Commission is retained on refunds."
        ),
        failure_category=TierCFailureCategory.negation,
        expected_nonline=NonlineAllocation.proportional,
        expected_commission=CommissionTreatment.retained,
        canonical_equivalent="Non-line refund rule: proportional.",
        regex_expected_to_succeed=True,
        description=(
            "Conditional negation ('does not apply when') modifies scope of the rule "
            "but regex extracts the canonical phrase correctly without understanding "
            "the condition. Regex succeeds syntactically but is semantically incomplete. "
            "Marks as negation category to document the semantic limitation."
        ),
    ),

    # ── Multi-clause precedence (2 cases) ─────────────────────────────────────

    TierCClause(
        clause_id="tc_prec_01",
        clause_text=(
            "Base agreement (Section 4.1):\n"
            "Non-line refund rule: proportional.\n"
            "Commission is retained on refunds.\n"
            "\n"
            "Special terms (Section 4.2, applies to shipping-related cancellations):\n"
            "For refunds where reason is shipping, the shipping account bears the loss.\n"
            "Commission is returned in full for shipping refunds."
        ),
        failure_category=TierCFailureCategory.multi_clause_precedence,
        expected_nonline=NonlineAllocation.proportional,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: shipping funder.",
        regex_expected_to_succeed=False,
        description=(
            "Two sections with different rules for different conditions. "
            "Regex extracts the first nonline match (proportional) from Section 4.1 "
            "but Section 4.2 overrides for shipping refunds. "
            "Commission conflict: retained (4.1) + full (4.2) → regex abstains. "
            "Correct extraction requires understanding precedence scope."
        ),
    ),

    TierCClause(
        clause_id="tc_prec_02",
        clause_text=(
            "Master agreement:\n"
            "Non-line refund rule: discount funder.\n"
            "Commission is returned proportionally.\n"
            "\n"
            "Supplementary clause (overrides Master for platform fee transactions):\n"
            "Non-line refund rule: platform absorbs.\n"
            "Commission is retained on refunds."
        ),
        failure_category=TierCFailureCategory.multi_clause_precedence,
        expected_nonline=NonlineAllocation.discount_funder,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: platform absorbs.",
        regex_expected_to_succeed=False,
        description=(
            "Master + supplementary clause with scoped override. "
            "Regex returns first nonline match (discount_funder) instead of platform_absorbs. "
            "Commission conflict: proportional + retained → regex abstains correctly "
            "but for the wrong reason (it can't detect the scoped override)."
        ),
    ),

    # ── Amendment conflict (3 cases) ──────────────────────────────────────────

    TierCClause(
        clause_id="tc_amend_01",
        clause_text=(
            "Original agreement:\n"
            "Non-line refund rule: proportional.\n"
            "Commission is returned in full.\n"
            "\n"
            "AMENDMENT: (effective 2026-07-01)\n"
            "Non-line refund rule: shipping funder.\n"
            "Commission is retained on refunds."
        ),
        failure_category=TierCFailureCategory.amendment_conflict,
        expected_nonline=NonlineAllocation.proportional,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: shipping funder.",
        regex_expected_to_succeed=False,
        description=(
            "Amendment overrides original with different nonline rule and commission. "
            "Regex extracts first nonline match (proportional) ignoring amendment override. "
            "Commission conflict: full (original) + retained (amendment) → abstain. "
            "Correct answer: shipping_funder + retained (amendment wins)."
        ),
    ),

    TierCClause(
        clause_id="tc_amend_02",
        clause_text=(
            "Platform agreement:\n"
            "Non-line refund rule: platform absorbs.\n"
            "Commission is returned proportionally.\n"
            "Recovery order: acc_orig_0 then acc_orig_1.\n"
            "\n"
            "AMENDMENT: (2026-08-15) Recovery order only:\n"
            "Recovery order: acc_new_0 then acc_new_1."
        ),
        failure_category=TierCFailureCategory.amendment_conflict,
        expected_nonline=NonlineAllocation.platform_absorbs,
        expected_commission=CommissionTreatment.proportional,
        canonical_equivalent="Non-line refund rule: platform absorbs.",
        regex_expected_to_succeed=False,
        description=(
            "Amendment changes only the recovery order, not the nonline rule or commission. "
            "Regex extracts the first recovery order (acc_orig_0 then acc_orig_1) instead of "
            "the amended one (acc_new_0 then acc_new_1). "
            "Nonline and commission are extracted correctly (no conflict), so partial success."
        ),
    ),

    TierCClause(
        clause_id="tc_amend_03",
        clause_text=(
            "Merchant agreement:\n"
            "Non-line refund rule: discount funder.\n"
            "Commission retained.\n"
            "\n"
            "AMENDMENT: (2026-09-01)\n"
            "Non-line refund rule: proportional.\n"
            "Commission is returned in full."
        ),
        failure_category=TierCFailureCategory.amendment_conflict,
        expected_nonline=NonlineAllocation.discount_funder,
        expected_commission=CommissionTreatment.unknown,
        canonical_equivalent="Non-line refund rule: proportional.",
        regex_expected_to_succeed=False,
        description=(
            "Full rule replacement by amendment. "
            "Regex returns first nonline (discount_funder) instead of amended (proportional). "
            "Commission conflict: retained + full → abstain (correct from regex perspective "
            "but both clauses exist; correct answer is full from amendment). "
            "Demonstrates amendment-scope blindness of regex."
        ),
    ),
)
