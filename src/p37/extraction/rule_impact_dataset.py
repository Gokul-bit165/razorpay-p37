"""
Rule-impact dataset.

Controlled cases that demonstrate whether each rule dimension has measurable
financial consequences.  Uses directly constructed ObservableCase objects —
NOT the frozen generator — so that structure can be precisely controlled.

Each RuleImpactCase references a specific validation case_id for audit
traceability.  Where a rule dimension is proven to be allocation-inert, the
structural limitation is documented here (not silently omitted).

Structural findings (proved by pre-implementation analysis):
  1. Commission treatment — zero allocation impact in observable predictor.
     residual_for_commission = max(refund - principal, 0) = 0 always because
     largest_remainder(refund, ...) always sums to refund.
  2. Recovery order — zero allocation impact.
     Each account draws from its own independent balance_snapshot.
     take = min(bear[acc], balance[acc], residual) => result order-independent.

See docs/DETERMINISTIC_EXTRACTION_TIER_B.md for full proofs.
"""
from __future__ import annotations

from dataclasses import dataclass

from p37.benchmark.models import (
    ObservableCase,
    ObservableLine,
    ObservableRefund,
    ObservableTransfer,
)
from p37.benchmark.rounding import largest_remainder

from .models import (
    AbstainReason,
    CommissionTreatment,
    NonlineAllocation,
    StructuredRule,
)


@dataclass(frozen=True)
class RuleImpactCase:
    """
    Controlled case for rule-dimension impact testing.

    case_id: unique identifier for this impact case
    obs: constructed ObservableCase (not from frozen generator)
    oracle_rule: the correct StructuredRule for this case
    oracle_bear: expected bear_paise per account (from oracle_rule + allocator)
    default_rule: the R0 wrong-assumption rule
    expected_r0_bear: what R0 default would produce (for comparison)
    linked_validation_case_id: specific val-set case ID for audit traceability
    structural_limitation: None if impact is demonstrable; documented string otherwise
    """

    case_id:                   str
    obs:                       ObservableCase
    oracle_rule:               StructuredRule
    oracle_bear:               dict[str, int]
    default_rule:              StructuredRule
    expected_r0_bear:          dict[str, int]
    linked_validation_case_id: str
    structural_limitation:     str | None


# ── Shared helpers ────────────────────────────────────────────────────────────

_CAPTURED = "2026-08-01T07:00:00+00:00"
_SETTLED  = "2026-08-01T10:00:00+00:00"
_HOLD     = "2026-08-01T14:00:00+00:00"
_REFUND_T = "2026-08-01T08:00:00+00:00"


def _tr(tid: str, account: str, amount: int, commission: int) -> ObservableTransfer:
    return ObservableTransfer(tid, account, amount, commission, _SETTLED, _HOLD)


def _ln(lid: str, amount: int, kind: str, attribution: tuple[str, ...]) -> ObservableLine:
    return ObservableLine(lid, amount, kind, attribution)


def _obs(
    case_id: str,
    gross: int,
    transfers: list[ObservableTransfer],
    lines: list[ObservableLine],
    refund_amount: int,
    refund_reason: str | None,
    balance: dict[str, int],
    agreement_text: str,
) -> ObservableCase:
    return ObservableCase(
        case_id=case_id,
        payment_id=f"pay_{case_id}",
        gross_amount_paise=gross,
        captured_at=_CAPTURED,
        transfers=tuple(transfers),
        lines=tuple(lines),
        refunds=(
            ObservableRefund(
                f"ref_{case_id}", refund_amount, _REFUND_T, refund_reason
            ),
        ),
        balance_snapshot=balance,
        agreement_text=agreement_text,
    )


def _proportional_rule(recovery_order: tuple[str, ...]) -> StructuredRule:
    """R0 default: wrong nonline rule, unknown commission, correct recovery order."""
    return StructuredRule(
        nonline_allocation=NonlineAllocation.proportional,
        commission_treatment=CommissionTreatment.unknown,
        recovery_order=recovery_order,
        funding_map=None,
        principal_bearer_verified=True,
        abstain=False,
        abstain_reason=AbstainReason.none,
        spans={},
    )


def _named_oracle_rule(
    nl: NonlineAllocation,
    ct: CommissionTreatment,
    recovery_order: tuple[str, ...],
    funding_map: dict[str, str] | None = None,
) -> StructuredRule:
    return StructuredRule(
        nonline_allocation=nl,
        commission_treatment=ct,
        recovery_order=recovery_order,
        funding_map=funding_map,
        principal_bearer_verified=True,
        abstain=False,
        abstain_reason=AbstainReason.none,
        spans={},
    )


