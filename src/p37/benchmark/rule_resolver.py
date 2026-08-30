from __future__ import annotations
from .models import ObservableCase, Prediction, PredictedAllocation
from .rules import StructuredRule
from .rounding import largest_remainder

DEFAULT_RULE = StructuredRule()

def resolve(case: ObservableCase, rule: StructuredRule = DEFAULT_RULE) -> Prediction:
    refund = case.refunds[0]
    if refund.refund_amount_paise > case.gross_amount_paise:
        return Prediction(refund.refund_id, (), True, "refund_exceeds_payment")
    transfer_total = sum(t.transfer_amount_paise for t in case.transfers)
    if refund.refund_amount_paise > transfer_total:
        return Prediction(refund.refund_id, (), True, "refund_exceeds_transfers")

    allocations: dict[str, int] = {}
    attributed = [(line.line_id, line.line_attribution[0], line.line_amount_paise)
                  for line in case.lines if len(line.line_attribution) == 1]
    if attributed:
        for _, account, amount in attributed:
            allocations[account] = allocations.get(account, 0) + amount
    elif rule.nonline_allocation == "proportional":
        shares = largest_remainder(
            refund.refund_amount_paise,
            [t.transfer_amount_paise for t in case.transfers],
            [transfer_total] * len(case.transfers),
            [t.linked_account_id for t in case.transfers],
        )
        allocations = {t.linked_account_id: share for t, share in zip(case.transfers, shares) if share}
    elif rule.nonline_target_account is not None:
        allocations[rule.nonline_target_account] = refund.refund_amount_paise
    else:
        return Prediction(refund.refund_id, (), True, "rule_target_not_observable")

    principal_total = sum(allocations.values())
    residual = max(refund.refund_amount_paise - principal_total, 0)
    for account in sorted(allocations):
        if residual <= 0:
            break
        if rule.commission_treatment.get(account, "proportional") == "full":
            commission = next(t.commission_component_paise for t in case.transfers if t.linked_account_id == account)
            add = min(commission, residual)
            allocations[account] += add
            residual -= add

    return Prediction(
        refund_id=refund.refund_id,
        allocations=tuple(PredictedAllocation(k, v) for k, v in sorted(allocations.items()) if v),
        abstained=False,
        reason_code="rule_driven",
    )
