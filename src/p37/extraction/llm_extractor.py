"""
LLM-based and Hybrid Rule Extractors for P37 Refund Allocation Agreements.

Translates natural language agreement text (including Tier-C non-canonical phrasing,
synonyms, passive voice, negation, multi-clause precedence, and amendment conflicts)
into a strictly validated StructuredRule with exact source-span grounding.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from .extractor import extract as extract_regex
from .llm_client import LLMClient, MockLLMClient
from .models import (
    AbstainReason,
    CommissionTreatment,
    ExtractionError,
    NonlineAllocation,
    SourceSpan,
    StructuredRule,
)

SYSTEM_PROMPT = """You are a precision legal rule extractor for Razorpay split-payment refund agreements (P37).
Analyze the input contract text and extract the governing refund rules into a structured JSON object.

Rules to enforce:
1. Non-line refund rule (nonline_allocation):
   - "proportional": distributed proportionally across lines/accounts.
   - "shipping_funder": non-line costs fall on the shipping service provider/pool.
   - "platform_absorbs": platform/marketplace operator absorbs non-line costs or platform fee funder.
   - "discount_funder": promotional/discount concession funder absorbs non-line costs.
   - "unknown": not specified or ambiguous.

2. Commission treatment (commission_treatment):
   - "retained": platform retains commission upon refund (not refunded / withheld).
   - "full": platform returns commission in full upon refund (waived / refunded in full).
   - "proportional": platform returns commission proportionally to refund amount.
   - "unknown": not specified.

3. Recovery order (recovery_order):
   - Ordered list of account IDs to draw clawbacks/refunds from (e.g. ["acc_1", "acc_2"]).

4. Role bindings (funding_map):
   - Map of role name ("shipping", "platform", "discount") to designated account_id (e.g. {"shipping": "acc_1"}).

5. Precedence & Amendments:
   - "AMENDMENT:" clauses override earlier conflicting base contract terms for that specific rule or role.
   - If two unamended clauses directly contradict each other without precedence, set "abstain": true, "abstain_reason": "conflicting".
   - If two different accounts are assigned to the same role without an amendment, set "abstain": true, "abstain_reason": "role_binding_conflict".

6. Source Spans (spans & role_binding_spans):
   - CRITICAL SAFETY: For every extracted field, quote the EXACT verbatim substring from the input text that justifies the extraction.
   - Do NOT paraphrase or hallucinate text that is not present in the input.

