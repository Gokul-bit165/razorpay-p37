"""
Contract prose renderer for benchmark regimes (Phase 4 / Ladder).

Generates realistic contractual legal prose from underlying GroundTruthCase
stipulations across three benchmark regimes:
  - Regime A (Canonical): 100% standard Tier-B template.
  - Regime B (Mixed): ~30% canonical, ~70% derived non-canonical variants.
  - Regime C (Non-canonical): 100% derived non-canonical variants.

CONSTRAINTS & METHODOLOGY:
1. Variations are derived directly from the pre-existing tier_c_dataset.py
   linguistic categories (synonym, passive, negation, multi_clause, amendment).
2. Each linguistic category provides 5 distinct surface forms so n is not
   collapsed to a single repetitive template.
3. Deterministic execution seeded by dedicated PRNG seed (default: 3701),
   strictly separate from the transaction generator seed (42).
4. No regex patterns in extractor.py are modified to accommodate these outputs.
"""
from __future__ import annotations

import random
from typing import Any, Sequence

from p37.benchmark.models import GroundTruthCase

RENDERER_DEFAULT_SEED = 3701

# Mapping from internal rule string to human-readable concepts
NONLINE_RULE_NAMES = {
    "proportional": "proportional",
    "shipping_funder": "shipping funder",
    "platform_absorbs": "platform absorbs",
    "discount_funder": "discount funder",
}

COMMISSION_TREATMENT_NAMES = {
    "retained": "retained on refunds",
    "proportional": "returned proportionally",
    "full": "returned in full",
}


def render_canonical(case: GroundTruthCase) -> str:
    """Standard Tier-B canonical contract prose."""
    rule_str = NONLINE_RULE_NAMES.get(
        case.agreement.nonline_allocation_rule,
        case.agreement.nonline_allocation_rule.replace("_", " "),
    )
    comm_str = COMMISSION_TREATMENT_NAMES.get(
        case.agreement.commission_treatment,
        "retained on refunds",
    )
    lines = [
        "Refund allocation agreement:",
        "Goods: refund bears with the fulfilling vendor.",
        "Shipping: refund bears with the shipping-funding party.",
        "Platform fee: refund bears with the platform.",
        "Discount adjustments: refund bears with the party that funded the discount.",
        f"Non-line refund rule: {rule_str}.",
        f"Commission is {comm_str}.",
        "Recovery order: " + " then ".join(case.agreement.recovery_order) + ".",
    ]
    for role, account_id in sorted(case.funding_map.items()):
        lines.append(f"Funding account: {account_id} is designated {role}.")
    return "\n".join(lines)


# ── Surface Form Templates Derived from tier_c_dataset.py ───────────────────

