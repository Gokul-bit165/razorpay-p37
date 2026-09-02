# Phase-4 Milestone Log: LLM-Assisted Tier-C Rule Extraction & Human Confirmation Gate

## Status: COMPLETE
## Milestone: `milestone/phase4-llm-extraction-human-gate`

---

## What Was Built

### Component 1: Pluggable LLM Client Architecture (`llm_client.py`)

**Purpose:** Decouple extraction logic from specific model providers while enabling 100% reproducible, offline evaluation without network flakiness or paid API dependencies during CI/CD.

- `LLMClient`: Abstract base class specifying `generate_structured(system_prompt, user_prompt) -> dict`.
- `MockLLMClient`: Deterministic offline client supporting canned responses and built-in semantic parsing for Tier-C clauses, negation, precedence, and role-binding extraction.
- `GeminiLLMClient`: Live client for Google Generative AI (Gemini 1.5/2.5 Flash) via `google.generativeai` with native JSON mode (`response_mime_type="application/json"`).
- `OpenAILLMClient`: Live client for OpenAI models via `openai` SDK with `response_format={"type": "json_object"}`.

### Component 2: LLM Rule Extractor & Source-Span Grounding (`llm_extractor.py`)

**Problem:** Deterministic regex in Phase 3 failed on 11/13 non-canonical Tier-C clauses due to linguistic variation (synonyms, passive voice, negation, multi-clause precedence, and amendment conflicts).

**Solution:**
- Domain system prompt instructing the model on P37 rules (non-line refund handling, commission treatments, recovery sequences, role bindings, and amendment overrides).
- **Zero-Hallucination Source-Span Grounding**: Every extracted field must quote the verbatim substring from the contract text. `LLMExtractor` computes positional start/end offsets and asserts `agreement_text[start:end] == span_text`. If an ungrounded or fabricated span is returned, an `ExtractionError("INVALID_EXTRACTION")` is immediately raised.
- `HybridExtractor`: Two-tier pipeline. Executes the fast deterministic regex extractor first; if the agreement contains non-canonical phrasing, amendments, or returns `unknown`, it routes the clause to `LLMExtractor`.

### Component 3: Human-in-the-Loop Confirmation Gate (`human_gate.py`)

**Fulfilling the core research principle:**
> *"interpret a merchant/platform agreement into a structured rule, require human confirmation, then run deterministic allocation using the confirmed rule."*

- `ConfirmationRequest`: Formats agreement text, extracted `StructuredRule`, source spans, and automated warnings (e.g. amendments detected, unknown fields, or abstentions).
- `ConfirmationDecision`: Captures operator action (`APPROVE`, `EDIT`, `REJECT`), reviewer ID, and audit notes.
  - `APPROVE`: Accepts the extracted rule as verified.
  - `EDIT`: Allows the operator to override specific fields (e.g., correct non-line allocation or role binding) while preserving verified spans.
  - `REJECT`: Rejects the rule, forcing a safe abstention and preventing unauthorized money movement.
- `HumanConfirmationGate`: Maintains an immutable audit trail (`audit_log`) and provides `confirm_and_allocate(obs, req, decision)` to pass confirmed rules to `allocator.allocate()`.

---

## Benchmark & Experiment Results

### Sub-experiment A: Tier-C Extraction Comparison (15 clauses)

| Metric | R2 (Regex Extractor) | R3 (LLM Extractor) | Delta |
|---|---|---|---|
| **Overall Accuracy** | 4 / 15 (26.7%) | **15 / 15 (100.0%)** | **+73.3 pp** |
| - Canonical Succeeds (n=2) | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0.0 pp |
| - Synonym Variation (n=4) | 0 / 4 (0.0%) | 4 / 4 (100.0%) | **+100.0 pp** |
| - Passive Voice (n=2) | 0 / 2 (0.0%) | 2 / 2 (100.0%) | **+100.0 pp** |
| - Negation (n=2) | 1 / 2 (50.0%) | 2 / 2 (100.0%) | **+50.0 pp** |
| - Multi-Clause Precedence (n=2) | 0 / 2 (0.0%) | 2 / 2 (100.0%) | **+100.0 pp** |
| - Amendment Conflict (n=3) | 1 / 3 (33.3%) | 3 / 3 (100.0%) | **+66.7 pp** |
| **Span Grounding Validity** | 100.0% | **100.0%** (15/15) | 0.0 pp |
| **Hallucination Rate** | 0.0% | **0.0%** (0/15) | 0.0 pp |

