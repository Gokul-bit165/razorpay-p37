"""
Human-in-the-loop confirmation gate for P37 refund allocation rules.

Enforces the core research decision:
  "interpret a merchant/platform agreement into a structured rule,
   require human confirmation, then run deterministic allocation using the confirmed rule."

Provides:
  - ConfirmationRequest: Inspectable proposal presented to operator with raw text & spans.
  - ConfirmationDecision: Operator action (APPROVE, EDIT, REJECT) with audit notes.
  - HumanConfirmationGate: Workflow manager producing verified StructuredRule and audit logs.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from .allocator import allocate
from .models import (
    AbstainReason,
    CommissionTreatment,
    NonlineAllocation,
    StructuredRule,
)


class ConfirmationAction(Enum):
    APPROVE = "APPROVE"  # Accept extracted rule as-is
    EDIT    = "EDIT"     # Override one or more fields before execution
    REJECT  = "REJECT"   # Reject rule; force safe abstention


@dataclass(frozen=True)
class ConfirmationRequest:
    """
    Operator review payload packaging raw agreement text, extracted rule,
    grounding spans, and automated safety warnings.
    """
    request_id: str
    agreement_text: str
    extracted_rule: StructuredRule
    warnings: list[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class ConfirmationDecision:
    """
    Operator resolution for an extraction request.
    """
    action: ConfirmationAction
    reviewer_id: str
    audit_note: str
    overrides: Optional[dict[str, Any]] = None  # Populated when action == EDIT
    decided_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HumanConfirmationGate:
    """
    Review gate sitting between intelligent extraction and deterministic allocation.
    Maintains an immutable audit log of all human interactions.
    """

    def __init__(self):
        self.audit_log: list[dict[str, Any]] = []

    def prepare_request(self, agreement_text: str, extracted_rule: StructuredRule) -> ConfirmationRequest:
        """
        Package extraction results and identify safety warnings requiring human attention.
        """
        warnings: list[str] = []

        if extracted_rule.abstain:
            warnings.append(f"Extractor signaled abstention: {extracted_rule.abstain_reason.value}")

        if extracted_rule.nonline_allocation == NonlineAllocation.unknown:
            warnings.append("Non-line refund allocation could not be determined.")

        if extracted_rule.commission_treatment == CommissionTreatment.unknown:
            warnings.append("Commission treatment is unknown / not specified.")

        if not extracted_rule.recovery_order:
            warnings.append("Recovery order is empty.")

        if "AMENDMENT:" in agreement_text:
            warnings.append("Agreement text contains amendment clauses overriding base terms.")

        # Deterministic request ID based on agreement text and extracted fields
        stable_sig = f"{agreement_text}:{extracted_rule.nonline_allocation.value}:{extracted_rule.commission_treatment.value}"
        stable_id = hashlib.sha256(stable_sig.encode("utf-8")).hexdigest()[:8]
        req = ConfirmationRequest(
            request_id=f"req_{stable_id}",
            agreement_text=agreement_text,
            extracted_rule=extracted_rule,
            warnings=warnings,
        )
        return req

    def apply_decision(
        self,
        request: ConfirmationRequest,
        decision: ConfirmationDecision,
    ) -> StructuredRule:
        """
        Apply operator decision to produce the operative, confirmed StructuredRule.
        Records an audit entry.
        """
        orig = request.extracted_rule

        if decision.action == ConfirmationAction.APPROVE:
            confirmed_rule = orig

        elif decision.action == ConfirmationAction.REJECT:
            confirmed_rule = StructuredRule(
                nonline_allocation=NonlineAllocation.unknown,
                commission_treatment=CommissionTreatment.unknown,
                recovery_order=(),
                funding_map=None,
                principal_bearer_verified=False,
                abstain=True,
                abstain_reason=AbstainReason.unsupported,
                spans={},
                role_binding_spans={},
            )

        elif decision.action == ConfirmationAction.EDIT:
            overrides = decision.overrides or {}

            # Override nonline
            nonline = orig.nonline_allocation
            if "nonline_allocation" in overrides:
                val = overrides["nonline_allocation"]
                nonline = val if isinstance(val, NonlineAllocation) else NonlineAllocation(val)

            # Override commission
            commission = orig.commission_treatment
            if "commission_treatment" in overrides:
                val = overrides["commission_treatment"]
                commission = val if isinstance(val, CommissionTreatment) else CommissionTreatment(val)

            # Override recovery order
            recovery = orig.recovery_order
            if "recovery_order" in overrides:
                recovery = tuple(overrides["recovery_order"])

            # Override funding map
            funding_map = orig.funding_map
            if "funding_map" in overrides:
                funding_map = dict(overrides["funding_map"]) if overrides["funding_map"] is not None else None

            # Override abstain
            abstain = overrides.get("abstain", False)
            abstain_reason = (
                AbstainReason(overrides.get("abstain_reason"))
                if overrides.get("abstain_reason")
                else (AbstainReason.none if not abstain else orig.abstain_reason)
            )

            confirmed_rule = StructuredRule(
                nonline_allocation=nonline,
                commission_treatment=commission,
                recovery_order=recovery,
                funding_map=funding_map,
                principal_bearer_verified=overrides.get("principal_bearer_verified", orig.principal_bearer_verified),
                abstain=abstain,
                abstain_reason=abstain_reason,
                spans=orig.spans,
                role_binding_spans=orig.role_binding_spans,
            )
        else:
            raise ValueError(f"Unknown ConfirmationAction: {decision.action}")

        # Log audit entry
        self.audit_log.append({
            "request_id": request.request_id,
            "action": decision.action.value,
            "reviewer_id": decision.reviewer_id,
            "audit_note": decision.audit_note,
            "decided_at": decision.decided_at,
            "had_warnings": len(request.warnings) > 0,
            "warnings": request.warnings,
            "extracted_nonline": orig.nonline_allocation.value,
            "confirmed_nonline": confirmed_rule.nonline_allocation.value,
            "confirmed_abstain": confirmed_rule.abstain,
        })

        return confirmed_rule

    def confirm_and_allocate(
        self,
        observable_case: Any,
        request: ConfirmationRequest,
        decision: ConfirmationDecision,
    ) -> Any:
        """
        Execute deterministic allocation using the human-confirmed rule.
        """
        confirmed_rule = self.apply_decision(request, decision)
        return allocate(observable_case, confirmed_rule)