def _render_synonym(case: GroundTruthCase, form_idx: int) -> str:
    rule = case.agreement.nonline_allocation_rule
    comm = case.agreement.commission_treatment
    rec = case.agreement.recovery_order
    acc0 = rec[0] if len(rec) > 0 else "acc_0"
    acc1 = rec[1] if len(rec) > 1 else "acc_1"
    fmap = case.funding_map

    # 5 distinct surface forms derived from tc_syn_01 .. tc_syn_04
    if form_idx == 0:
        nl_map = {
            "shipping_funder": "For cancellations, the carrier settlement pool bears the loss.",
            "platform_absorbs": "Non-line losses are absorbed by the marketplace operator.",
            "discount_funder": "Promotional concession losses fall on the promotional fund account.",
            "proportional": "Any non-order-line refund is shared across all linked accounts in proportion to their original transfer amounts.",
        }
        cm_map = {
            "retained": "Merchant commission is not returned on refunds.",
            "proportional": "Commission amounts will be reimbursed proportionally upon refund.",
            "full": "Platform commissions are refunded in their entirety.",
        }
        lines = [
            "Refund policy:",
            nl_map.get(rule, nl_map["proportional"]),
            cm_map.get(comm, cm_map["retained"]),
            f"Repayment sequence: {acc0} prior to {acc1}.",
        ]
        for role, acc in sorted(fmap.items()):
            lines.append(f"Funding account: {acc} is designated {role}.")
        return "\n".join(lines)

    elif form_idx == 1:
        nl_map = {
            "shipping_funder": "The freight and logistics provider shoulders unallocated reversal balances.",
            "platform_absorbs": "Unassigned refund deductions are absorbed entirely by the marketplace operator.",
            "discount_funder": "Rebate adjustments are charged against the promotional reserve pool.",
            "proportional": "Unattributed return balances are split ratably among recipient accounts according to payout ratios.",
        }
        cm_map = {
            "retained": "Earned commissions remain with Razorpay upon refund.",
            "proportional": "Platform service fees are waived on reversals.",
            "full": "Platform service fees are refunded in full to vendors.",
        }
        lines = [
            "Refund terms:",
            nl_map.get(rule, nl_map["proportional"]),
            cm_map.get(comm, cm_map["retained"]),
            f"Repayment priority: {acc0}, then {acc1}.",
        ]
        for role, acc in sorted(fmap.items()):
            lines.append(f"Account {acc} is assigned role {role}.")
        return "\n".join(lines)

    elif form_idx == 2:
        nl_map = {
            "shipping_funder": "The transportation facilitator bears final liability for overhead refund amounts.",
            "platform_absorbs": "Non-itemized balances shall be defrayed directly by the central platform.",
            "discount_funder": "Promotional subsidization deficits revert to the coupon-sponsoring account.",
            "proportional": "Overhead clawback liabilities are apportioned among parties on a pro-rata basis.",
        }
        cm_map = {
            "retained": "The commission component will be withheld by the platform on all reversals.",
            "proportional": "Platform fee portions are remitted back on a proportional basis.",
            "full": "All transaction processing commissions are returned without deduction.",
        }
        lines = [
            "Reversal terms and conditions:",
            nl_map.get(rule, nl_map["proportional"]),
            cm_map.get(comm, cm_map["retained"]),
            f"Settlement order: {acc0} before {acc1}.",
        ]
        for role, acc in sorted(fmap.items()):
            lines.append(f"Designated {role} account: {acc}.")
        return "\n".join(lines)

    elif form_idx == 3:
        nl_map = {
            "shipping_funder": "Delivery and handling partners are assigned sole responsibility for non-line deficits.",
            "platform_absorbs": "Overhead and miscellaneous return costs fall squarely upon the platform host.",
            "discount_funder": "Markdown allowances and promo deficits are deducted from the marketing allowance balance.",
            "proportional": "All connected accounts participate evenly in non-itemized return distributions based on principal.",
        }
        cm_map = {
            "retained": "Commission fees are non-refundable.",
            "proportional": "Commission is credited back prorated against the refund sum.",
            "full": "The complete commission tariff is refunded.",
        }
        lines = [
            "Cancellation agreement:",
            nl_map.get(rule, nl_map["proportional"]),
            cm_map.get(comm, cm_map["retained"]),
            f"Accounts are settled starting with {acc0}, proceeding to {acc1}.",
        ]
        for role, acc in sorted(fmap.items()):
            lines.append(f"Role assignment: {acc} operates as {role}.")
        return "\n".join(lines)

    else:
        nl_map = {
            "shipping_funder": "Dispatch logistics associates absorb remaining unmapped clawback sums.",
            "platform_absorbs": "System-wide return adjustments are written off by the platform administrator.",
            "discount_funder": "Campaign voucher funding balances carry full clawback obligations for non-line adjustments.",
            "proportional": "Clawbacks without specific item bindings are shared ratably across all settlement accounts.",
        }
        cm_map = {
            "retained": "Fee retentions remain non-reversible.",
            "proportional": "Commission clawback matches the proportional ratio of original transfers.",
            "full": "Commission reimbursement is 100% of the original assessed fee.",
        }
        lines = [
            "Master merchant policy:",
            nl_map.get(rule, nl_map["proportional"]),
            cm_map.get(comm, cm_map["retained"]),
            f"Settlement sequence: first {acc0}, subsequently {acc1}.",
        ]
        for role, acc in sorted(fmap.items()):
            lines.append(f"Funding account: {acc} is designated {role}.")
        return "\n".join(lines)


