"""
Observable-state predictor allocator.

Intentionally different from groundtruth.py — the two implementations
operate on different information:

  groundtruth.py — authoritative hidden-state resolver
      Reads: GroundTruthCase (true_line_coverage, true_commission_treatment,
             funding_map, balance_timeline)
      Returns: GroundTruthResolution (the answer key)

  allocator.py — predictor-side observable-state allocator
      Reads: ObservableCase (line_attribution, line_amount_paise,
             transfer_amount_paise, commission_component_paise,
             balance_snapshot) + StructuredRule (injected)
      Returns: Prediction (compared against the answer key)

The predictor allocator is validated to match the authoritative resolver
when supplied with the oracle rule on all resolvable validation cases.
Any disagreement must be investigated — see test_tier_b_safety.py
(test_oracle_rule_allocator_matches_groundtruth).

Structural limitations documented in DETERMINISTIC_EXTRACTION_TIER_B.md:
  - residual_for_commission is always 0 (observable proxy fills principal = refund)
  - recovery order is allocation-inert (each account draws from its own balance)
"""
from __future__ import annotations

from p37.benchmark.models import ObservableCase, Prediction, PredictedAllocation
from p37.benchmark.rounding import largest_remainder

from .models import NonlineAllocation, CommissionTreatment, StructuredRule


