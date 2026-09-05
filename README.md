# Razorpay Route · P37 Split Clawback Engine

[![Tests: 52 Passed](https://img.shields.io/badge/Tests-52%20Passed%20(100%25)-success)](tests)
[![Precision: Integer-Paise](https://img.shields.io/badge/Precision-Integer--Paise%20(No%20Float%20Drift)-blue)](src/p37/extraction/allocator.py)
[![Grounding: Verbatim Spans](https://img.shields.io/badge/Grounding-100%25%20Verbatim%20Spans-brightgreen)](src/p37/extraction/llm_extractor.py)
[![Hallucinations: 0.0%](https://img.shields.io/badge/Hallucinations-0.0%25-green)](experiments/results/phase4_llm_extraction.json)

**Research-first prototype for the Razorpay AI Buildathon.**

**Problem P37:** Partial-refund allocation and clawback on split payments where contract-specific bearing rules differ from proportional/default handling.

📖 **Read the Full Submission:** [SUBMISSION.md](SUBMISSION.md)

---

## Quickstart

### 1. Launch the Interactive Settlement Simulator
Experience the live contract interpreter, human confirmation gate, and side-by-side clawback comparison in your browser:
```bash
streamlit run app.py
```

### 2. Run the Test Suite (52 Passing Tests)
```bash
python -m pytest -v
```

### 3. Run the Evaluation Benchmark
```bash
python experiments/run_phase4_llm.py
```

---

## What Problem Does This Solve?

On multi-vendor platforms (e.g., Swiggy, Dunzo, Shopify stores using **Razorpay Route**), customer payments are split among multiple linked accounts (restaurant, delivery partner, platform commission).

When a **partial refund** occurs (e.g., damaged transit goods, delayed courier, platform goodwill):
- **Today's Naive Route Split:** Proportionately debits all linked accounts. An innocent restaurant loses money for a courier's error, causing silent balance erosion and disputes.
- **P37 Solution:** Interprets merchant/platform agreements into structured rules with **verbatim source-span grounding**, submits them to a **human confirmation gate**, and executes deterministic **integer-paise clawbacks** that protect innocent merchants.

---

## The Allocation Ladder (Empirical Proof)

Our research adhered to the principle:
> *Problem → Evidence → Root Cause → Decision → Hypothesis → Baseline → AI Necessity → Implementation → Evaluation.*

| Predictor | Exact Match (140 cases) | Match Rate | Error Gap |
|---|---|---|---|
| **R0: Default Baseline** | 40 / 140 | 28.57% | 71.43% |
| **R1: Oracle Rule Ceiling** | 120 / 140 | **85.71%** | 0.00% (Ceiling) |
| **R2: Regex Extractor (Tier B)** | 120 / 140 | **85.71%** | 0.00% (on Canonical) |
| **R3: P37 LLM Extractor (Tier C)** | 120 / 140 | **85.71%** | **0.00% (Full Parity)** |

### Natural Language Complexity (Tier C):
On 15 non-canonical contract clauses (synonyms, passive voice, negation, multi-clause precedence, amendments):
- **Regex (R2):** 26.7% (4/15)
- **P37 LLM (R3):** **100.0% (15/15)** (+73.3 pp improvement)
- **Span Grounding Rate:** **100.0%** (15/15)
- **Hallucination Rate:** **0.0%** (0/15)

---

## Repository Structure

```
├── app.py                     # Interactive Streamlit Demo & Clawback Simulator
├── SUBMISSION.md              # Razorpay AI Buildathon Submission Document
├── src/p37/
│   ├── benchmark/             # Independent Ground-Truth Generator & Boundary
│   │   ├── generator.py       # Deterministic transaction generator
│   │   ├── groundtruth.py     # Independent answer key resolver
│   │   ├── models.py          # Hidden state and observable models
│   │   └── project.py         # One-way projection boundary
│   └── extraction/            # Predictor, Extractor & Human Gate
│       ├── allocator.py       # Integer-paise Hamiltonian allocator
│       ├── extractor.py       # Canonical Tier-B regex extractor
│       ├── human_gate.py      # Human-in-the-loop review & audit log
│       ├── llm_client.py      # Mock, Gemini, and OpenAI client providers
│       ├── llm_extractor.py   # LLM extractor with source-span grounding
│       ├── models.py          # StructuredRule and SourceSpan models
│       └── tier_c_dataset.py  # 15 Tier-C failure-mode clauses
├── experiments/               # Reproducible experiment runners & frozen results
│   ├── run_tier_b.py          # Tier-B baseline evaluation
│   ├── run_tier_c.py          # Phase-3 role-binding evaluation
│   ├── run_phase4_llm.py      # Phase-4 LLM & human gate benchmark
│   └── results/               # Frozen JSON output artifacts
├── docs/                      # Milestone logs & specifications
│   ├── BENCHMARK_SPEC.md
│   ├── DETERMINISTIC_EXTRACTION_TIER_B.md
│   ├── MILESTONE_LOG_PHASE3.md
│   └── MILESTONE_LOG_PHASE4.md
└── tests/                     # 52 Automated unit, safety & boundary tests
    ├── test_benchmark_integrity.py
    ├── test_tier_b_extraction.py
    ├── test_tier_b_safety.py
    ├── test_tier_c_role_binding.py
    └── test_phase4_llm.py
```

---

## Core Payments Engineering Guarantees

1. **Integer Paise Only:** Never operates on floating-point currencies.
2. **Conservation of Funds:** `sum(allocated_paise) == refund_amount_paise` strictly guaranteed by largest-remainder rounding.
3. **Strict Boundary Isolation:** Predictor code never imports hidden ground-truth classes.
4. **Verifiable Attribution:** Every rule extracted by an LLM is checked against verbatim contract text.
5. **Immutable Audit Trail:** All human review decisions (approve, edit, reject) are logged for financial compliance.
