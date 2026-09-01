"""
Extraction-side data models.

These types are used by the predictor (extractor.py, allocator.py).
They are intentionally separate from benchmark.models to prevent leakage
of hidden benchmark types into the predictor boundary.

CommissionTreatment here is the extractor's canonical enum, which adds
``unknown`` to the benchmark's three-value set.  It is NOT re-exported
from benchmark.models to keep the import boundary clean.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class NonlineAllocation(Enum):
    """Governing rule for refund amounts not attributable to order lines."""

    proportional    = "proportional"
    shipping_funder = "shipping_funder"
    platform_absorbs = "platform_absorbs"   # includes "platform fee funder" phrasing
    discount_funder = "discount_funder"
    unknown         = "unknown"             # not found in or not parseable from text


class CommissionTreatment(Enum):
    """
    How the merchant commission component is handled on refund.

    Canonical extractor enum — adds ``unknown`` to the three benchmark values.
    ``unknown`` means the clause did not contain extractable commission language.
    """

    proportional = "proportional"   # commission returned proportionally
    full         = "full"           # commission returned in full
    retained     = "retained"       # commission not returned
    unknown      = "unknown"        # not found in or not parseable from text


class AbstainReason(Enum):
    """Why the extractor chose to abstain rather than return a structured rule."""

    none                 = "none"
    ambiguous            = "ambiguous"            # internally ambiguous clause
    conflicting          = "conflicting"           # two contradictory values for the same field
    missing              = "missing"               # required information absent
    unsupported          = "unsupported"           # phrasing present but not in supported vocabulary
    role_binding_conflict = "role_binding_conflict" # one role asserted to two different accounts


@dataclass(frozen=True)
class SourceSpan:
    """
    Exact positional reference to the substring that produced an extracted value.

    Validation is mandatory before returning a StructuredRule.
    """

    field_name: str
    text: str    # exact substring
    start: int   # inclusive
    end: int     # exclusive

    def validate(self, agreement_text: str) -> bool:
        """Return True iff agreement_text[start:end] == text."""
        return (
            0 <= self.start
            and self.start <= self.end
            and self.end <= len(agreement_text)
            and agreement_text[self.start : self.end] == self.text
        )


@dataclass(frozen=True)
class StructuredRule:
    """
    Structured representation of the governing refund/clawback rule.

    Produced by:
      - extractor.extract(agreement_text)  → R2 path; funding_map populated when
        canonical role-binding clause is present, else None.
      - oracle_rule.oracle_rule(case)      → R1 path; funding_map from hidden case.
      - default_rule(obs)                  → R0 path; wrong assumptions, funding_map None.

    The predictor allocator (allocator.py) accepts this type.
    The oracle resolver (groundtruth.py) does NOT accept this type — it is the answer key.

    funding_map:
        Single source of truth for role → account_id bindings.
        For the oracle path: populated from the hidden GroundTruthCase.funding_map.
        For the extractor path: populated from role_binding_spans after conflict
        resolution; None if no canonical binding clause found or if abstaining.
        For the R0 (default) path: always None.

    spans:
        Maps field_name → SourceSpan for every field whose value was extracted
        from text (i.e. not unknown and not oracle-supplied).
        All spans are positionally validated before the StructuredRule is returned.

    role_binding_spans:
        Maps role_name → SourceSpan for each role-to-account binding found in
        the agreement text.  Provenance record only; operative value is funding_map.
        Defaults to empty dict so all existing R0/R1 construction paths are unchanged.
    """

    nonline_allocation:        NonlineAllocation
    commission_treatment:      CommissionTreatment
    recovery_order:            tuple[str, ...]
    funding_map:               Mapping[str, str] | None
    principal_bearer_verified: bool
    abstain:                   bool
    abstain_reason:            AbstainReason
    spans:                     Mapping[str, SourceSpan]
    role_binding_spans:        Mapping[str, SourceSpan] = field(default_factory=dict)


class ExtractionError(Exception):
    """Raised when source-span positional validation fails."""
    pass


# ── Role binding failure categories (Tier-C) ──────────────────────────────────

class TierCFailureCategory(Enum):
    """
    Qualitative failure-mode category for Tier-C natural-language extraction.

    Assigned per-clause in tier_c_dataset.py and used by experiments/run_tier_c.py
    to produce a per-category failure count (not a top-line accuracy number).

    canonical_succeeds:     Regex correctly handles this clause (control).
    synonym_variation:      Phrasing synonym for a known concept; regex fails.
    passive_voice:          Passive / inverted sentence structure; regex fails.
    negation:               Negated or conditional statement; regex fails.
    multi_clause_precedence: Rule stated in multiple clauses with override logic.
    amendment_conflict:     Amendment clause changes an earlier base clause.
    """

    canonical_succeeds      = "canonical_succeeds"
    synonym_variation       = "synonym_variation"
    passive_voice           = "passive_voice"
    negation                = "negation"
    multi_clause_precedence = "multi_clause_precedence"
    amendment_conflict      = "amendment_conflict"