# ── Nonline rule agreement texts ──────────────────────────────────────────────

_AGREEMENT_PROPORTIONAL = (
    "Refund allocation agreement:\n"
    "Goods: refund bears with the fulfilling vendor.\n"
    "Shipping: refund bears with the shipping-funding party.\n"
    "Platform fee: refund bears with the platform.\n"
    "Discount adjustments: refund bears with the party that funded the discount.\n"
    "Non-line refund rule: proportional.\n"
    "Recovery order: acc_platform_ri then acc_vendor_ri."
)

_AGREEMENT_SHIPPING_FUNDER = (
    "Refund allocation agreement:\n"
    "Goods: refund bears with the fulfilling vendor.\n"
    "Shipping: refund bears with the shipping-funding party.\n"
    "Platform fee: refund bears with the platform.\n"
    "Discount adjustments: refund bears with the party that funded the discount.\n"
    "Non-line refund rule: shipping funder.\n"
    "Recovery order: acc_platform_ri then acc_vendor_ri."
)


def _build_cases() -> tuple[RuleImpactCase, ...]:
    from p37.extraction.allocator import allocate  # local import to avoid circular deps

    cases: list[RuleImpactCase] = []

    # Shared transaction: 2 transfers, non-line refund (no line attribution)
    transfers_nl = [
        _tr("tr_ri_nl_0", "acc_platform_ri", 6000, 300),
        _tr("tr_ri_nl_1", "acc_vendor_ri",   4000, 200),
    ]
    lines_nl = [
        _ln("line_ri_0", 6000, "goods", ()),
        _ln("line_ri_1", 4000, "goods", ()),
    ]
    balance_nl = {"acc_platform_ri": 6000, "acc_vendor_ri": 4000}
    ro_nl = ("acc_platform_ri", "acc_vendor_ri")

    # ── RI-NL-1A: proportional rule (R0 and oracle agree) ────────────────────
    obs_prop = _obs(
        "ri_nl_1a", 10000, transfers_nl, lines_nl,
        2000, None, balance_nl, _AGREEMENT_PROPORTIONAL,
    )
    oracle_prop = _named_oracle_rule(
        NonlineAllocation.proportional, CommissionTreatment.unknown, ro_nl
    )
    pred_prop = allocate(obs_prop, oracle_prop)
    oracle_bear_prop = {
        pa.linked_account_id: pa.allocated_paise for pa in pred_prop.allocations
    }
    # R0 default also uses proportional, so same result
    cases.append(RuleImpactCase(
        case_id="ri_nl_1a",
        obs=obs_prop,
        oracle_rule=oracle_prop,
        oracle_bear=oracle_bear_prop,
        default_rule=_proportional_rule(ro_nl),
        expected_r0_bear=oracle_bear_prop,  # identical
        linked_validation_case_id="case_000140",  # first A5_proportional_cancellation
        structural_limitation=None,
    ))

    # ── RI-NL-1B: shipping_funder with oracle-supplied funding_map ────────────
    # Oracle knows acc_vendor_ri is the shipping funder.
    # R0 (proportional) gives different allocation than oracle (shipping_funder).
    # This demonstrates measurable financial impact when funding party is known.
    obs_ship = _obs(
        "ri_nl_1b", 10000, transfers_nl, lines_nl,
        2000, None, balance_nl, _AGREEMENT_SHIPPING_FUNDER,
    )
    oracle_ship = _named_oracle_rule(
        NonlineAllocation.shipping_funder,
        CommissionTreatment.unknown,
        ro_nl,
        funding_map={"shipping": "acc_vendor_ri"},
    )
    pred_ship = allocate(obs_ship, oracle_ship)
    oracle_bear_ship = {
        pa.linked_account_id: pa.allocated_paise for pa in pred_ship.allocations
    }

    # R0 (proportional): 2000 * [6000, 4000] / 10000 = [1200, 800]
    shares_prop = largest_remainder(
        2000, [6000, 4000], [10000, 10000], ["acc_platform_ri", "acc_vendor_ri"]
    )
    r0_bear_ship = {
        "acc_platform_ri": shares_prop[0],
        "acc_vendor_ri":   shares_prop[1],
    }

    cases.append(RuleImpactCase(
        case_id="ri_nl_1b",
        obs=obs_ship,
        oracle_rule=oracle_ship,
        oracle_bear=oracle_bear_ship,
        default_rule=_proportional_rule(ro_nl),
        expected_r0_bear=r0_bear_ship,
        linked_validation_case_id="case_000060",  # first A1_shipping_fee
        structural_limitation=None,
    ))

    # ── RI-NL-2: observability limit — shipping_funder, account not in text ──
    # The extractor correctly parses shipping_funder from text.
    # The allocator cannot resolve the account without funding_map.
    # R2 will abstain (funding_map_unavailable) — correct behaviour.
    cases.append(RuleImpactCase(
        case_id="ri_nl_2",
        obs=obs_ship,  # same observable case as ri_nl_1b
        oracle_rule=oracle_ship,
        oracle_bear=oracle_bear_ship,
        default_rule=_proportional_rule(ro_nl),
        expected_r0_bear=r0_bear_ship,
        linked_validation_case_id="case_000060",  # first A1_shipping_fee
        structural_limitation=(
            "Extractor correctly identifies NonlineAllocation.shipping_funder "
            "from text, but cannot determine which account IS the shipping funder "
            "because the agreement text does not name it (only says 'shipping funder'). "
            "Allocator returns abstain=True (funding_map_unavailable). "
            "This is an observability gap, not an extraction failure. "
            "An LLM cannot close this gap either — the information is simply absent."
        ),
    ))

    # ── RI-COMM-UNIT: commission math unit test ───────────────────────────────
    # Demonstrates that the allocator math for commission IS correct when
    # residual > 0, but this state cannot be reached via the observable proxy
    # (which always fills principal = refund_amount).
    # Tested via allocator.allocate() with a manually-adjusted flow — see
    # test_tier_b_safety.py::test_commission_unit_math.
    obs_comm = _obs(
        "ri_comm_unit", 10000, transfers_nl, lines_nl,
        2000, None, balance_nl, _AGREEMENT_PROPORTIONAL,
    )
    cases.append(RuleImpactCase(
        case_id="ri_comm_unit",
        obs=obs_comm,
        oracle_rule=_named_oracle_rule(
            NonlineAllocation.proportional, CommissionTreatment.retained, ro_nl
        ),
        oracle_bear={},  # not meaningful for unit test
        default_rule=_proportional_rule(ro_nl),
        expected_r0_bear={},
        linked_validation_case_id="case_000160",  # first C1_commission_retained
        structural_limitation=(
            "The observable predictor always sets sum(principal) = refund_amount "
            "via largest_remainder(), so residual_for_commission = 0 always. "
            "Commission treatment therefore has zero allocation impact in the "
            "observable predictor. Unit test (test_commission_unit_math) validates "
            "the allocator commission math directly with principal < refund_amount. "
            "This is a structural proxy constraint, not an extraction gap."
        ),
    ))

    # ── RI-RECOV-NEG: recovery order negative finding ─────────────────────────
    # Demonstrates that recovery order has zero allocation impact in this model.
    obs_recov = _obs(
        "ri_recov_neg", 10000, transfers_nl, lines_nl,
        2000, None, balance_nl, _AGREEMENT_PROPORTIONAL,
    )
    ro_reversed = ("acc_vendor_ri", "acc_platform_ri")
    oracle_forward = _named_oracle_rule(
        NonlineAllocation.proportional, CommissionTreatment.unknown, ro_nl
    )
    oracle_reversed = _named_oracle_rule(
        NonlineAllocation.proportional, CommissionTreatment.unknown, ro_reversed
    )
    pred_forward  = allocate(obs_recov, oracle_forward)
    pred_reversed = allocate(obs_recov, oracle_reversed)
    bear_forward  = {pa.linked_account_id: pa.allocated_paise for pa in pred_forward.allocations}
    bear_reversed = {pa.linked_account_id: pa.allocated_paise for pa in pred_reversed.allocations}

    cases.append(RuleImpactCase(
        case_id="ri_recov_neg",
        obs=obs_recov,
        oracle_rule=oracle_forward,
        oracle_bear=bear_forward,
        default_rule=_proportional_rule(ro_nl),
        expected_r0_bear=bear_forward,
        linked_validation_case_id="case_000000",  # first D1_single_line_return
        structural_limitation=(
            f"Recovery order is allocation-inert in this model. "
            f"Forward order {ro_nl}: {bear_forward}. "
            f"Reversed order {ro_reversed}: {bear_reversed}. "
            f"Per-account amounts are identical (proved: each account draws "
            f"from its own independent balance_snapshot, not a shared pool). "
            f"Recovery order extraction is a valid rule-level metric but has "
            f"zero allocation impact in the current allocator design."
        ),
    ))

    return tuple(cases)


RULE_IMPACT_CASES: tuple[RuleImpactCase, ...] = _build_cases()
