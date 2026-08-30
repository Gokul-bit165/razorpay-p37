from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class StructuredRule:
    principal_bearer: str = "fulfilling_account"
    nonline_allocation: str = "proportional"
    recovery_order: tuple[str, ...] = ()
    commission_treatment: Mapping[str, str] = None  # type: ignore[assignment]
    nonline_target_account: str | None = None

    def __post_init__(self):
        if self.commission_treatment is None:
            object.__setattr__(self, "commission_treatment", {})
