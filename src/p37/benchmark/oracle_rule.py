from __future__ import annotations
from .models import GroundTruthCase
from .rules import StructuredRule

def oracle_rule(case: GroundTruthCase) -> StructuredRule:
    target = None
    rule = case.agreement.nonline_allocation_rule
    if rule == "shipping_funder":
        target = case.funding_map.get("shipping")
    elif rule in {"platform_absorbs", "platform_fee_funder"}:
        target = case.funding_map.get("platform")
    elif rule == "discount_funder":
        target = case.funding_map.get("discount")
    return StructuredRule(
        principal_bearer="fulfilling_account",
        nonline_allocation=rule,
        recovery_order=case.agreement.recovery_order,
        commission_treatment={t.linked_account_id: t.true_commission_treatment for t in case.transfers},
        nonline_target_account=target,
    )
