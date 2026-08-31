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

    none        = "none"
    ambiguous   = "ambiguous"       # internally ambiguous clause
    conflicting = "conflicting"     # two contradictory values for the same field
    missing     = "missing"         # required information absent
    unsupported = "unsupported"     # phrasing present but not in supported vocabulary


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
      - extractor.extract(agreement_text)  → R2 path; funding_map always None
      - oracle_rule.oracle_rule(case)      → R1 path; funding_map from hidden case
      - default_rule(obs)                  → R0 path; wrong assumptions, funding_map None

    The predictor allocator (allocator.py) accepts this type.
    The oracle resolver (groundtruth.py) does NOT accept this type — it is the answer key.

    funding_map:
        For the oracle path, populated from the hidden GroundTruthCase.funding_map.
        For the extractor path, None unless the agreement text explicitly names
        the funding account (e.g. "borne by <account_id>").
        For the R0 (default) path, always None.

    spans:
        Maps field_name → SourceSpan for every field whose value was extracted
        from text (i.e. not unknown and not oracle-supplied).
        All spans are positionally validated before the StructuredRule is returned.
    """

    nonline_allocation:        NonlineAllocation
    commission_treatment:      CommissionTreatment
    recovery_order:            tuple[str, ...]
    funding_map:               Mapping[str, str] | None
    principal_bearer_verified: bool
    abstain:                   bool
    abstain_reason:            AbstainReason
    spans:                     Mapping[str, SourceSpan]


class ExtractionError(Exception):
    """Raised when source-span positional validation fails."""
    pass
