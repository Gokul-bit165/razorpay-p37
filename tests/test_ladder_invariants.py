"""
Tests for Benchmark Ladder Invariants across all regimes (T2.1).

INVARIANTS:
1. Within any single case set, no predictor may exceed the R1 Oracle ceiling.
2. Full sample size is 140; stratified subsample size is 40.
3. Diagnostic counters are non-negative integers.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

_RESULTS_DIR = Path(__file__).resolve().parents[1] / "experiments" / "results"


@pytest.mark.parametrize("regime", ["a", "b", "c"])
def test_regime_ladder_invariants(regime: str):
    json_path = _RESULTS_DIR / f"ladder_regime_{regime}.json"
    assert json_path.exists(), f"Ladder results file missing: {json_path}"

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["full_sample_size"] == 140
    assert data["stratified_subsample_size"] == 40

    # 1. Invariants on Full 140
    m_full = data["metrics_full_140"]
    r1_full = m_full["r1_oracle_correct"]
    assert m_full["r0_default_correct"] <= r1_full, f"Regime {regime} Full 140: R0 > R1"
    assert m_full["r2_regex_correct"] <= r1_full, f"Regime {regime} Full 140: R2 > R1"
    assert m_full["r0_default_accuracy"] <= m_full["r1_oracle_accuracy"]
    assert m_full["r2_regex_accuracy"] <= m_full["r1_oracle_accuracy"]

    # 2. Invariants on Stratified Subsample 40
    m_sub = data["metrics_subsample_40"]
    r1_sub = m_sub["r1_oracle_correct"]
    assert m_sub["r0_default_correct"] <= r1_sub, f"Regime {regime} Subsample: R0 > R1"
    assert m_sub["r2_regex_correct"] <= r1_sub, f"Regime {regime} Subsample: R2 > R1"
    assert m_sub["r3_llm_correct"] <= r1_sub, f"Regime {regime} Subsample: R3 > R1"
    assert m_sub["r3_confirmed_correct"] <= r1_sub, f"Regime {regime} Subsample: R3-Confirmed > R1"

    assert m_sub["r0_default_accuracy"] <= m_sub["r1_oracle_accuracy"]
    assert m_sub["r2_regex_accuracy"] <= m_sub["r1_oracle_accuracy"]
    assert m_sub["r3_llm_accuracy"] <= m_sub["r1_oracle_accuracy"]
    assert m_sub["r3_confirmed_accuracy"] <= m_sub["r1_oracle_accuracy"]

    # 3. Diagnostic counts
    assert m_sub["r3_span_validation_rejections"] >= 0
    assert m_sub["r3_json_parse_failures"] >= 0
    assert m_sub["r3_enum_violations"] >= 0
    assert m_sub["r3_abstain_count"] >= 0
