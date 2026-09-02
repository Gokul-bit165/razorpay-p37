# Razorpay AI Buildathon Submission: Problem P37

# Contract-Aware Split-Payment Refund & Clawback Engine
**Solving Multi-Vendor Silent Balance Erosion and Reconciliation Disputes on Razorpay Route**

---

## 1. Executive Summary

In marketplaces and split-payment platforms (e.g., Swiggy, Dunzo, Urban Company, multi-vendor Shopify stores using **Razorpay Route**), a single customer payment is split among multiple parties: fulfilling vendors, courier partners, platform commissions, and promotional discount pools.

When a **partial refund** occurs (such as an unfulfilled order item, damaged goods, transit delay, or customer goodwill credit), standard payment gateways execute a **naive proportional clawback**.

### The Silent Crisis in Split Payments
- **The Failure Mode:** If a delivery driver damages a package or fails to deliver, a naive proportional refund claws back money from the **merchant/restaurant**, even though the merchant fulfilled the food perfectly.
- **The Financial Impact:** Millions of rupees in silent balance erosion, negative merchant balances, chargeback disputes, and merchant churn.
- **Why Simple Code Fails:** Contracts govern who bears which loss (e.g. *"shipping funder bears non-line refunds"*, *"losses are absorbed by the marketplace operator"*). However, these agreements are written in natural legal language, subject to mid-term amendments, and stored outside the core transaction ledger.

### The P37 Solution
**P37** is an end-to-end, payments-grade clawback engine built specifically for Razorpay Route. It combines:
1. **Intelligent Contract Interpretation:** Extracts governing clawback rules and role-to-account bindings from natural legal text.
2. **Zero-Hallucination Source-Span Grounding:** Every extracted rule is strictly tied to verbatim character-level spans in the contract text; any ungrounded claim raises an immediate safety halt.
3. **Human-in-the-Loop Confirmation Gate:** Ops teams inspect contract text, verbatim citations, and automated warnings to approve, edit, or reject before money moves.
4. **Deterministic Integer-Paise Allocation:** Math executed strictly in integer paise using largest-remainder rounding—guaranteeing zero float leakage and total conservation of funds.

---

## 2. The Core Engineering Principle: Empirical AI Necessity

Unlike submissions that arbitrarily wrap an LLM around basic prompts, P37 adheres to a strict payments engineering standard:
> **Problem → Evidence → Root Cause → Decision → Hypothesis → Baseline → AI Necessity → Implementation → Evaluation.**

We proved empirically through a 4-phase validation ladder exactly where deterministic logic suffices and where AI is mathematically necessary:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        THE ALLOCATION LADDER                           │
│                                                                        │
│  R0: Naive Proportional Baseline         28.57% (40/140)               │
│  ▲                                                                     │
│  │ +57.14 pp gap                                                       │
│  ▼                                                                     │
│  R1: Oracle Rule (Hidden Ground Truth)   85.71% (120/140)              │
│                                                                        │
│  R2: Regex Extractor (Clean Canonical)   85.71% (closes oracle gap)    │
│  ▲                                                                     │
│  │ BUT regex drops to 26.7% on real natural-language variation         │
│  ▼                                                                        │
│  R3: P37 LLM Extractor (Tier-C NLP)      100.0% (15/15, +73.3 pp lift) │
└────────────────────────────────────────────────────────────────────────┘
```

### Empirical Findings:
1. **The Missing Role-Binding Discovery (Tier-B):** Pure regex achieved 100% parsing on canonical keywords, but recovered 0 pp in allocation because agreements did not state *which account played which role*. Once observable role-designation clauses were introduced, the oracle gap (+57.14 pp) was completely closed.
2. **The Linguistic Boundary Proof (Tier-C):** When tested across 15 real-world legal phrasing patterns, regex collapsed to **26.7%**:
   - **Synonym variations** (*"carrier settlement pool"*): Regex 0% → P37 LLM **100%** (+100 pp)
   - **Passive voice** (*"shall be borne by the party providing shipping"*): Regex 0% → P37 LLM **100%** (+100 pp)
   - **Multi-clause precedence** (Section 4.2 shipping overrides Section 4.1): Regex 0% → P37 LLM **100%** (+100 pp)
   - **Amendment conflicts** (last amendment wins): Regex 33.3% → P37 LLM **100%** (+66.7 pp)
3. **Span Grounding & Anti-Hallucination:**
   - Evaluated across all clauses: **100% span validation rate**, **0.0% hallucination rate**.

---

## 3. Architecture & System Flow

```
                               RAW AGREEMENT TEXT
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │         Hybrid Extractor          │
                     │  Fast Regex ──► LLM Fallback      │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │   Source-Span Grounding Engine    │
                     │ Assert: text[start:end] == span   │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │   Human Confirmation Gate (UI)    │
                     │ [Approve]   [Edit]   [Reject]     │
                     │     └──────► Audit Log ◄──────┘   │
                     └─────────────────┬─────────────────┘
                                       │ Confirmed StructuredRule
                                       ▼
                     ┌───────────────────────────────────┐
                     │   Deterministic Paise Allocator   │
                     │  Integer math · Largest-remainder │
                     │  sum(allocations) == refund_amt   │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                            RAZORPAY ROUTE REVERSAL
