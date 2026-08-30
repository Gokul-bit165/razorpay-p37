from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import random

from .models import AgreementTruth, GroundTruthCase, RefundTruth, TrueLine, TrueTransfer

CASE_TYPES = (
    "D1_single_line_return", "D2_multi_line_clean", "D3_full_refund",
    "A1_shipping_fee", "A2_goodwill_credit", "A3_discount_funded", "A4_platform_fee_only", "A5_proportional_cancellation",
    "C1_commission_retained", "C2_commission_full_return",
    "B1_rounding", "B2_exact_balance", "B3_one_paisa_short", "B4_prior_partial_reversal", "B5_zero_commission", "B6_single_transfer",
    "N1_refund_exceeds_payment", "N2_refund_exceeds_transfers", "N3_closed_account", "N4_line_maps_to_multiple", "N5_reason_mislabelled",
)

@dataclass(frozen=True)
class GenerationConfig:
    counts: dict[str, int]
    seed: int


def _rng(seed: int, index: int) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{index}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def generate(config: GenerationConfig) -> list[GroundTruthCase]:
    out = []
    index = 0
    for case_type in CASE_TYPES:
        for _ in range(config.counts.get(case_type, 0)):
            out.append(_make(case_type, _rng(config.seed, index), index))
            index += 1
    return out


def _make(case_type: str, rng: random.Random, index: int) -> GroundTruthCase:
    gross = 10000 if case_type == "B1_rounding" else rng.choice((10000, 15000, 20000, 30000, 50000))
    n = 1 if case_type == "B6_single_transfer" else rng.choice((2, 2, 3))
    accounts = [f"acc_{index:05d}_{i}" for i in range(n)]
    weights = [rng.randint(20, 80) for _ in accounts]
    total_weight = sum(weights)
    transfers_amount = [gross * w // total_weight for w in weights]
    transfers_amount[-1] += gross - sum(transfers_amount)
    if case_type == "N2_refund_exceeds_transfers":
        transfers_amount[-1] = max(0, transfers_amount[-1] - 100)

    base = datetime(2026, 8, 1, tzinfo=timezone.utc) + timedelta(hours=index)
    decision = base.isoformat()
    lines = tuple(TrueLine(f"line_{index:05d}_{i}", transfers_amount[i], accounts[i], "goods") for i in range(n))

    commission_treatment = "retained" if case_type == "C1_commission_retained" else "full" if case_type == "C2_commission_full_return" else "proportional"
    transfers = []
    for i, account in enumerate(accounts):
        amount = transfers_amount[i]
        commission = 0 if case_type == "B5_zero_commission" else amount // 20
        already = amount * 3 // 5 if case_type == "B4_prior_partial_reversal" and i == 0 else 0
        status = "closed" if case_type == "N3_closed_account" and i == 0 else "active"
        transfers.append(TrueTransfer(f"tr_{index:05d}_{i}", account, amount, commission, (base-timedelta(hours=2)).isoformat(), (base+timedelta(hours=4)).isoformat(), commission_treatment, status, already))
    transfers = tuple(transfers)

    nonline = "proportional"
    if case_type == "A1_shipping_fee": nonline = "shipping_funder"
    elif case_type == "A2_goodwill_credit": nonline = "platform_absorbs"
    elif case_type == "A3_discount_funded": nonline = "discount_funder"
    elif case_type == "A4_platform_fee_only": nonline = "platform_fee_funder"

    agreement = AgreementTruth(
        {"goods":"fulfilling_vendor","shipping":"shipping_funder","platform_fee":"platform","discount_adjustment":"discount_funder"},
        nonline,
        tuple(accounts),
    )

    if case_type == "D1_single_line_return":
        refund, coverage, reason = lines[0].line_amount_paise, ((lines[0].line_id, lines[0].line_amount_paise),), "return"
    elif case_type == "D2_multi_line_clean":
        refund = sum(l.line_amount_paise for l in lines[:2])
        coverage = tuple((l.line_id, l.line_amount_paise) for l in lines[:2])
        reason = "return"
    elif case_type == "D3_full_refund":
        refund, coverage, reason = gross, tuple((l.line_id, l.line_amount_paise) for l in lines), "return"
    elif case_type == "C1_commission_retained":
        refund = min(gross//5, lines[0].line_amount_paise)
        coverage, reason = ((lines[0].line_id, refund),), "return"
    elif case_type == "C2_commission_full_return":
        refund = min(gross//5, lines[0].line_amount_paise)
        principal = max(refund - (transfers[0].commission_component_paise or 1), 1)
        coverage, reason = ((lines[0].line_id, principal),), "return"
    elif case_type == "N1_refund_exceeds_payment":
        refund, coverage, reason = gross+1, (), "invalid"
    elif case_type == "N2_refund_exceeds_transfers":
        refund, coverage, reason = gross, (), "invalid"
    elif case_type == "A5_proportional_cancellation":
        refund, coverage, reason = gross//2, (), "cancellation"
    else:
        refund = max(gross//5, 100)
        if case_type == "B2_exact_balance": refund = min(refund, transfers[0].transfer_amount_paise)
        if case_type == "B3_one_paisa_short": refund = min(refund, transfers[0].transfer_amount_paise)
        coverage = ()
        reason = {"A1_shipping_fee":"shipping","A2_goodwill_credit":"goodwill","A3_discount_funded":"discount-reversal","A4_platform_fee_only":"platform-fee","B1_rounding":"goodwill","B2_exact_balance":"return","B3_one_paisa_short":"return","B4_prior_partial_reversal":"return","B5_zero_commission":"return","B6_single_transfer":"return","N3_closed_account":"return","N4_line_maps_to_multiple":"return","N5_reason_mislabelled":"return","C1_commission_retained":"return","C2_commission_full_return":"return"}.get(case_type, "goodwill")

    funding = {"shipping": accounts[-1], "platform": accounts[0], "discount": accounts[-1]}
    balances = {}
    for i, t in enumerate(transfers):
        bal = max(t.transfer_amount_paise, refund)
        if case_type == "B2_exact_balance" and i == 0: bal = refund
        if case_type == "B3_one_paisa_short" and i == 0: bal = max(refund-1, 0)
        balances[t.linked_account_id] = ((decision, bal),)

    invalid = {"N1_refund_exceeds_payment":"refund_exceeds_payment","N2_refund_exceeds_transfers":"refund_exceeds_transfers","N3_closed_account":"account_not_active","N4_line_maps_to_multiple":"line_attribution_ambiguous","N5_reason_mislabelled":"reason_mislabelled"}.get(case_type)
    return GroundTruthCase(f"case_{index:06d}", case_type, f"pay_{index:06d}", gross, (base-timedelta(hours=3)).isoformat(), funding, lines, transfers, agreement, balances, decision, RefundTruth(f"ref_{index:06d}", refund, (base+timedelta(minutes=10)).isoformat(), coverage, reason), None, invalid)
