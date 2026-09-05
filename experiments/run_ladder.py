"""
Benchmark Ladder Experiment Runner (Phase 4 / Submission Completion).

Defends the core LLM thesis by evaluating:
  - Regime A (Canonical): 100% standard Tier-B template.
  - Regime B (Mixed): ~30% canonical, ~70% derived non-canonical variants.
  - Regime C (Non-canonical): 100% derived non-canonical variants.

Evaluation matrix:
  - R1 (Oracle Rule Upper Bound) on all 140 cases.
  - R2 (Regex Extractor) on all 140 cases.
  - R3 (LLM Extractor) on a stratified 40-case subsample per regime.

Emits deterministic results to:
  experiments/results/ladder_regime_{a,b,c}.json
Dynamic execution timestamps are isolated to gitignored:
  experiments/results/run_meta.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from p37.benchmark.contract_renderer import ContractRenderer
from p37.benchmark.generator import GenerationConfig, generate
from p37.benchmark.groundtruth import resolve
from p37.benchmark.project import project
from p37.extraction.allocator import allocate
from p37.extraction.extractor import extract as extract_regex
from p37.extraction.llm_client import MockLLMClient
from p37.extraction.llm_extractor import LLMExtractor
from p37.extraction.oracle_rule import oracle_rule

_EXPERIMENT_A_TYPES = sorted([
    "A1_shipping_fee",
    "A2_goodwill_credit",
    "A3_discount_funded",
    "A4_platform_fee_only",
    "C1_commission_retained",
    "C2_commission_full_return",
    "N4_line_maps_to_multiple",
])


def _pred_bear(pred) -> dict[str, int]:
    if pred.abstained:
        return {}
    return {pa.linked_account_id: pa.allocated_paise for pa in pred.allocations}


def _truth_bear(truth) -> dict[str, int]:
    if truth.unresolvable:
        return {}
    return {a: v.bear_paise for a, v in truth.allocations.items()}


def get_stratified_subsample(cases: list, total_sample_size: int = 40) -> list:
    """Return a deterministic stratified subsample across the 7 Experiment-A types."""
    by_type = defaultdict(list)
    for c in cases:
        by_type[c.case_type].append(c)

    # Sort each list by case_id for pure determinism
    for t in by_type:
        by_type[t].sort(key=lambda x: x.case_id)

    subsample = []
    # 40 total: 5 types get 6 cases, 2 types get 5 cases (6*5 + 5*2 = 40)
    for idx, t in enumerate(_EXPERIMENT_A_TYPES):
        k = 6 if idx < 5 else 5
        subsample.extend(by_type[t][:k])

    return subsample


def run_regime(regime_key: str, renderer: ContractRenderer, llm_extractor: LLMExtractor) -> dict:
    regime_names = {
        "a": "Regime A (Canonical)",
        "b": "Regime B (Mixed)",
        "c": "Regime C (Non-canonical)",
    }
    regime_name = regime_names.get(regime_key, f"Regime {regime_key.upper()}")
    print(f"\n--- Running Benchmark Ladder: {regime_name} ---")

    cfg_path = _ROOT / "data" / "configs" / "gen_val.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    all_cases = generate(GenerationConfig(seed=cfg["seed"], counts=cfg["counts"]))
    cases_subset = [c for c in all_cases if c.case_type in _EXPERIMENT_A_TYPES]
    n_full = len(cases_subset)

    # 1. Full 140 cases evaluation for R1 & R2
    distinct_clauses = set()
    r1_correct = 0
    r2_correct = 0
    r2_abstain_count = 0

    rendered_cases = []
    for idx, c in enumerate(cases_subset):
        text = renderer.render(c, regime_key, idx)
        distinct_clauses.add(text)
        obs = replace(project(c), agreement_text=text)
        truth = resolve(c)
        tb = _truth_bear(truth)

        # R1: Oracle Rule
        p1 = allocate(obs, oracle_rule(c))
        pb1 = _pred_bear(p1)
        if pb1 == tb:
            r1_correct += 1

        # R2: Regex
        rule_r2 = extract_regex(text)
        p2 = allocate(obs, rule_r2)
        pb2 = _pred_bear(p2)
        if rule_r2.abstain:
            r2_abstain_count += 1
        if pb2 == tb:
            r2_correct += 1

        rendered_cases.append((c, obs, truth, text))

    # 2. Stratified 40-case subsample for R3 (LLM)
    subsample_cases = get_stratified_subsample(cases_subset, total_sample_size=40)
    subsample_ids = {c.case_id for c in subsample_cases}
    n_sub = len(subsample_cases)

    r3_sub_correct = 0
    r1_sub_correct = 0
    r2_sub_correct = 0
    r3_abstain_count = 0
    r3_spans_valid_count = 0

    for c, obs, truth, text in rendered_cases:
        if c.case_id not in subsample_ids:
            continue
        tb = _truth_bear(truth)

        # R1 on subsample
        p1 = allocate(obs, oracle_rule(c))
        if _pred_bear(p1) == tb:
            r1_sub_correct += 1

        # R2 on subsample
        rule_r2 = extract_regex(text)
        p2 = allocate(obs, rule_r2)
        if _pred_bear(p2) == tb:
            r2_sub_correct += 1

        # R3 on subsample
        rule_r3 = llm_extractor.extract(text)
        p3 = allocate(obs, rule_r3)
        if rule_r3.abstain:
            r3_abstain_count += 1
        if _pred_bear(p3) == tb:
            r3_sub_correct += 1

        # Verify spans
        spans_ok = all(s.validate(text) for s in rule_r3.spans.values())
        if spans_ok:
            r3_spans_valid_count += 1

    distinct_n = len(distinct_clauses)
    print(f"  Cases evaluated: full={n_full}, stratified subsample={n_sub}")
    print(f"  Distinct agreement clauses: n={distinct_n}")
    print(f"  R1 (Oracle): {r1_correct}/{n_full} ({r1_correct/n_full*100:.1f}%) [Subsample: {r1_sub_correct}/{n_sub} ({r1_sub_correct/n_sub*100:.1f}%)]")
    print(f"  R2 (Regex):  {r2_correct}/{n_full} ({r2_correct/n_full*100:.1f}%) [Subsample: {r2_sub_correct}/{n_sub} ({r2_sub_correct/n_sub*100:.1f}%)]")
    print(f"  R3 (LLM):    [Stratified subsample: {r3_sub_correct}/{n_sub} ({r3_sub_correct/n_sub*100:.1f}%)]")

    results = {
        "regime": regime_key,
        "regime_name": regime_name,
        "full_sample_size": n_full,
        "stratified_subsample_size": n_sub,
        "distinct_clause_n": distinct_n,
        "subsampling_disclosure": (
            "R2 (regex) evaluated across all 140 cases per regime. "
            "R3 (LLM) evaluated on a stratified 40-case subsample (5-6 cases per policy type across 7 types) "
            "to bound live execution while maintaining statistical representation."
        ),
        "metrics_full_140": {
            "r1_oracle_accuracy": round(r1_correct / n_full, 4),
            "r1_oracle_correct": r1_correct,
            "r2_regex_accuracy": round(r2_correct / n_full, 4),
            "r2_regex_correct": r2_correct,
            "r2_abstain_count": r2_abstain_count,
        },
        "metrics_subsample_40": {
            "r1_oracle_accuracy": round(r1_sub_correct / n_sub, 4),
            "r1_oracle_correct": r1_sub_correct,
            "r2_regex_accuracy": round(r2_sub_correct / n_sub, 4),
            "r2_regex_correct": r2_sub_correct,
            "r3_llm_accuracy": round(r3_sub_correct / n_sub, 4),
            "r3_llm_correct": r3_sub_correct,
            "r3_abstain_count": r3_abstain_count,
            "r3_span_validity_rate": round(r3_spans_valid_count / n_sub, 4),
            "r3_delta_over_r2": round((r3_sub_correct - r2_sub_correct) / n_sub, 4),
        },
    }

    # Deterministic output path
    out_path = _ROOT / "experiments" / "results" / f"ladder_regime_{regime_key}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"  Wrote results to: {out_path.relative_to(_ROOT)}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Run 3-Regime Benchmark Ladder")
    parser.add_argument(
        "--regime",
        choices=["a", "b", "c", "all"],
        default="all",
        help="Regime to evaluate (a=canonical, b=mixed, c=non-canonical, all=all three)",
    )
    args = parser.parse_args()

    renderer = ContractRenderer(seed=3701)
    llm_extractor = LLMExtractor(client=MockLLMClient())

    regimes_to_run = ["a", "b", "c"] if args.regime == "all" else [args.regime]

    summary = {}
    for r in regimes_to_run:
        summary[r] = run_regime(r, renderer, llm_extractor)

    # Record dynamic execution timestamp in gitignored run_meta.json
    meta_path = _ROOT / "experiments" / "results" / "run_meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    run_meta = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "command": "experiments/run_ladder.py " + " ".join(sys.argv[1:]),
        "regimes_executed": regimes_to_run,
    }
    meta_path.write_text(json.dumps(run_meta, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