def _render_passive(case: GroundTruthCase, form_idx: int) -> str:
    rule = case.agreement.nonline_allocation_rule
    comm = case.agreement.commission_treatment
    rec = case.agreement.recovery_order
    acc0 = rec[0] if len(rec) > 0 else "acc_0"
    acc1 = rec[1] if len(rec) > 1 else "acc_1"
    fmap = case.funding_map

    # 5 distinct passive voice surface forms derived from tc_passive_01, tc_passive_02
    nl_targets = {
        "shipping_funder": "the party providing the shipping service",
        "platform_absorbs": "the central marketplace platform partner",
        "discount_funder": "the entity funding discount allowances",
        "proportional": "all recipient accounts on a proportional basis",
    }
    target = nl_targets.get(rule, nl_targets["proportional"])

    if form_idx == 0:
        lines = [
            "Refund obligations:",
            f"Non-line refunds shall be borne by {target}.",
            "The commission component will be withheld by the platform on all reversals." if comm == "retained" else "Commission amounts will be reimbursed proportionally upon refund.",
            f"Settlement: {acc0}, followed by {acc1}.",
        ]
    elif form_idx == 1:
        lines = [
            "Platform agreement:",
            f"All non-line losses are to be absorbed by {target}.",
            "Commission amounts will be reimbursed proportionally upon refund." if comm == "proportional" else "Commission is retained on all reversals.",
            f"Recovery order: {acc0} then {acc1}.",
        ]
    elif form_idx == 2:
        lines = [
            "Stipulations of settlement:",
            f"Any residual refund balance is required to be assumed by {target}.",
            "All transaction processing commissions are returned without deduction." if comm == "full" else "Commission fees are retained on cancellations.",
            f"Priority of deduction: {acc0} before {acc1}.",
        ]
    elif form_idx == 3:
        lines = [
            "Terms of fulfillment:",
            f"Disputed non-line liabilities are allocated to be covered by {target}.",
            "Platform fees are designated for pro-rata recovery." if comm == "proportional" else "Commission is not returned upon refund.",
            f"Accounts are cleared: {acc0} prior to {acc1}.",
        ]
    else:
        lines = [
            "Settlement protocol:",
            f"Overhead adjustments are directed to be discharged by {target}.",
            "Fee revenues are surrendered back in full upon cancellation." if comm == "full" else "Commissions earned are retained by the gateway.",
            f"Settlement sequence: first {acc0}, subsequently {acc1}.",
        ]

    for role, acc in sorted(fmap.items()):
        lines.append(f"Funding account: {acc} is designated {role}.")
    return "\n".join(lines)


def _render_negation(case: GroundTruthCase, form_idx: int) -> str:
    rule = case.agreement.nonline_allocation_rule
    comm = case.agreement.commission_treatment
    rec = case.agreement.recovery_order
    acc0 = rec[0] if len(rec) > 0 else "acc_0"
    acc1 = rec[1] if len(rec) > 1 else "acc_1"
    fmap = case.funding_map

    # 5 distinct negation surface forms derived from tc_neg_01, tc_neg_02
    nl_phrasing = {
        "shipping_funder": "The shipping partner bears the cost of all non-line refunds.",
        "platform_absorbs": "The central platform assumes full absorption for non-line refunds.",
        "discount_funder": "The discount-funding party bears the cost of all non-line refunds.",
        "proportional": "All connected parties share non-line refunds proportionally.",
    }
    rule_clause = nl_phrasing.get(rule, nl_phrasing["proportional"])

    if form_idx == 0:
        lines = [
            "Refund policy:",
            f"Non-line amounts are not distributed across vendors arbitrarily. {rule_clause}",
            "Commission will not be returned to the merchant on any refund." if comm == "retained" else "Commission will not be withheld and returns proportionally.",
            f"Recovery order: {acc0} then {acc1}.",
        ]
    elif form_idx == 1:
        lines = [
            "Operating conditions:",
            f"Rather than unguided distribution, {rule_clause}",
            "Commission adjustments are not subject to total retention and return in full." if comm == "full" else "Commissions are not returned upon cancellation.",
            f"Settlement order: {acc0} before {acc1}.",
        ]
    elif form_idx == 2:
        lines = [
            "Merchant schedule:",
            f"Under no circumstances shall untargeted absorption occur; instead, {rule_clause}",
            "Commission is not surrendered." if comm == "retained" else "Commission is returned proportionally.",
            f"Repayment sequence: {acc0} prior to {acc1}.",
        ]
    elif form_idx == 3:
        lines = [
            "Reversal terms:",
            f"Non-line losses do not follow standard order lines; {rule_clause}",
            "No commissions are refunded to transacting vendors." if comm == "retained" else "Commission is returned in full without fees withheld.",
            f"Repayment priority: {acc0}, then {acc1}.",
        ]
    else:
        lines = [
            "Settlement rules:",
            f"Except where otherwise mandated by statutory limits, {rule_clause}",
            "Commission components shall not be repaid." if comm == "retained" else "Commission returns proportionally.",
            f"Settlement: {acc0}, followed by {acc1}.",
        ]

    for role, acc in sorted(fmap.items()):
        lines.append(f"Funding account: {acc} is designated {role}.")
    return "\n".join(lines)