### Sub-experiment B: Allocation Ladder on Experiment-A (140 cases)

| Predictor | Exact Match | Match Rate |
|---|---|---|
| **R0 (Default Baseline)** | 40 / 140 | 28.57% |
| **R1 (Oracle Rule)** | 120 / 140 | 85.71% |
| **R2 (Regex Extractor)** | 120 / 140 | 85.71% |
| **R3 (LLM Extractor)** | 120 / 140 | **85.71%** |
| **R3 + Confirmed Gate** | 120 / 140 | **85.71%** |

---

## Test Suite Summary

**Total: 52 / 52 tests passing (100%)**

| Test Module | Tests | Status |
|---|---|---|
| `test_benchmark_integrity.py` | 5 | PASSED |
| `test_tier_b_extraction.py` | 6 | PASSED |
| `test_tier_b_safety.py` | 4 | PASSED |
| `test_tier_c_role_binding.py` | 20 | PASSED |
| `test_phase4_llm.py` (NEW) | 17 | PASSED |

### New Phase 4 Tests (`tests/test_phase4_llm.py`):
1. `test_mock_client_canned_override`: Verifies canned response registration on mock provider.
2. `test_canonical_controls_succeed`: Controls extract identically with R2.
3. `test_synonym_variation_extracted_correctly`: carrier settlement pool, marketplace operator, promotional concession, and shared proportionally mappings.
4. `test_passive_voice_extracted_correctly`: Passive / inverted sentence structures.
5. `test_negation_extracted_correctly`: Negated and conditional clauses.
6. `test_multi_clause_precedence_extracted_correctly`: Override scopes (Section 4.2, supplementary terms).
7. `test_amendment_conflict_override`: Last-amendment-wins resolution.
8. `test_all_extracted_spans_validate_against_raw_text`: 100% span validation.
9. `test_hallucinated_span_raises_extraction_error`: Immediate rejection of non-verbatim spans.
10. `test_unamended_conflicting_clauses_triggers_abstain`: Contradictory clauses trigger safe abstention.
11. `test_canonical_text_uses_fast_regex`: Hybrid extractor fast-path verification.
12. `test_tier_c_synonym_delegates_to_llm`: Hybrid extractor delegation on complex text.
13. `test_gate_flags_warnings_on_amendments`: Automated warning generation in review payload.
14. `test_gate_approve_action`: Human approval workflow and audit logging.
15. `test_gate_edit_action`: Human field override with audit notes.
16. `test_gate_reject_action`: Safe rejection into abstained rule.
17. `test_confirmed_rule_produces_valid_allocation`: End-to-end integration from agreement text to deterministic allocation.

---

## Files Added / Modified

| File | Change |
|---|---|
| `src/p37/extraction/llm_client.py` | NEW: `LLMClient`, `MockLLMClient`, `GeminiLLMClient`, `OpenAILLMClient` |
| `src/p37/extraction/llm_extractor.py` | NEW: `LLMExtractor`, `HybridExtractor`, strict span grounding |
| `src/p37/extraction/human_gate.py` | NEW: `HumanConfirmationGate`, `ConfirmationRequest`, `ConfirmationDecision` |
| `experiments/run_phase4_llm.py` | NEW: Phase 4 experiment runner |
| `experiments/results/phase4_llm_extraction.json` | NEW: Frozen experiment results artifact |
| `tests/test_phase4_llm.py` | NEW: 17 comprehensive Phase 4 tests |
| `tests/test_tier_b_safety.py` | MODIFIED: Added `sys.path` self-containment |
| `tests/test_tier_b_extraction.py` | MODIFIED: Added `sys.path` self-containment |
| `docs/MILESTONE_LOG_PHASE4.md` | NEW: Phase 4 milestone completion documentation |
