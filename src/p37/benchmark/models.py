from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

CaseType = Literal[
    "D1_single_line_return", "D2_multi_line_clean", "D3_full_refund",
    "A1_shipping_fee", "A2_goodwill_credit", "A3_discount_funded",
    "A4_platform_fee_only", "A5_proportional_cancellation",
    "C1_commission_retained", "C2_commission_full_return",
    "B1_rounding", "B2_exact_balance", "B3_one_paisa_short", "B4_prior_partial_reversal",
    "B5_zero_commission", "B6_single_transfer",
    "N1_refund_exceeds_payment", "N2_refund_exceeds_transfers", "N3_closed_account",
    "N4_line_maps_to_multiple", "N5_reason_mislabelled",
]
LineKind = Literal["goods", "shipping", "platform_fee", "discount_adjustment"]
CommissionTreatment = Literal["proportional", "full", "retained"]
AccountStatus = Literal["active", "closed", "suspended"]

@dataclass(frozen=True)
class TrueLine:
    line_id: str
    line_amount_paise: int
    true_fulfilling_account: str
    line_kind: LineKind

@dataclass(frozen=True)
class TrueTransfer:
    transfer_id: str
    linked_account_id: str
    transfer_amount_paise: int
    commission_component_paise: int
    settled_at: str
    hold_release_at: str
    true_commission_treatment: CommissionTreatment
    account_status: AccountStatus
    already_reversed_paise: int

@dataclass(frozen=True)
class AgreementTruth:
    principal_bearer_rule: Mapping[LineKind, str]
    nonline_allocation_rule: str
    recovery_order: tuple[str, ...]

@dataclass(frozen=True)
class RefundTruth:
    refund_id: str
    refund_amount_paise: int
    initiated_at: str
    true_line_coverage: tuple[tuple[str, int], ...]
    true_reason: str | None

@dataclass(frozen=True)
class GroundTruthCase:
    case_id: str
    case_type: CaseType
    payment_id: str
    gross_amount_paise: int
    captured_at: str
    funding_map: Mapping[str, str]
    lines: tuple[TrueLine, ...]
    transfers: tuple[TrueTransfer, ...]
    agreement: AgreementTruth
    balance_timeline: Mapping[str, tuple[tuple[str, int], ...]]
    decision_time: str
    refund: RefundTruth
    observed_reason_override: str | None = None
    truth_invalid_reason: str | None = None

@dataclass(frozen=True)
class ObservableLine:
    line_id: str
    line_amount_paise: int
    line_kind: LineKind
    line_attribution: tuple[str, ...]

@dataclass(frozen=True)
class ObservableTransfer:
    transfer_id: str
    linked_account_id: str
    transfer_amount_paise: int
    commission_component_paise: int
    settled_at: str
    hold_release_at: str

@dataclass(frozen=True)
class ObservableRefund:
    refund_id: str
    refund_amount_paise: int
    initiated_at: str
    observed_reason: str | None

@dataclass(frozen=True)
class ObservableCase:
    case_id: str
    payment_id: str
    gross_amount_paise: int
    captured_at: str
    transfers: tuple[ObservableTransfer, ...]
    lines: tuple[ObservableLine, ...]
    refunds: tuple[ObservableRefund, ...]
    balance_snapshot: Mapping[str, int]
    agreement_text: str

@dataclass(frozen=True)
class AccountAllocation:
    principal_alloc_paise: int
    commission_alloc_paise: int
    bear_paise: int
    capped: bool
    recoverable_paise: int

@dataclass(frozen=True)
class GroundTruthResolution:
    refund_id: str
    allocations: Mapping[str, AccountAllocation]
    unresolvable: bool
    reason_code: str | None
    truth_shortfall_paise: int
    unrecoverable_residual_paise: int

@dataclass(frozen=True)
class PredictedAllocation:
    linked_account_id: str
    allocated_paise: int

@dataclass(frozen=True)
class Prediction:
    refund_id: str
    allocations: tuple[PredictedAllocation, ...]
    abstained: bool
    reason_code: str | None = None
