# Razorpay Route · P37 Split Clawback Engine

[![Tests: 68 Passed](https://img.shields.io/badge/Tests-68%20Passed%20(100%25)-success)](tests)
[![Precision: Integer-Paise](https://img.shields.io/badge/Precision-Integer--Paise%20(No%20Float%20Drift)-blue)](src/p37/extraction/allocator.py)
[![Grounding: Verbatim Spans](https://img.shields.io/badge/Grounding-100%25%20Verbatim%20Spans-brightgreen)](src/p37/extraction/llm_extractor.py)
[![Hallucinations: 0.0%](https://img.shields.io/badge/Hallucinations-0.0%25-green)](experiments/results/phase4_llm_extraction.json)

**Research-first prototype for the Razorpay AI Buildathon.**

**Problem P37:** Partial-refund allocation and clawback on split payments where contract-specific bearing rules differ from proportional/default handling.

📖 **Read the Complete Official Submission:** [SUBMISSION.md](SUBMISSION.md)  
🔍 **Read the Model Audit & Provenance Report:** [FINDINGS.md](FINDINGS.md)  
🎬 **View the 3-Minute Demo Video Script:** [DEMO_SCRIPT.md](DEMO_SCRIPT.md)  

---

## Quickstart

### 1. Launch the Guided Settlement Simulator
Experience the live 4-step contract interpreter, human confirmation gate, and side-by-side clawback comparison in your browser:
```bash
streamlit run app.py
```

### 2. Run the Full Test Suite (68 Passing Tests)
```bash
pytest tests/ -v
```

### 3. Run the 3-Regime Benchmark Ladder
```bash
python experiments/run_ladder.py --regime all --llm-mode replay
```

### 4. Verify Cryptographic Manifest Checksums
```bash
python scripts/generate_manifest.py --verify
```

---

## What Problem Does This Solve?

On multi-vendor platforms (e.g., Swiggy, Dunzo, Shopify stores using **Razorpay Route**), customer payments are split among multiple linked accounts (restaurant, delivery partner, platform commission).

When a **partial refund** occurs (e.g., damaged transit goods, delayed courier, platform goodwill):
- **Today's Naive Route Split:** Proportionately debits all linked accounts. An innocent restaurant loses money for a courier's error, causing silent balance erosion and disputes.
- **P37 Solution:** Interprets merchant/platform agreements into structured rules with **verbatim source-span grounding**, submits them to a **human confirmation gate**, and executes deterministic **integer-paise clawbacks** that protect innocent merchants.

---

## The Benchmark Ladder (Empirical Proof)

The core justification for deploying an LLM is the collapse of deterministic pattern-matching when legal language departs from rigid boilerplate templates. Across 140 distinct agreements, regex accuracy collapses from **85.71%** on canonical phrasing down to **15.00%** on non-canonical phrasing.

### Full 140-Case Evaluation ($n=140$ Cases per Regime)
| Evaluation Regime | Description | R0 (Default Naive) | R1 (Oracle Ceiling) | R2 (Regex Extractor) |
| :--- | :--- | :---: | :---: | :---: |
| **Regime A (Canonical)** | 100% standard contract template | 28.57% (40/140) | **85.71%** (120/140) | **85.71%** (120/140) |
| **Regime B (Mixed)** | ~30% canonical, ~70% derived variants | 26.43% (37/140) | **85.71%** (120/140) | **42.14%** (59/140) |
| **Regime C (Non-canonical)** | 100% derived natural language variants | 24.29% (34/140) | **85.71%** (120/140) | **15.00%** (21/140) |

### Natural Language Complexity (Tier C, $n=15$ clauses):
On non-canonical contract clauses (synonyms, passive voice, negation, multi-clause precedence, amendments):
- **Regex (R2):** 26.7% (4/15)
- **P37 Live LLM (R3):** **93.3% (14/15)** (+66.6 pp improvement)
- **Span Grounding Rate:** **100.0%** (15/15)
- **Hallucination Rate:** **0.0%** (0/15)

---

## Repository Structure

```
├── app.py                     # Guided 4-Step Streamlit Narrative & Clawback Simulator
├── SUBMISSION.md              # Razorpay AI Buildathon Submission Document
├── FINDINGS.md                # Gate 1 Audit of MockLLMClient & Provenance Resolution
├── DEMO_SCRIPT.md             # 3-minute shot-by-shot video presentation guide
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
│       ├── llm_client.py      # Live Gemini Flash Lite & Mock providers
│       ├── llm_extractor.py   # LLM extractor with source-span grounding
│       ├── models.py          # StructuredRule and SourceSpan models
│       └── tier_c_dataset.py  # Tier-C failure-mode clauses
├── experiments/               # Reproducible experiment runners & frozen results
│   ├── run_ladder.py          # 3-regime benchmark ladder runner
│   ├── run_phase4_llm.py      # Tier-C LLM & human gate benchmark
│   └── results/               # Committed JSON artifacts & 113 live transcripts
├── scripts/                   # Verification, manifest & economics scripts
│   ├── calc_cost_latency.py   # Transcript-measured cost & latency calculator
│   └── generate_manifest.py   # SHA-256 verification manifest generator
└── tests/                     # 68 Automated unit, invariant, safety & boundary tests
    ├── test_adversarial_injection.py
    ├── test_ladder_invariants.py
    ├── test_portability.py
    └── ...
```

---

## Core Payments Engineering Guarantees

1. **Integer Paise Only:** Never operates on floating-point currencies.
2. **Conservation of Funds:** `sum(allocated_paise) == refund_amount_paise` strictly guaranteed by largest-remainder rounding.
3. **Strict Boundary Isolation:** Predictor code never imports hidden ground-truth classes.
4. **Verifiable Attribution:** Every rule extracted by an LLM is checked against verbatim contract text.
5. **Immutable Audit Trail:** All human review decisions (approve, edit, reject) are logged for financial compliance.
