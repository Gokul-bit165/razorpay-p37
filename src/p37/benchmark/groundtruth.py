from __future__ import annotations

from collections import defaultdict

from .models import AccountAllocation, GroundTruthCase, GroundTruthResolution
from .rounding import largest_remainder


def _unresolvable(refund_id: str, reason: str) -> GroundTruthResolution:
    return GroundTruthResolution(refund_id, {}, True, reason, 0, 0)


def resolve(case: GroundTruthCase) -> GroundTruthResolution:
    """Independent answer key. Never imports or calls the baseline."""
    refund = case.refund
    if case.truth_invalid_reason:
        return _unresolvable(refund.refund_id, case.truth_invalid_reason)

    transfer_sum = sum(t.transfer_amount_paise for t in case.transfers)
    if refund.refund_amount_paise > case.gross_amount_paise:
        return _unresolvable(refund.refund_id, "refund_exceeds_payment")
    if refund.refund_amount_paise > transfer_sum:
        return _unresolvable(refund.refund_id, "refund_exceeds_transfers")
    if any(t.account_status != "active" for t in case.transfers):
        return _unresolvable(refund.refund_id, "account_not_active")

    line_by_id = {line.line_id: line for line in case.lines}
    for line_id, _ in refund.true_line_coverage:
        if line_id not in line_by_id:
            return _unresolvable(refund.refund_id, "covered_line_missing")

    principal: dict[str, int] = defaultdict(int)
    if refund.true_line_coverage:
        for line_id, amount in refund.true_line_coverage:
            principal[line_by_id[line_id].true_fulfilling_account] += amount
    else:
        accounts = [t.linked_account_id for t in case.transfers]
        rule = case.agreement.nonline_allocation_rule
        if rule == "shipping_funder":
            principal[case.funding_map["shipping"]] = refund.refund_amount_paise
        elif rule == "platform_absorbs" or rule == "platform_fee_funder":
            principal[case.funding_map["platform"]] = refund.refund_amount_paise
        elif rule == "discount_funder":
            principal[case.funding_map["discount"]] = refund.refund_amount_paise
        elif rule == "proportional":
            denom = sum(t.transfer_amount_paise for t in case.transfers)
            shares = largest_remainder(refund.refund_amount_paise, [t.transfer_amount_paise for t in case.transfers], [denom] * len(case.transfers), accounts)
            principal.update({a: s for a, s in zip(accounts, shares) if s})
        else:
            raise ValueError(f"unknown non-line rule: {rule}")

    residual_for_commission = max(refund.refund_amount_paise - sum(principal.values()), 0)
    commission: dict[str, int] = defaultdict(int)
    eligible = [t for t in case.transfers if t.linked_account_id in principal]
    if residual_for_commission and eligible:
        if all(t.true_commission_treatment == "retained" for t in eligible):
            pass
        else:
            numerators = [t.commission_component_paise for t in eligible]
            denom = sum(numerators)
            if denom:
                amount = min(residual_for_commission, denom)
                shares = largest_remainder(amount, numerators, [denom] * len(eligible), [t.linked_account_id for t in eligible])
                commission.update({t.linked_account_id: s for t, s in zip(eligible, shares) if s})

    transfer_by_account = {t.linked_account_id: t for t in case.transfers}
    allocations: dict[str, AccountAllocation] = {}
    truth_shortfall = 0
    for account in sorted(set(principal) | set(commission)):
        bear = principal.get(account, 0) + commission.get(account, 0)
        transfer = transfer_by_account[account]
        ceiling = max(transfer.transfer_amount_paise - transfer.already_reversed_paise, 0)
        capped = min(bear, ceiling)
        truth_shortfall += bear - capped
        principal_capped = min(principal.get(account, 0), capped)
        allocations[account] = AccountAllocation(principal_capped, capped - principal_capped, capped, capped < bear, 0)

    balances = {a: next(v for ts, v in timeline if ts == case.decision_time) for a, timeline in case.balance_timeline.items()}
    residual = sum(a.bear_paise for a in allocations.values())
    recovered: dict[str, int] = defaultdict(int)
    for account in case.agreement.recovery_order:
        if residual <= 0:
            break
        alloc = allocations.get(account)
        if alloc is None:
            continue
        take = min(alloc.bear_paise, balances.get(account, 0), residual)
        recovered[account] = take
        residual -= take

    allocations = {
        a: AccountAllocation(v.principal_alloc_paise, v.commission_alloc_paise, v.bear_paise, v.capped, recovered.get(a, 0))
        for a, v in allocations.items()
    }
    return GroundTruthResolution(refund.refund_id, allocations, False, None, truth_shortfall, residual)
