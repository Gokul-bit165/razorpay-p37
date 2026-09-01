"""
Deterministic Tier-B / Phase-3 rule extractor.

Converts agreement text into a StructuredRule using deterministic pattern
matching only.  No LLM, no embeddings, no external API, no hidden benchmark
state is accessed.

Supported phrase vocabulary
--------------------------
Tier-B canonical extraction (full table in docs/DETERMINISTIC_EXTRACTION_TIER_B.md):

  Non-line refund rule:
    "proportional"             → NonlineAllocation.proportional
    "shipping funder"          → NonlineAllocation.shipping_funder
    "platform absorbs"         → NonlineAllocation.platform_absorbs
    "platform fee funder"      → NonlineAllocation.platform_absorbs
    "discount funder"          → NonlineAllocation.discount_funder

  Commission treatment:
    "Commission is retained on refunds."     → CommissionTreatment.retained
    "Commission retained."                   → CommissionTreatment.retained
    "Commission is returned proportionally." → CommissionTreatment.proportional
    "Commission is returned in full."        → CommissionTreatment.full
    "Full commission returned on refunds."   → CommissionTreatment.full

  Recovery order:
    "Recovery order: X then Y."              → ("X", "Y")

  Principal bearer:
    All four standard lines present          → principal_bearer_verified = True

Phase-3 role-binding extraction (canonical scope only):
    Pattern: "Funding account: <account_id> is designated <role>."
    Roles:   shipping, platform, discount

    SCOPE: This pattern family covers the same tier of canonical phrasing as the
    Tier-B vocabulary above.  It is designed to bind roles to account IDs when
    the benchmark-generated agreement text contains an explicit designation clause.
    It does NOT claim to handle natural legal text variation (synonyms, passive voice,
    multi-clause amendments) — Tier-C is built specifically to demonstrate those
    failures.  See docs/DETERMINISTIC_EXTRACTION_TIER_B.md and tier_c_dataset.py.

    Conflict policy:
      - One role → two different accounts: abstain (AbstainReason.role_binding_conflict)
      - Two roles → same account: allowed (multi-role account is legitimate)
      - Same role → same account twice: deduplicate silently
      - Amendment header ("Amendment:" / "AMENDMENT:") overrides earlier binding
        for the same role (last amendment wins for that role; first-mention for
        non-amendment clauses).

    Abstention on conflict blocks the entire rule (abstain=True).
    Missing binding (no clause found) → funding_map=None, rule is valid;
    allocator then returns Prediction(abstained=True, reason_code="funding_map_unavailable").

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

# Role-binding canonical pattern (Phase-3, Tier-B-equivalent canonical scope).
# Matches: "Funding account: <account_id> is designated <role>."
# Amendment header on the same or preceding non-empty line triggers
# last-amendment-wins override for that role.
_ROLE_BINDING_RE = re.compile(
    r"Funding account:\s+(\S+)\s+is designated\s+(shipping|platform|discount)\b[^\n]*",
    re.IGNORECASE,
)
_AMENDMENT_HEADER_RE = re.compile(r"AMENDMENT:", re.IGNORECASE)

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
    nonline, _nonline_abstain = _extract_nonline(agreement_text, spans)

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
            role_binding_spans={},
        )

    # ── Recovery order ────────────────────────────────────────────────────────
    recovery_order = _extract_recovery_order(agreement_text, spans)

    # ── Principal bearer verification ─────────────────────────────────────────
    principal_verified = all(ln in agreement_text for ln in _PRINCIPAL_REQUIRED_LINES)

    # ── Role bindings (Phase-3) ───────────────────────────────────────────────
    funding_map, rb_spans, rb_abstain, rb_reason = _extract_role_bindings(agreement_text)
    if rb_abstain:
        return StructuredRule(
            nonline_allocation=NonlineAllocation.unknown,
            commission_treatment=CommissionTreatment.unknown,
            recovery_order=(),
            funding_map=None,
            principal_bearer_verified=False,
            abstain=True,
            abstain_reason=rb_reason,
            spans={},
            role_binding_spans={},
        )

    # ── Source span validation ────────────────────────────────────────────────
    for field_name, span in spans.items():
        if not span.validate(agreement_text):
            raise ExtractionError(
                f"INVALID_EXTRACTION: span for field '{field_name}' "
                f"at [{span.start}:{span.end}] does not match "
                f"agreement_text[{span.start}:{span.end}]"
            )
    for role, span in rb_spans.items():
        if not span.validate(agreement_text):
            raise ExtractionError(
                f"INVALID_EXTRACTION: role_binding span for role '{role}' "
                f"at [{span.start}:{span.end}] does not match agreement_text slice"
            )

    return StructuredRule(
        nonline_allocation=nonline,
        commission_treatment=commission,
        recovery_order=tuple(recovery_order),
        funding_map=funding_map if funding_map else None,
        principal_bearer_verified=principal_verified,
        abstain=False,
        abstain_reason=AbstainReason.none,
        spans=spans,
        role_binding_spans=rb_spans,
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


def _extract_role_bindings(
    text: str,
) -> tuple[dict[str, str] | None, dict[str, SourceSpan], bool, AbstainReason]:
    """
    Extract canonical role-to-account bindings from agreement text.

    Pattern: "Funding account: <account_id> is designated <role>."
    Roles:   shipping, platform, discount

    Returns (funding_map, role_binding_spans, abstain, abstain_reason).

    Conflict policy (D2):
      - One role -> two different accounts: abstain with role_binding_conflict.
      - Two roles -> same account: allowed.
      - Same role -> same account twice: deduplicate silently.
      - Lines where the same or immediately preceding non-empty line contains
        AMENDMENT: cause last-amendment-wins override for that role only.
    """
    lines = text.splitlines()

    # Compute line start character offsets for amendment-context lookup.
    line_start_offsets: list[int] = []
    offset = 0
    for ln in lines:
        line_start_offsets.append(offset)
        offset += len(ln) + 1  # +1 for newline

    def _is_amendment_context(match_start: int) -> bool:
        """True if the match's line or previous non-empty line contains AMENDMENT:."""
        match_line_idx = 0
        for i, ls in enumerate(line_start_offsets):
            if ls <= match_start:
                match_line_idx = i
            else:
                break
        if _AMENDMENT_HEADER_RE.search(lines[match_line_idx]):
            return True
        for i in range(match_line_idx - 1, -1, -1):
            if lines[i].strip():
                return _AMENDMENT_HEADER_RE.search(lines[i]) is not None
        return False

    # Gather all binding matches in document order.
    # Each entry: (role, account_id, start, end, matched_text, is_amendment)
    binding_matches: list[tuple[str, str, int, int, str, bool]] = []
    for m in _ROLE_BINDING_RE.finditer(text):
        account_id = m.group(1)
        role = m.group(2).lower()
        is_amend = _is_amendment_context(m.start())
        binding_matches.append((role, account_id, m.start(), m.end(), m.group(0), is_amend))

    if not binding_matches:
        return None, {}, False, AbstainReason.none

    # Resolve with amendment-override and conflict detection.
    role_to_account: dict[str, str] = {}
    role_to_span: dict[str, SourceSpan] = {}
    role_to_is_amendment: dict[str, bool] = {}

    for role, account_id, start, end, matched_text, is_amend in binding_matches:
        span = SourceSpan(field_name=f"role_{role}", text=matched_text, start=start, end=end)
        if role not in role_to_account:
            # First mention: accept regardless of amendment status.
            role_to_account[role] = account_id
            role_to_span[role] = span
            role_to_is_amendment[role] = is_amend
        else:
            if account_id == role_to_account[role]:
                # Same role, same account: idempotent, skip.
                continue
            # Same role, different account.
            if is_amend:
                # Amendment overrides existing binding for this role.
                role_to_account[role] = account_id
                role_to_span[role] = span
                role_to_is_amendment[role] = True
            else:
                # Non-amendment conflict: abstain.
                return None, {}, True, AbstainReason.role_binding_conflict

    return dict(role_to_account), dict(role_to_span), False, AbstainReason.none
