# Milestone Completion Log: Deterministic Extraction (Tier B)

**Milestone:** `milestone/deterministic-extraction-tier-b`  
**Date:** 2026-09-01  
**Status:** Completed & Fully Verified  

---

## 1. Executive Summary

This milestone evaluated whether a purely deterministic rule extractor (without LLMs or autonomous agents) could extract structured refund/clawback rules from clean, canonical contract text (Tier B) and recover the +57.14 percentage point allocation improvement demonstrated by the oracle rule (R1).

### Key Empirical Findings:
1. **Rule Extraction Accuracy: 100.0% (12/12)** across all canonical contract clauses (nonline rules, commission treatment, recovery ordering, principal verification).
2. **Safety & Abstention: 100.0%** on conflicting clauses; **0.0% hallucination** on adversarial/irrelevant legal text.
3. **Allocation Lift: +0.00 pp** over default baseline (R0).
4. **Root Cause Diagnosis:** The gap between extracted rules (R2) and oracle rules (R1) is **100% attributable to hidden transaction data** (`funding_map` mapping account IDs to roles like "shipping funder"), **not text comprehension**.

---

## 2. Artifacts & Codebase Additions

### Source Modules (`src/p37/extraction/`)
* [`models.py`](../src/p37/extraction/models.py): Canonical enums (`NonlineAllocation`, `CommissionTreatment`), `StructuredRule`, `SourceSpan`, `ExtractionResult`, `PredictorResolution`.
* [`allocator.py`](../src/p37/extraction/allocator.py): Predictor-side observable allocation engine using `largest_remainder` integer-paise arithmetic, rigorously isolated from hidden ground-truth state.
* [`extractor.py`](../src/p37/extraction/extractor.py): Regex-based deterministic extractor with span extraction, confidence scoring, and conflict detection.
* [`oracle_rule.py`](../src/p37/extraction/oracle_rule.py): Ground-truth oracle adapter that maps hidden true agreement state into `StructuredRule` for ceiling benchmarking.
* [`tier_b_dataset.py`](../src/p37/extraction/tier_b_dataset.py): Canonical 12-clause clean dataset and 5-clause safety/adversarial dataset mapped to validation cases.
* [`rule_impact_dataset.py`](../src/p37/extraction/rule_impact_dataset.py): 5 controlled scenarios isolating allocation behavior across distinct rule types.

### Test Suites (`tests/`)
* [`test_benchmark_integrity.py`](../tests/test_benchmark_integrity.py): 5 tests verifying ground truth generator, resolver, projection invariants, and zero-leakage boundaries.
* [`test_tier_b_extraction.py`](../tests/test_tier_b_extraction.py): 6 tests verifying clean extraction, span integrity, confidence scores, and rule impact allocations.
* [`test_tier_b_safety.py`](../tests/test_tier_b_safety.py): 4 tests verifying conflict abstention, safety sets, absence of hallucinations, and predictor-resolver 100% equivalence.

### Experiments & Evaluation (`experiments/`)
* [`run_tier_b.py`](../experiments/run_tier_b.py): End-to-end benchmark execution script evaluating extraction accuracy, safety metrics, ladder comparison (R0 vs R1 vs R2), and failure mode attribution.
* [`results/deterministic_tier_b.json`](../experiments/results/deterministic_tier_b.json): Complete machine-readable evaluation results across all 320 validation cases.

### Reports (`docs/`)
* [`DETERMINISTIC_EXTRACTION_TIER_B.md`](DETERMINISTIC_EXTRACTION_TIER_B.md): In-depth scientific findings, proofs of allocation inertness, and failure analysis.

---

## 3. Test & Verification Summary

Executed test command: `python -m pytest`
```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.0.2, pluggy-1.6.0
collected 15 items

tests\test_benchmark_integrity.py .....                                  [ 33%]
tests\test_tier_b_extraction.py ......                                   [ 73%]
tests\test_tier_b_safety.py ....                                         [100%]

============================= 15 passed in 0.79s ==============================
```

---

## 4. Benchmark Ladder Metrics (140 Divergent Cases)

| Predictor | Exact Match | Exact Match Rate | Wrong Allocation Rate |
|---|---|---|---|
| **R0 (Default Baseline)** | 40 / 140 | 28.57% | 71.43% |
| **R1 (Oracle Rule)** | 120 / 140 | 85.71% | 14.29% |
| **R2 (Deterministic Extraction)** | 40 / 140 | 28.57% | 71.43% |

* **Oracle Ceiling Improvement (R1 − R0):** +57.14 pp
* **Extracted Rule Improvement (R2 − R0):** +0.00 pp
* **Remaining Gap (R1 − R2):** +57.14 pp

---

## 5. Structural Proofs & Root Cause Attribution

1. **Missing Account Identifiers (80 / 140 failures):**
   * Agreement text states: `"Non-line refund rule: shipping funder."`
   * Text parsed successfully: `NonlineAllocation.shipping_funder`.
   * Allocation constraint: The observable case metadata contains account IDs `[acc_0, acc_1]` but does not identify which account is the shipping funder. Without `funding_map`, the predictor must abstain.
2. **Predictor Allocation Inertness:**
   * Proved that under observable constraints, `residual_for_commission == 0` because principal refund exhausts the total refund amount.
   * Proved that recovery ordering does not affect bearing totals across independent balance pools.
3. **Implication for AI / LLM Scope:**
   * An LLM cannot close this allocation gap because the missing information is not in the text.
   * The next necessary architectural evolution is enriching observable account metadata or integrating human-in-the-loop role confirmation.

---

## 6. Next Steps & Recommendations

1. **Merge to Main:** Merge `milestone/deterministic-extraction-tier-b` into `main`.
2. **Benchmark Schema Evolution:** Add observable account role metadata (e.g. `role: shipping_provider`) to allow extracted rules to bind to concrete accounts.
3. **Tier C Benchmark:** Evaluate complex/ambiguous phrasing to test where regex fails and LLMs become strictly necessary.
