from __future__ import annotations

import json
from dataclasses import asdict

from .models import GroundTruthCase, ObservableCase, ObservableLine, ObservableRefund, ObservableTransfer


def _agreement_text(case: GroundTruthCase) -> str:
    return "\n".join([
        "Refund allocation agreement:",
        "Goods: refund bears with the fulfilling vendor.",
        "Shipping: refund bears with the shipping-funding party.",
        "Platform fee: refund bears with the platform.",
        "Discount adjustments: refund bears with the party that funded the discount.",
        f"Non-line refund rule: {case.agreement.nonline_allocation_rule.replace('_', ' ')}.",
        "Recovery order: " + " then ".join(case.agreement.recovery_order) + ".",
    ])


def project(case: GroundTruthCase) -> ObservableCase:
    covered = {line_id for line_id, _ in case.refund.true_line_coverage}
    true_accounts = {line.line_id: line.true_fulfilling_account for line in case.lines}
    attrs: dict[str, tuple[str, ...]] = {}
    for line in case.lines:
        if line.line_id not in covered:
            attrs[line.line_id] = ()
        elif case.case_type == "N4_line_maps_to_multiple":
            attrs[line.line_id] = (true_accounts[line.line_id], f"{true_accounts[line.line_id]}_alt")
        else:
            attrs[line.line_id] = (true_accounts[line.line_id],)

    observed_reason = case.refund.true_reason
    if case.case_type in {"A1_shipping_fee", "A2_goodwill_credit", "A3_discount_funded", "A4_platform_fee_only", "A5_proportional_cancellation"}:
        observed_reason = None
    elif case.case_type == "N5_reason_mislabelled":
        observed_reason = "mislabelled_reason"

    return ObservableCase(
        case_id=case.case_id,
        payment_id=case.payment_id,
        gross_amount_paise=case.gross_amount_paise,
        captured_at=case.captured_at,
        transfers=tuple(ObservableTransfer(t.transfer_id, t.linked_account_id, t.transfer_amount_paise, t.commission_component_paise, t.settled_at, t.hold_release_at) for t in case.transfers),
        lines=tuple(ObservableLine(l.line_id, l.line_amount_paise, l.line_kind, attrs[l.line_id]) for l in case.lines),
        refunds=(ObservableRefund(case.refund.refund_id, case.refund.refund_amount_paise, case.refund.initiated_at, observed_reason),),
        balance_snapshot={a: next(v for ts, v in timeline if ts == case.decision_time) for a, timeline in case.balance_timeline.items()},
        agreement_text=_agreement_text(case),
    )


def observable_to_json(case: ObservableCase) -> str:
    return json.dumps(asdict(case), sort_keys=True, separators=(",", ":"))