def _render_multi_clause(case: GroundTruthCase, form_idx: int) -> str:
    rule_str = NONLINE_RULE_NAMES.get(case.agreement.nonline_allocation_rule, "proportional")
    comm_str = COMMISSION_TREATMENT_NAMES.get(case.agreement.commission_treatment, "retained on refunds")
    rec = case.agreement.recovery_order
    acc0 = rec[0] if len(rec) > 0 else "acc_0"
    acc1 = rec[1] if len(rec) > 1 else "acc_1"
    fmap = case.funding_map

    # 5 distinct multi-clause precedence surface forms derived from tc_prec_01, tc_prec_02
    if form_idx == 0:
        lines = [
            "Base agreement (Section 4.1):",
            "Non-line refund rule: proportional.",
            "Commission is retained on refunds.",
            "",
            "Special terms (Section 4.2, applies to this transaction):",
            f"Non-line refund rule: {rule_str}.",
            f"Commission is {comm_str}.",
            f"Recovery order: {acc0} then {acc1}.",
        ]
    elif form_idx == 1:
        lines = [
            "Master agreement:",
            "General terms assign non-line refunds to discount funder.",
            "Commission is returned in full.",
            "",
            "Supplementary clause (overrides Master for current transaction category):",
            f"Non-line refund rule: {rule_str}.",
            f"Applicable commission treatment: {comm_str}.",
            f"Settlement order: {acc0} before {acc1}.",
        ]
    elif form_idx == 2:
        lines = [
            "Standard schedule:",
            "Default allocation: non-line refunds platform absorbs.",
            "Commission retained.",
            "",
            "Schedule B Specific Endorsement (preempts Standard Schedule):",
            f"Non-line refund rule: {rule_str}.",
            f"Commission is {comm_str}.",
            f"Repayment priority: {acc0}, then {acc1}.",
        ]
    elif form_idx == 3:
        lines = [
            "Primary terms of service:",
            "Unattributed claims shall be settled via proportional distribution.",
            "Commission is returned in full.",
            "",
            "Operational rider (governs in case of conflict):",
            f"Non-line refund rule: {rule_str}.",
            f"Commission is {comm_str}.",
            f"Settlement sequence: {acc0} then {acc1}.",
        ]
    else:
        lines = [
            "Section A General Provisions:",
            "Non-line rule is shipping funder.",
            "Commission is retained.",
            "",
            "Section D Priority Exceptions (overrules Section A):",
            f"Non-line refund rule: {rule_str}.",
            f"Commission is {comm_str}.",
            f"Recovery order: {acc0} then {acc1}.",
        ]

    for role, acc in sorted(fmap.items()):
        lines.append(f"Funding account: {acc} is designated {role}.")
    return "\n".join(lines)