def allocate(obs: ObservableCase, rule: StructuredRule) -> Prediction:
    """
    Predictor-side allocation using only observable state and an injected rule.

    Returns a Prediction with abstained=True when allocation cannot be determined.
    Does NOT import or access GroundTruthCase or any hidden benchmark type.
    """
    # ── Structural Security Invariants (P0-3) ──────────────────────────────────
    # The allocator solely accepts qualitative enum classifications from the extracted
    # rule. Under no circumstances may an extracted rule inject monetary paise amounts,
    # balance modifications, or arbitrary floating-point percentage modifiers.
    assert not hasattr(rule, "amounts"), "Security invariant: StructuredRule must never contain amount fields."
    assert not hasattr(rule, "allocated_paise"), "Security invariant: StructuredRule must never specify paise allocations."
    assert not hasattr(rule, "fee_percentage"), "Security invariant: StructuredRule must never specify percentages."
    assert rule.nonline_allocation in NonlineAllocation, f"Security invariant: Unknown nonline allocation '{rule.nonline_allocation}'."
    assert rule.commission_treatment in CommissionTreatment, f"Security invariant: Unknown commission treatment '{rule.commission_treatment}'."

    refund = obs.refunds[0]
    refund_id = refund.refund_id
    refund_amount = refund.refund_amount_paise

    # Abstain if rule instructs it
    if rule.abstain:
        return Prediction(refund_id, (), True, f"rule_abstain:{rule.abstain_reason.value}")


    # Observable guard rails
    transfer_sum = sum(t.transfer_amount_paise for t in obs.transfers)
    if refund_amount > obs.gross_amount_paise:
        return Prediction(refund_id, (), True, "refund_exceeds_payment")
    if refund_amount > transfer_sum:
        return Prediction(refund_id, (), True, "refund_exceeds_transfers")

    # ── Principal allocation ───────────────────────────────────────────────────
    covered_lines = [ln for ln in obs.lines if ln.line_attribution]
    principal: dict[str, int] = {}

    if covered_lines:
        # Line-based proxy: distribute refund proportionally to attributed line amounts.
        # Note: sum(principal) == refund_amount always (mathematical identity of
        # largest_remainder).  residual_for_commission will therefore be 0.
        acct_amounts: dict[str, int] = {}
        for ln in covered_lines:
            for acc in ln.line_attribution:
                acct_amounts[acc] = acct_amounts.get(acc, 0) + ln.line_amount_paise

        total = sum(acct_amounts.values())
        if total == 0:
            return Prediction(refund_id, (), True, "zero_line_total")

        accounts = sorted(acct_amounts.keys())
        shares = largest_remainder(
            refund_amount,
            [acct_amounts[a] for a in accounts],
            [total] * len(accounts),
            accounts,
        )
        principal = {a: s for a, s in zip(accounts, shares) if s > 0}

    else:
        # Non-line: apply nonline_allocation rule from StructuredRule
        nl = rule.nonline_allocation

        if nl == NonlineAllocation.proportional:
            total = sum(t.transfer_amount_paise for t in obs.transfers)
            if total == 0:
                return Prediction(refund_id, (), True, "zero_transfer_total")
            accounts = [t.linked_account_id for t in obs.transfers]
            shares = largest_remainder(
                refund_amount,
                [t.transfer_amount_paise for t in obs.transfers],
                [total] * len(obs.transfers),
                accounts,
            )
            principal = {a: s for a, s in zip(accounts, shares) if s > 0}

        elif nl in (
            NonlineAllocation.shipping_funder,
            NonlineAllocation.platform_absorbs,
            NonlineAllocation.discount_funder,
        ):
            if rule.funding_map is None:
                return Prediction(refund_id, (), True, "funding_map_unavailable")
            role_map = {
                NonlineAllocation.shipping_funder:  "shipping",
                NonlineAllocation.platform_absorbs: "platform",
                NonlineAllocation.discount_funder:  "discount",
            }
            role = role_map[nl]
            acct = rule.funding_map.get(role)
            if acct is None:
                return Prediction(refund_id, (), True, f"funding_map_missing_role:{role}")
            principal = {acct: refund_amount}

        elif nl == NonlineAllocation.unknown:
            return Prediction(refund_id, (), True, "nonline_rule_unknown")

        else:
            return Prediction(refund_id, (), True, f"unsupported_nonline:{nl.value}")

    # ── Commission ────────────────────────────────────────────────────────────
    # residual_for_commission = max(refund_amount - sum(principal), 0)
    # For line-based cases: sum(principal) == refund_amount → residual == 0 always.
    # For non-line cases: same identity holds.
    # Commission treatment therefore has zero allocation impact in the observable
    # predictor.  The math is preserved here for correctness; the finding is
    # documented explicitly.
    residual_for_commission = max(refund_amount - sum(principal.values()), 0)
    commission: dict[str, int] = {}
    ct = rule.commission_treatment

    if (
        residual_for_commission > 0
        and ct not in (CommissionTreatment.retained, CommissionTreatment.unknown)
    ):
        eligible = [t for t in obs.transfers if t.linked_account_id in principal]
        numerators = [t.commission_component_paise for t in eligible]
        denom = sum(numerators)
        if denom > 0:
            amount = min(residual_for_commission, denom)
            shares = largest_remainder(
                amount,
                numerators,
                [denom] * len(eligible),
                [t.linked_account_id for t in eligible],
            )
            commission = {
                t.linked_account_id: s
                for t, s in zip(eligible, shares)
                if s > 0
            }

    # ── Transfer ceiling ──────────────────────────────────────────────────────
    transfer_by_account = {t.linked_account_id: t for t in obs.transfers}
    bear: dict[str, int] = {}
    for acc in sorted(set(principal) | set(commission)):
        b = principal.get(acc, 0) + commission.get(acc, 0)
        ceiling = max(transfer_by_account[acc].transfer_amount_paise, 0)
        bear[acc] = min(b, ceiling)

    # ── Recovery ──────────────────────────────────────────────────────────────
    # Recovery order is allocation-inert in this model (each account draws from
    # its own independent balance_snapshot).  The loop is retained for
    # correctness and to mirror the oracle's structure; see structural finding
    # in DETERMINISTIC_EXTRACTION_TIER_B.md.
    residual = sum(bear.values())
    recovered: dict[str, int] = {}
    for acc in rule.recovery_order:
        if residual <= 0:
            break
        if acc not in bear:
            continue
        take = min(bear[acc], obs.balance_snapshot.get(acc, 0), residual)
        recovered[acc] = take
        residual -= take

    allocs = tuple(
        PredictedAllocation(a, recovered.get(a, 0))
        for a in bear
    )
    return Prediction(refund_id, allocs, False, None)
