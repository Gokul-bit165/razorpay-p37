# Recovery Engine · P37 Split-Settlement Clawback Recovery

**Track: AI Revenue Recovery** — *Find revenue that's slipping away and win it back.*

[![Tests: 68 Passed](https://img.shields.io/badge/Tests-68%20Passed%20(100%25)-success)](tests)
[![Precision: Integer-Paise](https://img.shields.io/badge/Precision-Integer--Paise%20(No%20Float%20Drift)-blue)](src/p37/extraction/allocator.py)
[![Grounding: Verbatim Spans](https://img.shields.io/badge/Grounding-100%25%20Verbatim%20Spans-brightgreen)](src/p37/extraction/llm_extractor.py)
[![Hallucinations: 0.0%](https://img.shields.io/badge/Hallucinations-0.0%25-green)](experiments/results/phase4_llm_extraction.json)

**Research-first prototype for the Razorpay AI Buildathon.**

**Problem P37:** Partial-refund allocation and clawback on split payments where contract-specific bearing rules differ from proportional/default handling — one of the quietest and most common ways multi-vendor platforms leak revenue: money silently pulled from the *wrong* linked account, or never recovered from the *right* one.

📖 **Read the Complete Official Submission:** [SUBMISSION.md](SUBMISSION.md)
🔍 **Read the Model Audit & Provenance Report:** [FINDINGS.md](FINDINGS.md)
🎬 **View the 3-Minute Demo Video Script:** [DEMO_SCRIPT.md](DEMO_SCRIPT.md)

---

## Why this counts as Revenue Recovery

The track asks for an agent that **detects revenue at risk, diagnoses it, picks the right intervention, and executes a bounded recovery workflow** — with measured money recovered across a batch, compliant escalation, stopping rules, and an audit trail. This project is a deep, end-to-end build of exactly that loop for one high-frequency, high-stakes leak: **split-settlement partial refunds**, rather than a shallow pass across every example direction.

| Track requirement | How this engine satisfies it | Where |
| :--- | :--- | :--- |
| **Detect revenue at risk** | Naive proportional clawback silently debits innocent linked accounts and misapplies commission on every partial refund — quantified live, per-case and at portfolio scale. | `app.py` Step 1, Step 5 |
| **Diagnose root cause** | Governing agreement clause is extracted into a structured rule with **verbatim source-span grounding** — every field is traceable to an exact character offset in the contract text, so the diagnosis is auditable, not a black box. | `src/p37/extraction/llm_extractor.py`, `extractor.py` |
| **Choose the right intervention** | The structured rule (non-line allocation, commission treatment, recovery order, funding map) drives a deterministic **integer-paise allocator** that recovers exactly the right amount from exactly the right party. | `src/p37/extraction/allocator.py` |
| **Bounded recovery workflow** | Nothing executes without passing a **human confirmation gate** (APPROVE / EDIT / REJECT). REJECT forces a safe abstention — zero funds move. | `src/p37/extraction/human_gate.py` |
| **Stopping rules** | The allocator refuses to act — rather than guess — on `refund_exceeds_payment`, `refund_exceeds_transfers`, `funding_map_unavailable`, `zero_line_total`, `role_binding_conflict`, and every other structurally unsafe state. These are explicit, enumerable `AbstainReason` codes, not silent failures. | `src/p37/extraction/models.py`, `allocator.py` |
| **Compliant escalation** | Every extraction with a warning (unknown allocation, missing commission treatment, empty recovery order, amendment clauses) is routed to a human reviewer before money moves. | `human_gate.py: prepare_request` |
| **Audit trail** | Every reviewer decision — action, reviewer ID, note, warnings shown, confirmed rule — is appended to an immutable, timestamped log. | `human_gate.py: HumanConfirmationGate.audit_log` |
| **Measured money recovered, across a batch** | A "Step 5: At Scale" simulation runs the real extractor + allocator over a **generated portfolio of hundreds to thousands of refund cases across 21 documented real-world scenario types** (clean returns, contract-clause-driven splits, commission edge cases, rounding, invalid/adversarial requests), grades every case against an **independent ground-truth resolver**, and reports ₹ recovered correctly, ₹ naive-misallocation prevented, accuracy, and abstain-safety — with honest disclosure of current detection limits. | `app.py` Step 5, `src/p37/benchmark/` |

**Scope honesty:** this build does not implement checkout-abandonment recovery, subscription dunning, or a B2B receivables chaser (other example directions in the brief). It goes deep on one revenue-leak pattern end-to-end — detection, diagnosis, bounded execution, and measured batch impact — rather than wide and shallow across all six.

---

## Quickstart

### 1. Launch the Guided Recovery Simulator (5-Step Narrative + Bulk Impact)
Walk through the naive-loss problem, root-cause diagnosis, human confirmation gate, correct recovery, and a portfolio-scale impact simulation in your browser:
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
*Committed Manifest SHA Binding:* `65788246c47197427ce9a4867b5db59b078f6462` (`6578824`)

---

## What Revenue Leak Does This Recover?

On multi-vendor platforms (e.g., Swiggy, Dunzo, Shopify stores using **Razorpay Route**), customer payments are split among multiple linked accounts (restaurant, delivery partner, platform commission).

When a **partial refund** occurs (e.g., damaged transit goods, delayed courier, platform goodwill):
- **Today's Naive Route Split (the leak):** Proportionately debits *all* linked accounts. An innocent restaurant loses money for a courier's error — silent balance erosion, merchant disputes, and support tickets that never get traced back to the actual cause.
- **The Recovery Intervention:** Interpret the merchant/platform agreement into a structured, grounded rule; route it through a **human confirmation gate**; execute a deterministic **integer-paise clawback** that recovers the refund exactly from the responsible party — protecting innocent merchants' revenue and Razorpay's earned commission in the same motion.

---

## The Benchmark Ladder (Empirical Proof)

The core justification for deploying an LLM in the diagnosis step is the collapse of deterministic pattern-matching when legal language departs from rigid boilerplate templates. Across 140 distinct agreements, regex accuracy collapses from **85.71%** on canonical phrasing down to **15.00%** on non-canonical phrasing.

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

### Portfolio-Scale Recovery (Step 5, $n=1{,}500$ generated cases, seed 42)
Run via the deterministic pipeline (extractor + allocator) against the independent ground-truth resolver, distributed across a realistic mix of the 21 case types:
- **Deterministic accuracy vs. ground truth:** 100.0% on resolvable cases (canonical machine-generated contract phrasing)
- **Naive-logic misallocation prevented:** ₹35,642 reallocated correctly that proportional clawback would have moved to the wrong account, out of ₹161,159 total simulated refund volume
- **Invalid-refund abstain safety:** 40.0% — the observable interface structurally detects `refund_exceeds_payment` and `refund_exceeds_transfers` (2 of 5 invalid subtypes); closed-account, ambiguous-attribution, and mislabelled-reason detection require signals outside the current observable schema — a documented scope boundary, not a silent failure. See the in-app caption on Step 5 for the live breakdown.

Numbers regenerate live in `app.py` Step 5 with any portfolio size or seed — nothing above is hand-typed.

---

## Repository Structure

```
├── app.py                     # 5-Step Streamlit Recovery Narrative + Bulk Portfolio Impact Simulator
├── SUBMISSION.md              # Razorpay AI Buildathon Submission Document
├── FINDINGS.md                # Gate 1 Audit of MockLLMClient & Provenance Resolution
├── DEMO_SCRIPT.md             # 3-minute shot-by-shot video presentation guide
├── src/p37/
│   ├── benchmark/             # Independent Ground-Truth Generator & Boundary
│   │   ├── generator.py       # Deterministic transaction generator (21 real-world case types)
│   │   ├── groundtruth.py     # Independent answer key resolver
│   │   ├── models.py          # Hidden state and observable models
│   │   └── project.py         # One-way projection boundary
│   └── extraction/            # Predictor, Extractor & Human Gate
│       ├── allocator.py       # Integer-paise Hamiltonian allocator + stopping rules
│       ├── extractor.py       # Canonical Tier-B regex extractor
│       ├── human_gate.py      # Human-in-the-loop review & immutable audit log
│       ├── llm_client.py      # Live Gemini Flash Lite & Mock providers
│       ├── llm_extractor.py   # LLM extractor with source-span grounding
│       ├── models.py          # StructuredRule, SourceSpan & AbstainReason models
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

## Core Recovery Engineering Guarantees

1. **Integer Paise Only:** Never operates on floating-point currencies — no rounding drift in recovered amounts.
2. **Conservation of Funds:** `sum(allocated_paise) == refund_amount_paise` strictly guaranteed by largest-remainder rounding.
3. **Strict Boundary Isolation:** Predictor code never imports hidden ground-truth classes — the batch-impact numbers are graded independently, not self-reported.
4. **Verifiable Diagnosis:** Every rule extracted by an LLM is checked against verbatim contract text; an invalid span raises immediately rather than executing on an unverified basis.
5. **Bounded Execution:** The allocator abstains — moves zero funds — on every structurally unsafe state (`refund_exceeds_payment`, `funding_map_unavailable`, `role_binding_conflict`, etc.) instead of guessing.
6. **Compliant Escalation:** Any extraction carrying a warning (unknown allocation, missing commission treatment, amendment clause) routes to human review before execution.
7. **Immutable Audit Trail:** All human review decisions (approve, edit, reject) — with reviewer ID, timestamp, warnings shown, and confirmed rule — are logged for financial compliance.
