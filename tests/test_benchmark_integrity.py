from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p37.benchmark.generator import GenerationConfig, generate
from p37.benchmark.groundtruth import resolve
from p37.benchmark.project import observable_to_json, project
from p37.benchmark.rounding import largest_remainder


def test_rounding_is_exact_and_deterministic():
    result = largest_remainder(100, [1, 1, 1], [3, 3, 3], ["a", "b", "c"])
    assert result == [34, 33, 33]
    assert sum(result) == 100


def test_projection_drops_hidden_structural_fields():
    case = generate(GenerationConfig({"D1_single_line_return": 1}, 7))[0]
    payload = observable_to_json(project(case))
    for hidden in ("funding_map", "true_fulfilling_account", "true_commission_treatment", "balance_timeline", "true_line_coverage", "true_reason", "case_type"):
        assert hidden not in payload


def test_true_state_is_reproducible():
    cfg = GenerationConfig({"A3_discount_funded": 3, "C2_commission_full_return": 3}, 77)
    a = [resolve(c) for c in generate(cfg)]
    b = [resolve(c) for c in generate(cfg)]
    assert a == b


def test_invalid_cases_resolve_as_unresolvable():
    types = ["N1_refund_exceeds_payment", "N2_refund_exceeds_transfers", "N3_closed_account", "N4_line_maps_to_multiple", "N5_reason_mislabelled"]
    cases = generate(GenerationConfig({t: 1 for t in types}, 91))
    assert all(resolve(c).unresolvable for c in cases)


def test_commission_divergence_is_present():
    cases = generate(GenerationConfig({"C1_commission_retained": 2, "C2_commission_full_return": 2}, 101))
    assert all(not resolve(c).unresolvable for c in cases)
    assert any(any(a.commission_alloc_paise > 0 for a in r.allocations.values()) for r in map(resolve, cases) if r.allocations)