def _render_amendment(case: GroundTruthCase, form_idx: int) -> str:
    rule_str = NONLINE_RULE_NAMES.get(case.agreement.nonline_allocation_rule, "proportional")
    comm_str = COMMISSION_TREATMENT_NAMES.get(case.agreement.commission_treatment, "retained on refunds")
    rec = case.agreement.recovery_order
    acc0 = rec[0] if len(rec) > 0 else "acc_0"
    acc1 = rec[1] if len(rec) > 1 else "acc_1"
    fmap = case.funding_map

    # 5 distinct amendment surface forms derived from tc_amend_01 .. tc_amend_03
    if form_idx == 0:
        lines = [
            "Original agreement:",
            "Non-line refund rule: proportional.",
            "Commission is returned in full.",
            "Recovery order: acc_legacy_0 then acc_legacy_1.",
            "",
            "AMENDMENT: (effective 2026-07-01)",
            f"Non-line refund rule: {rule_str}.",
            f"Commission is {comm_str}.",
            f"Recovery order: {acc0} then {acc1}.",
        ]
    elif form_idx == 1:
        lines = [
            "Platform agreement:",
            "Non-line refund rule: platform absorbs.",
            "Commission is returned proportionally.",
            "Recovery order: acc_legacy_0 then acc_legacy_1.",
            "",
            "AMENDMENT: (effective 2026-08-15) Superseding terms:",
            f"Non-line refund rule: {rule_str}.",
            f"Recovery order: {acc0} then {acc1}.",
        ]
    elif form_idx == 2:
        lines = [
            "Merchant agreement:",
            "Non-line refund rule: discount funder.",
            "Commission retained.",
            "",
            "AMENDMENT: (effective 2026-09-01)",
            f"Non-line refund rule: {rule_str}.",
            f"Commission is {comm_str}.",
            f"Recovery order: {acc0} then {acc1}.",
        ]
    elif form_idx == 3:
        lines = [
            "Executed agreement:",
            "Terms specify non-line refund rule: shipping funder.",
            "Recovery order: acc_legacy_0 then acc_legacy_1.",
            "",
            "AMENDMENT: (formal rider dated 2026-09-10)",
            f"Amended non-line refund rule: {rule_str}.",
            f"Recovery order: {acc0} then {acc1}.",
        ]
    else:
        lines = [
            "Bilateral agreement:",
            "Non-line refund rule: proportional.",
            "Commission is returned proportionally.",
            "",
            "AMENDMENT: (Addendum 3)",
            f"Non-line refund rule: {rule_str}.",
            f"Commission is {comm_str}.",
            f"Recovery order: {acc0} then {acc1}.",
        ]

    for role, acc in sorted(fmap.items()):
        lines.append(f"Funding account: {acc} is designated {role}.")
    return "\n".join(lines)


# ── Main Rendering Interface ────────────────────────────────────────────────

class ContractRenderer:
    """
    Renders legal contract prose across Regime A, Regime B, and Regime C.
    """

    def __init__(self, seed: int = RENDERER_DEFAULT_SEED):
        self.seed = seed
        self._rng = random.Random(seed)

    def render(self, case: GroundTruthCase, regime: str, case_index: int = 0) -> str:
        """
        Render legal agreement text for a case under the specified regime.

        Regimes:
          - 'a' / 'canonical': 100% canonical Tier-B template
          - 'b' / 'mixed': ~30% canonical, ~70% derived non-canonical
          - 'c' / 'non_canonical': 100% derived non-canonical
        """
        regime_clean = regime.lower().strip()
        if regime_clean in ("a", "canonical"):
            return render_canonical(case)

        # For deterministic reproducibility per case, seed a sub-generator
        case_rng = random.Random(self.seed + case_index * 137)

        if regime_clean in ("b", "mixed"):
            # ~30% canonical
            if case_rng.random() < 0.30:
                return render_canonical(case)

        # Choose one of the 5 linguistic categories uniformly
        cat_idx = case_rng.randint(0, 4)
        form_idx = case_rng.randint(0, 4)

        if cat_idx == 0:
            return _render_synonym(case, form_idx)
        elif cat_idx == 1:
            return _render_passive(case, form_idx)
        elif cat_idx == 2:
            return _render_negation(case, form_idx)
        elif cat_idx == 3:
            return _render_multi_clause(case, form_idx)
        else:
            return _render_amendment(case, form_idx)
