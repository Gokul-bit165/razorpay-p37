"""
Deterministic Tier-B rule extractor.

Converts agreement text into a StructuredRule using deterministic pattern
matching only.  No LLM, no embeddings, no external API, no hidden benchmark
state is accessed.

Supported phrase vocabulary (full normalization table in
docs/DETERMINISTIC_EXTRACTION_TIER_B.md):

  Non-line refund rule:
    "proportional"             → NonlineAllocation.proportional
    "shipping funder"          → NonlineAllocation.shipping_funder
    "platform absorbs"         → NonlineAllocation.platform_absorbs
    "platform fee funder"      → NonlineAllocation.platform_absorbs
    "discount funder"          → NonlineAllocation.discount_funder

  Commission treatment:
    "Commission is retained on refunds."  → CommissionTreatment.retained
    "Commission retained."                → CommissionTreatment.retained
    "Commission is returned proportionally." → CommissionTreatment.proportional
    "Commission is returned in full."     → CommissionTreatment.full
    "Full commission returned on refunds."→ CommissionTreatment.full

  Recovery order:
    "Recovery order: X then Y."          → ("X", "Y")

  Principal bearer:
    All four standard lines present      → principal_bearer_verified = True

Source span validation:
  For every extracted field, the exact substring position is recorded and
  validated: agreement_text[span.start:span.end] == span.text.
  An invalid span raises ExtractionError("INVALID_EXTRACTION").
"""
from __future__ import annotations

import re
from typing import Optional

from .models import (
    AbstainReason,
    CommissionTreatment,
    ExtractionError,
    NonlineAllocation,
    SourceSpan,
    StructuredRule,
)

# ── Pattern tables ────────────────────────────────────────────────────────────

# Each entry: (compiled regex matching the canonical phrase, enum value)
_NONLINE_PATTERNS: list[tuple[re.Pattern, NonlineAllocation]] = [
    (re.compile(r"platform fee funder", re.I), NonlineAllocation.platform_absorbs),
    (re.compile(r"platform absorbs",    re.I), NonlineAllocation.platform_absorbs),
    (re.compile(r"shipping funder",     re.I), NonlineAllocation.shipping_funder),
    (re.compile(r"discount funder",     re.I), NonlineAllocation.discount_funder),
    (re.compile(r"\bproportional\b",    re.I), NonlineAllocation.proportional),
]
# platform_fee_funder must be checked before platform_absorbs (longer match first)

_COMMISSION_PATTERNS: list[tuple[re.Pattern, CommissionTreatment]] = [
    (
        re.compile(r"commission\s+is\s+retained\s+on\s+refunds", re.I),
        CommissionTreatment.retained,
    ),
    (
        re.compile(r"commission\s+retained", re.I),
        CommissionTreatment.retained,
    ),
    (
        re.compile(r"commission\s+is\s+returned\s+proportionally", re.I),
        CommissionTreatment.proportional,
    ),
    (
        re.compile(r"commission\s+is\s+returned\s+in\s+full", re.I),
        CommissionTreatment.full,
    ),
    (
        re.compile(r"full\s+commission\s+returned", re.I),
        CommissionTreatment.full,
    ),
]

_NONLINE_LINE_RE = re.compile(
    r"Non-line refund rule:\s+(.+?)\.?\s*$", re.MULTILINE
)
_RECOVERY_LINE_RE = re.compile(
    r"Recovery order:\s+(.+?)\.?\s*$", re.MULTILINE
)

_PRINCIPAL_REQUIRED_LINES = (
    "Goods: refund bears with the fulfilling vendor.",
    "Shipping: refund bears with the shipping-funding party.",
    "Platform fee: refund bears with the platform.",
    "Discount adjustments: refund bears with the party that funded the discount.",
)


# ── Public interface ──────────────────────────────────────────────────────────