Output strictly valid JSON with this schema:
{
  "nonline_allocation": "proportional" | "shipping_funder" | "platform_absorbs" | "discount_funder" | "unknown",
  "commission_treatment": "retained" | "full" | "proportional" | "unknown",
  "recovery_order": ["account_id", ...],
  "funding_map": {"shipping": "...", "platform": "...", "discount": "..."},
  "principal_bearer_verified": true | false,
  "abstain": true | false,
  "abstain_reason": "none" | "conflicting" | "ambiguous" | "missing" | "unsupported" | "role_binding_conflict",
  "spans": {
     "nonline_allocation": "verbatim quoted text",
     "commission_treatment": "verbatim quoted text",
     "recovery_order": "verbatim quoted text"
  },
  "role_binding_spans": {
     "shipping": "verbatim quoted text",
     "platform": "verbatim quoted text",
     "discount": "verbatim quoted text"
  }
}
"""


class LLMExtractor:
    """
    LLM-powered rule extractor that processes natural language clauses into StructuredRule.
    Enforces strict source-span validation against raw input text.
    """

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or MockLLMClient()

    def extract(self, agreement_text: str) -> StructuredRule:
        """
        Extract a StructuredRule from agreement_text using the configured LLM client.
        All spans are verified to exist verbatim in agreement_text.
        """
        raw = self.client.generate_structured(SYSTEM_PROMPT, agreement_text)
        return self._parse_and_validate(raw, agreement_text)

    def _parse_and_validate(self, raw: dict[str, Any], agreement_text: str) -> StructuredRule:
        # Check abstention
        abstain = bool(raw.get("abstain", False))
        reason_str = str(raw.get("abstain_reason", "none")).lower()
        try:
            abstain_reason = AbstainReason(reason_str)
        except ValueError:
            abstain_reason = AbstainReason.unsupported if abstain else AbstainReason.none

        # Parse enums
        try:
            nonline = NonlineAllocation(str(raw.get("nonline_allocation", "unknown")).lower())
        except ValueError:
            nonline = NonlineAllocation.unknown

        try:
            commission = CommissionTreatment(str(raw.get("commission_treatment", "unknown")).lower())
        except ValueError:
            commission = CommissionTreatment.unknown

        recovery_raw = raw.get("recovery_order") or []
        recovery_order = tuple(str(x) for x in recovery_raw if str(x).strip())

        funding_map_raw = raw.get("funding_map") or {}
        funding_map: dict[str, str] = {str(k).lower(): str(v) for k, v in funding_map_raw.items()}

        principal_bearer_verified = bool(raw.get("principal_bearer_verified", True))

        # Validate spans
        raw_spans = raw.get("spans") or {}
        validated_spans: dict[str, SourceSpan] = {}
        for field_name, span_text in raw_spans.items():
            if not span_text or not isinstance(span_text, str):
                continue
            idx = agreement_text.find(span_text)
            if idx == -1:
                # Hallucinated or non-verbatim span: safety violation
                raise ExtractionError(
                    f"INVALID_EXTRACTION: Field '{field_name}' cited ungrounded span: '{span_text}'"
                )
            span = SourceSpan(
                field_name=field_name,
                text=span_text,
                start=idx,
                end=idx + len(span_text),
            )
            assert span.validate(agreement_text)
            validated_spans[field_name] = span

        # Validate role binding spans
        raw_role_spans = raw.get("role_binding_spans") or {}
        validated_role_spans: dict[str, SourceSpan] = {}
        for role, span_text in raw_role_spans.items():
            if not span_text or not isinstance(span_text, str):
                continue
            idx = agreement_text.find(span_text)
            if idx == -1:
                raise ExtractionError(
                    f"INVALID_EXTRACTION: Role '{role}' cited ungrounded span: '{span_text}'"
                )
            span = SourceSpan(
                field_name=f"role_binding_{role}",
                text=span_text,
                start=idx,
                end=idx + len(span_text),
            )
            assert span.validate(agreement_text)
            validated_role_spans[role] = span

        # If abstaining, clear operative funding map
        effective_funding_map = None if (abstain or not funding_map) else funding_map

        return StructuredRule(
            nonline_allocation=nonline,
            commission_treatment=commission,
            recovery_order=recovery_order,
            funding_map=effective_funding_map,
            principal_bearer_verified=principal_bearer_verified,
            abstain=abstain,
            abstain_reason=abstain_reason,
            spans=validated_spans,
            role_binding_spans=validated_role_spans,
        )


class HybridExtractor:
    """
    Tier-B/C Hybrid Extractor:
    1. Runs fast canonical regex extractor first.
    2. If regex produces an unambiguous known rule with no conflict, uses it.
    3. If regex returns unknown nonline or detects natural language variation, falls back to LLMExtractor.
    """

    def __init__(self, llm_extractor: Optional[LLMExtractor] = None):
        self.llm_extractor = llm_extractor or LLMExtractor()

    def extract(self, agreement_text: str) -> StructuredRule:
        regex_rule = extract_regex(agreement_text)

        # Conditions where regex suffices:
        # - Not abstained
        # - nonline_allocation is definitively known (not unknown)
        # - no amendment override conflict occurred
        is_canonical_clean = (
            not regex_rule.abstain
            and regex_rule.nonline_allocation != NonlineAllocation.unknown
            and "AMENDMENT:" not in agreement_text
            and "Section 4.2" not in agreement_text
            and "overrides Master" not in agreement_text
        )

        if is_canonical_clean:
            return regex_rule

        # Delegate complex / non-canonical / amended clauses to LLM extractor
        return self.llm_extractor.extract(agreement_text)
