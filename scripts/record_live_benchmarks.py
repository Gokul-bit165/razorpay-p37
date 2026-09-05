"""
Audited Live Gemini Benchmark Recorder (P37 Gate 1 / Path A).

Records live Gemini Flash inference calls for:
  1. Full Tier-C dataset (15 natural language boundary clauses)
  2. Regime C 40-case stratified subsample (100% non-canonical rendered text)
  3. Regime A & B 40-case stratified subsamples

Stores immutable transcripts in experiments/results/llm_transcripts/.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from p37.benchmark.contract_renderer import ContractRenderer
from p37.benchmark.generator import GenerationConfig, generate
from p37.benchmark.project import project
from p37.extraction.llm_client import create_llm_client
from p37.extraction.llm_extractor import LLMExtractor
from p37.extraction.tier_c_dataset import TIER_C_CLAUSES

_EXPERIMENT_A_TYPES = sorted([
    "A1_shipping_fee",
    "A2_goodwill_credit",
    "A3_discount_funded",
    "A4_platform_fee_only",
    "C1_commission_retained",
    "C2_commission_full_return",
    "N4_line_maps_to_multiple",
])


def get_stratified_subsample(cases: list, total_sample_size: int = 40) -> list:
    by_type = defaultdict(list)
    for c in cases:
        by_type[c.case_type].append(c)
    for t in by_type:
        by_type[t].sort(key=lambda x: x.case_id)
    subsample = []
    for idx, t in enumerate(_EXPERIMENT_A_TYPES):
        k = 6 if idx < 5 else 5
        subsample.extend(by_type[t][:k])
    return subsample


def record_all():
    print("=== P37 Audited Live Benchmark Recorder (Gemini Flash) ===")
    transcripts_dir = _ROOT / "experiments" / "results" / "llm_transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    client = create_llm_client(mode="record", cache_dir=transcripts_dir)
    extractor = LLMExtractor(client=client)

    # 1. Tier-C clauses (15 total)
    print(f"\n[1/4] Recording Tier-C Clauses (n={len(TIER_C_CLAUSES)}) ...")
    for i, clause in enumerate(TIER_C_CLAUSES, 1):
        t0 = time.perf_counter()
        try:
            rule = extractor.extract(clause.clause_text)
            elapsed = time.perf_counter() - t0
            print(f"  [{i:02d}/{len(TIER_C_CLAUSES):02d}] {clause.clause_id:<20} ({elapsed:.2f}s) nonline={rule.nonline_allocation.value} abstain={rule.abstain}")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"  [{i:02d}/{len(TIER_C_CLAUSES):02d}] {clause.clause_id:<20} ({elapsed:.2f}s) ERROR: {e}")

    # Load generator config & cases
    cfg_path = _ROOT / "data" / "configs" / "gen_val.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    all_cases = generate(GenerationConfig(seed=cfg["seed"], counts=cfg["counts"]))
    cases_subset = [c for c in all_cases if c.case_type in _EXPERIMENT_A_TYPES]
    subsample = get_stratified_subsample(cases_subset, total_sample_size=40)
    subsample_ids = {c.case_id for c in subsample}

    renderer = ContractRenderer(seed=3701)

    # 2. Regime C (40 cases) - Headline non-canonical regime
    print(f"\n[2/4] Recording Regime C Non-canonical Subsample (n=40) ...")
    regime_c_cases = []
    for idx, c in enumerate(cases_subset):
        if c.case_id in subsample_ids:
            text = renderer.render(c, "c", idx)
            regime_c_cases.append((c, text))

    for i, (c, text) in enumerate(regime_c_cases, 1):
        t0 = time.perf_counter()
        try:
            rule = extractor.extract(text)
            elapsed = time.perf_counter() - t0
            print(f"  [{i:02d}/{len(regime_c_cases):02d}] Case {c.case_id:<12} ({elapsed:.2f}s) nonline={rule.nonline_allocation.value} abstain={rule.abstain}")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"  [{i:02d}/{len(regime_c_cases):02d}] Case {c.case_id:<12} ({elapsed:.2f}s) ERROR: {e}")

    # 3. Regime A (40 cases)
    print(f"\n[3/4] Recording Regime A Canonical Subsample (n=40) ...")
    regime_a_cases = []
    for idx, c in enumerate(cases_subset):
        if c.case_id in subsample_ids:
            text = renderer.render(c, "a", idx)
            regime_a_cases.append((c, text))

    for i, (c, text) in enumerate(regime_a_cases, 1):
        t0 = time.perf_counter()
        try:
            rule = extractor.extract(text)
            elapsed = time.perf_counter() - t0
            print(f"  [{i:02d}/{len(regime_a_cases):02d}] Case {c.case_id:<12} ({elapsed:.2f}s) nonline={rule.nonline_allocation.value} abstain={rule.abstain}")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"  [{i:02d}/{len(regime_a_cases):02d}] Case {c.case_id:<12} ({elapsed:.2f}s) ERROR: {e}")

    # 4. Regime B (40 cases)
    print(f"\n[4/4] Recording Regime B Mixed Subsample (n=40) ...")
    regime_b_cases = []
    for idx, c in enumerate(cases_subset):
        if c.case_id in subsample_ids:
            text = renderer.render(c, "b", idx)
            regime_b_cases.append((c, text))

    for i, (c, text) in enumerate(regime_b_cases, 1):
        t0 = time.perf_counter()
        try:
            rule = extractor.extract(text)
            elapsed = time.perf_counter() - t0
            print(f"  [{i:02d}/{len(regime_b_cases):02d}] Case {c.case_id:<12} ({elapsed:.2f}s) nonline={rule.nonline_allocation.value} abstain={rule.abstain}")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"  [{i:02d}/{len(regime_b_cases):02d}] Case {c.case_id:<12} ({elapsed:.2f}s) ERROR: {e}")

    total_recorded = len(list(transcripts_dir.glob("*.json")))
    print(f"\n=== Recording Complete! Total transcripts in {transcripts_dir.relative_to(_ROOT)}: {total_recorded} ===")


if __name__ == "__main__":
    record_all()