```

---

## 4. Razorpay Route API Blueprint

P37 is designed to integrate cleanly into Razorpay Route's existing transfer reversal architecture:

### 1. Reversal Intent Request
```http
POST /v1/transfers/{transfer_id}/reversal_intent
Content-Type: application/json
Authorization: Basic <API_KEY>
```
```json
{
  "refund_id": "rf_9876543210",
  "refund_amount_paise": 25000,
  "reversal_mode": "contract_aware",
  "agreement_ref": "agr_swiggy_master_2026",
  "confirmation_token": "conf_token_abc123",
  "reviewer_id": "ops_engineer_gokul",
  "rule": {
    "nonline_allocation": "shipping_funder",
    "commission_treatment": "retained",
    "funding_map": {
      "shipping": "acc_delivery_fleet_01"
    }
  }
}
```

### 2. Execution Response
```json
{
  "status": "reversed",
  "total_reversed_paise": 25000,
  "currency": "INR",
  "breakdown": [
    {
      "linked_account_id": "acc_delivery_fleet_01",
      "reversed_amount_paise": 25000,
      "original_transfer_paise": 20000,
      "drawn_from_balance": true,
      "remaining_balance_paise": 55000
    },
    {
      "linked_account_id": "acc_restaurant_vendor",
      "reversed_amount_paise": 0,
      "status": "protected"
    }
  ],
  "dispute_risk_mitigated_paise": 17500,
  "audit_trail_id": "aud_log_45a78f"
}
```

---

## 5. Test Suite & Production Rigor

The codebase is backed by **52 automated unit and boundary tests** running in CI/CD (`pytest`):

| Test Suite | Tests | Description |
|---|---|---|
| `test_benchmark_integrity.py` | 5 | Boundary leakage checks, integer-paise math, generator reproducibility. |
| `test_tier_b_extraction.py` | 6 | Canonical phrase extraction, recovery ordering, span checks. |
| `test_tier_b_safety.py` | 4 | Import isolation (predictor cannot access hidden benchmark types). |
| `test_tier_c_role_binding.py` | 20 | Role designations, conflict detection, amendment overrides. |
| `test_phase4_llm.py` | 17 | LLM extraction across 6 NLP categories, anti-hallucination checks, human gate. |
| **TOTAL** | **52 / 52 PASSED** | **100% Test Pass Rate** |

---

## 6. How to Run & Experience the Demo

### 1. Launch the Interactive Streamlit Simulator
```bash
streamlit run app.py
```
- Select real-world marketplace scenarios (Food delivery damaged item, e-commerce goodwill refund, logistics amendment overrides).
- View live contract interpretation with verbatim source-span highlights.
- Interact with the **Human Confirmation Gate** (Approve / Edit / Reject).
- Inspect the **Side-by-Side Settlement Ledger** showing exact rupees saved from erroneous debits.

### 2. Run the Benchmark Experiment
```bash
python experiments/run_phase4_llm.py
```
Generates the frozen evaluation artifact in `experiments/results/phase4_llm_extraction.json`.

### 3. Run the Automated Test Suite
```bash
python -m pytest -v
```
Executes all 52 tests verifying mathematical determinism, security boundaries, and zero hallucinations.

---

## 7. Conclusion: Why P37 Deserves to Win

1. **Massive Commercial Relevance:** Addresses a core pain point in split payments that directly impacts merchant retention on Razorpay Route.
2. **Empirical Scientific Rigor:** Proves *why* and *where* AI is needed through adversarial benchmark ladders rather than ungrounded claims.
3. **Zero Financial Risk:** Operates with integer-paise precision, verifiable source grounding, and human-in-the-loop auditability before money is moved.
4. **Immediate Production Feasibility:** Directly maps to Razorpay's API architecture and can be deployed as an add-on service for enterprise platform merchants.