def extract(agreement_text: str) -> StructuredRule:
    """
    Parse ``agreement_text`` and return a StructuredRule.

    Raises ExtractionError if a source-span positional check fails.
    Returns a StructuredRule with abstain=True on detected conflicts.
    Returns unknown values for fields not found in the text.
    """
    spans: dict[str, SourceSpan] = {}

    # ── Nonline allocation ────────────────────────────────────────────────────
    nonline, nonline_abstain = _extract_nonline(agreement_text, spans)

    # ── Commission treatment ──────────────────────────────────────────────────
    commission, comm_abstain, comm_reason = _extract_commission(agreement_text, spans)

    if comm_abstain:
        return StructuredRule(
            nonline_allocation=NonlineAllocation.unknown,
            commission_treatment=CommissionTreatment.unknown,
            recovery_order=(),
            funding_map=None,
            principal_bearer_verified=False,
            abstain=True,
            abstain_reason=comm_reason,
            spans={},
        )

    # ── Recovery order ────────────────────────────────────────────────────────
    recovery_order = _extract_recovery_order(agreement_text, spans)

    # ── Principal bearer verification ─────────────────────────────────────────
    principal_verified = all(ln in agreement_text for ln in _PRINCIPAL_REQUIRED_LINES)

    # ── Source span validation ────────────────────────────────────────────────
    for field_name, span in spans.items():
        if not span.validate(agreement_text):
            raise ExtractionError(
                f"INVALID_EXTRACTION: span for field '{field_name}' "
                f"at [{span.start}:{span.end}] does not match "
                f"agreement_text[{span.start}:{span.end}]"
            )

    return StructuredRule(
        nonline_allocation=nonline,
        commission_treatment=commission,
        recovery_order=tuple(recovery_order),
        funding_map=None,
        principal_bearer_verified=principal_verified,
        abstain=False,
        abstain_reason=AbstainReason.none,
        spans=spans,
    )


# ── Private helpers ───────────────────────────────────────────────────────────

def _extract_nonline(
    text: str,
    spans: dict[str, SourceSpan],
) -> tuple[NonlineAllocation, bool]:
    """Return (value, abstain).  Writes span into spans on success."""
    m = _NONLINE_LINE_RE.search(text)
    if not m:
        return NonlineAllocation.unknown, False

    phrase = m.group(1).strip().rstrip(".")
    matched_value = NonlineAllocation.unknown

    for phrase_re, value in _NONLINE_PATTERNS:
        if phrase_re.search(phrase):
            matched_value = value
            break

    if matched_value != NonlineAllocation.unknown:
        raw = text[m.start() : m.end()].rstrip()
        spans["nonline_allocation"] = SourceSpan(
            field_name="nonline_allocation",
            text=raw,
            start=m.start(),
            end=m.start() + len(raw),
        )

    return matched_value, False


def _extract_commission(
    text: str,
    spans: dict[str, SourceSpan],
) -> tuple[CommissionTreatment, bool, AbstainReason]:
    """
    Return (value, should_abstain, abstain_reason).
    Writes span into spans on success.

    Conflict detection: if two different enum values are matched, abstain.
    Multiple matches for the same value are not a conflict.
    """
    matches: list[tuple[CommissionTreatment, int, int, str]] = []

    for pattern, value in _COMMISSION_PATTERNS:
        m = pattern.search(text)
        if m:
            matches.append((value, m.start(), m.end(), m.group(0)))

    if not matches:
        return CommissionTreatment.unknown, False, AbstainReason.none

    # Deduplicate by value to detect genuine conflicts
    unique_values = {v for v, *_ in matches}
    if len(unique_values) > 1:
        return CommissionTreatment.unknown, True, AbstainReason.conflicting

    # Use the first match's span
    value, start, end, matched_text = matches[0]
    spans["commission_treatment"] = SourceSpan(
        field_name="commission_treatment",
        text=matched_text,
        start=start,
        end=end,
    )
    return value, False, AbstainReason.none


def _extract_recovery_order(
    text: str,
    spans: dict[str, SourceSpan],
) -> list[str]:
    """Extract ordered account list from 'Recovery order: X then Y.' line."""
    m = _RECOVERY_LINE_RE.search(text)
    if not m:
        return []

    order_text = m.group(1).strip().rstrip(".")
    accounts = [
        tok.strip().rstrip(".")
        for tok in re.split(r"\s+then\s+", order_text)
        if tok.strip()
    ]

    if accounts:
        raw = text[m.start() : m.end()].rstrip()
        spans["recovery_order"] = SourceSpan(
            field_name="recovery_order",
            text=raw,
            start=m.start(),
            end=m.start() + len(raw),
        )

    return accounts
