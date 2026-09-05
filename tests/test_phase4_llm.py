"""
test_phase4_llm.py

Comprehensive test suite for Phase 4:
  1. LLM Client abstraction & mock provider
  2. LLM extraction on Tier-C failure categories:
     - synonym_variation
     - passive_voice
     - negation
     - multi_clause_precedence
     - amendment_conflict
  3. Source-span validation & anti-hallucination safety
  4. HybridExtractor fast-path vs LLM delegation
  5. HumanConfirmationGate (APPROVE, EDIT, REJECT) & audit trail
  6. End-to-end allocation integration
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from p37.benchmark.generator import GenerationConfig, generate
from p37.benchmark.project import project
from p37.extraction.allocator import allocate
from p37.extraction.human_gate import (
    ConfirmationAction,
    ConfirmationDecision,
    HumanConfirmationGate,
)
from p37.extraction.llm_client import MockLLMClient
from p37.extraction.llm_extractor import HybridExtractor, LLMExtractor
from p37.extraction.models import (
    AbstainReason,
    CommissionTreatment,
    ExtractionError,
    NonlineAllocation,
    StructuredRule,
)
from p37.extraction.tier_c_dataset import TIER_C_CLAUSES


@pytest.fixture
def llm_extractor() -> LLMExtractor:
    return LLMExtractor(client=MockLLMClient())


@pytest.fixture
def hybrid_extractor(llm_extractor: LLMExtractor) -> HybridExtractor:
    return HybridExtractor(llm_extractor=llm_extractor)


@pytest.fixture
def human_gate() -> HumanConfirmationGate:
    return HumanConfirmationGate()


# ── 1. LLM Client & Mock Provider Tests ────────────────────────────────────────

class TestLLMClient:

    def test_mock_client_canned_override(self):
        client = MockLLMClient()
        client.register_canned("custom_contract_keyword", {
            "nonline_allocation": "shipping_funder",
            "commission_treatment": "retained",
            "recovery_order": ["acc_canned_0"],
            "funding_map": {"shipping": "acc_canned_0"},
            "principal_bearer_verified": True,
            "abstain": False,
            "abstain_reason": "none",
            "spans": {
                "nonline_allocation": "custom_contract_keyword",
                "commission_treatment": "retained",
            },
            "role_binding_spans": {},
        })
        text = "This contract has custom_contract_keyword and retained commission."
        extractor = LLMExtractor(client=client)
        rule = extractor.extract(text)
        assert rule.nonline_allocation == NonlineAllocation.shipping_funder
        assert rule.commission_treatment == CommissionTreatment.retained
        assert rule.recovery_order == ("acc_canned_0",)

    def test_transcript_replay_client_fatal_cache_miss(self, tmp_path):
        from p37.extraction.llm_client import TranscriptReplayClient
        replay_client = TranscriptReplayClient(mode="replay", cache_dir=tmp_path)
        with pytest.raises(RuntimeError, match="Fatal: Replay cache miss"):
            replay_client.generate_structured("sys_prompt", "unrecorded_user_prompt")

    def test_transcript_record_and_replay_roundtrip(self, tmp_path):
        from p37.extraction.llm_client import TranscriptReplayClient, MockLLMClient
        mock = MockLLMClient()
        recorder = TranscriptReplayClient(mode="record", cache_dir=tmp_path, underlying_client=mock)
        resp1 = recorder.generate_structured("sys", "Refund allocation agreement:\nNon-line refund rule: proportional.")

        # Replay client should now succeed on this prompt
        replayer = TranscriptReplayClient(mode="replay", cache_dir=tmp_path)
        resp2 = replayer.generate_structured("sys", "Refund allocation agreement:\nNon-line refund rule: proportional.")
        assert resp1 == resp2
        assert resp2["nonline_allocation"] == "proportional"



# ── 2. Tier-C Linguistic Extraction Tests ─────────────────────────────────────

class TestTierCExtraction:

    def test_canonical_controls_succeed(self, llm_extractor: LLMExtractor):
        """tc_ctrl_01 and tc_ctrl_02 extract accurately."""
        c1 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_ctrl_01")
        rule1 = llm_extractor.extract(c1.clause_text)
        assert rule1.nonline_allocation == NonlineAllocation.proportional
        assert rule1.commission_treatment == CommissionTreatment.retained
        assert not rule1.abstain

        c2 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_ctrl_02")
        rule2 = llm_extractor.extract(c2.clause_text)
        assert rule2.nonline_allocation == NonlineAllocation.shipping_funder
        assert rule2.commission_treatment == CommissionTreatment.retained
        assert not rule2.abstain

    def test_synonym_variation_extracted_correctly(self, llm_extractor: LLMExtractor):
        """Synonyms are correctly resolved to canonical enums."""
        # tc_syn_01: carrier settlement pool -> shipping_funder
        c1 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_syn_01")
        rule1 = llm_extractor.extract(c1.clause_text)
        assert rule1.nonline_allocation == NonlineAllocation.shipping_funder
        assert rule1.commission_treatment == CommissionTreatment.retained
        assert rule1.recovery_order == ("acc_syn_0", "acc_syn_1")

        # tc_syn_02: marketplace operator -> platform_absorbs
        c2 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_syn_02")
        rule2 = llm_extractor.extract(c2.clause_text)
        assert rule2.nonline_allocation == NonlineAllocation.platform_absorbs
        assert rule2.commission_treatment == CommissionTreatment.full

        # tc_syn_03: promotional concession -> discount_funder
        c3 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_syn_03")
        rule3 = llm_extractor.extract(c3.clause_text)
        assert rule3.nonline_allocation == NonlineAllocation.discount_funder
        assert rule3.commission_treatment == CommissionTreatment.retained

        # tc_syn_04: shared across accounts in proportion -> proportional
        c4 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_syn_04")
        rule4 = llm_extractor.extract(c4.clause_text)
        assert rule4.nonline_allocation == NonlineAllocation.proportional
        assert rule4.commission_treatment == CommissionTreatment.proportional

    def test_passive_voice_extracted_correctly(self, llm_extractor: LLMExtractor):
        """Inverted and passive sentence structures are resolved."""
        # tc_passive_01: "shall be borne by the party providing the shipping service"
        c1 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_passive_01")
        rule1 = llm_extractor.extract(c1.clause_text)
        assert rule1.nonline_allocation == NonlineAllocation.shipping_funder
        assert rule1.commission_treatment == CommissionTreatment.retained
        assert rule1.recovery_order == ("acc_passive_0", "acc_passive_1")

        # tc_passive_02: "are to be absorbed by the platform partner"
        c2 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_passive_02")
        rule2 = llm_extractor.extract(c2.clause_text)
        assert rule2.nonline_allocation == NonlineAllocation.platform_absorbs
        assert rule2.commission_treatment == CommissionTreatment.proportional

    def test_negation_extracted_correctly(self, llm_extractor: LLMExtractor):
        """Negation statements are parsed accurately."""
        # tc_neg_01: "not distributed proportionally. The shipping partner bears..."
        c1 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_neg_01")
        rule1 = llm_extractor.extract(c1.clause_text)
        assert rule1.nonline_allocation == NonlineAllocation.shipping_funder
        assert rule1.commission_treatment == CommissionTreatment.retained

    def test_multi_clause_precedence_extracted_correctly(self, llm_extractor: LLMExtractor):
        """Special terms take precedence over base agreements."""
        # tc_prec_01: Section 4.2 shipping override
        c1 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_prec_01")
        rule1 = llm_extractor.extract(c1.clause_text)
        assert rule1.nonline_allocation == NonlineAllocation.shipping_funder
        assert rule1.commission_treatment == CommissionTreatment.full

        # tc_prec_02: Supplementary clause overrides Master
        c2 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_prec_02")
        rule2 = llm_extractor.extract(c2.clause_text)
        assert rule2.nonline_allocation == NonlineAllocation.platform_absorbs

    def test_amendment_conflict_override(self, llm_extractor: LLMExtractor):
        """AMENDMENT clauses override earlier base contract clauses."""
        # tc_amend_01: shipping funder & retained overrides proportional & full
        c1 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_amend_01")
        rule1 = llm_extractor.extract(c1.clause_text)
        assert rule1.nonline_allocation == NonlineAllocation.shipping_funder
        assert rule1.commission_treatment == CommissionTreatment.retained

        # tc_amend_02: amendment updates recovery order to acc_new_0 then acc_new_1
        c2 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_amend_02")
        rule2 = llm_extractor.extract(c2.clause_text)
        assert rule2.recovery_order == ("acc_new_0", "acc_new_1")

        # tc_amend_03: amendment changes discount_funder to proportional
        c3 = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_amend_03")
        rule3 = llm_extractor.extract(c3.clause_text)
        assert rule3.nonline_allocation == NonlineAllocation.proportional
        assert rule3.commission_treatment == CommissionTreatment.full


# ── 3. Source-Span Validation & Anti-Hallucination ────────────────────────────

class TestSpanGroundingAndSafety:

    def test_all_extracted_spans_validate_against_raw_text(self, llm_extractor: LLMExtractor):
        """Every span returned across all Tier-C clauses must validate against text."""
        for clause in TIER_C_CLAUSES:
            rule = llm_extractor.extract(clause.clause_text)
            for field_name, span in rule.spans.items():
                assert span.validate(clause.clause_text), (
                    f"Span validation failed for field {field_name} in clause {clause.clause_id}"
                )

    def test_hallucinated_span_raises_extraction_error(self):
        """If the LLM client cites a span not present verbatim, raise ExtractionError."""
        client = MockLLMClient()
        client.register_canned("test_hallucination", {
            "nonline_allocation": "shipping_funder",
            "commission_treatment": "retained",
            "recovery_order": [],
            "funding_map": {},
            "principal_bearer_verified": True,
            "abstain": False,
            "abstain_reason": "none",
            "spans": {
                "nonline_allocation": "THIS STRING DOES NOT EXIST IN THE CONTRACT AT ALL",
            },
            "role_binding_spans": {},
        })
        text = "This contract mentions test_hallucination and nothing else."
        extractor = LLMExtractor(client=client)
        with pytest.raises(ExtractionError, match="INVALID_EXTRACTION"):
            extractor.extract(text)

    def test_unamended_conflicting_clauses_triggers_abstain(self, llm_extractor: LLMExtractor):
        """Directly contradictory clauses without amendment header trigger safe abstention."""
        text = (
            "Refund agreement:\n"
            "Non-line refund rule: shipping funder.\n"
            "Non-line refund rule: platform absorbs.\n"
            "Commission is retained on refunds."
        )
        rule = llm_extractor.extract(text)
        assert rule.abstain
        assert rule.abstain_reason == AbstainReason.conflicting


# ── 4. Hybrid Extractor Tests ─────────────────────────────────────────────────

class TestHybridExtractor:

    def test_canonical_text_uses_fast_regex(self, hybrid_extractor: HybridExtractor):
        text = (
            "Refund allocation agreement:\n"
            "Non-line refund rule: proportional.\n"
            "Commission is retained on refunds.\n"
            "Recovery order: acc_0 then acc_1."
        )
        rule = hybrid_extractor.extract(text)
        assert rule.nonline_allocation == NonlineAllocation.proportional
        assert rule.commission_treatment == CommissionTreatment.retained
        assert not rule.abstain

    def test_tier_c_synonym_delegates_to_llm(self, hybrid_extractor: HybridExtractor):
        c = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_syn_01")
        rule = hybrid_extractor.extract(c.clause_text)
        # Regex would return unknown, but HybridExtractor delegates to LLM and succeeds
        assert rule.nonline_allocation == NonlineAllocation.shipping_funder
        assert rule.commission_treatment == CommissionTreatment.retained


# ── 5. Human Confirmation Gate Tests ──────────────────────────────────────────

class TestHumanConfirmationGate:

    def test_gate_flags_warnings_on_amendments(self, human_gate: HumanConfirmationGate, llm_extractor: LLMExtractor):
        c = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_amend_01")
        rule = llm_extractor.extract(c.clause_text)
        req = human_gate.prepare_request(c.clause_text, rule)
        assert any("amendment" in w.lower() for w in req.warnings)

    def test_gate_approve_action(self, human_gate: HumanConfirmationGate, llm_extractor: LLMExtractor):
        c = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_syn_01")
        rule = llm_extractor.extract(c.clause_text)
        req = human_gate.prepare_request(c.clause_text, rule)

        decision = ConfirmationDecision(
            action=ConfirmationAction.APPROVE,
            reviewer_id="ops_engineer_42",
            audit_note="Verified carrier pool wording maps to shipping funder.",
        )
        confirmed = human_gate.apply_decision(req, decision)
        assert confirmed.nonline_allocation == NonlineAllocation.shipping_funder
        assert not confirmed.abstain
        assert len(human_gate.audit_log) == 1
        assert human_gate.audit_log[0]["action"] == "APPROVE"

    def test_gate_edit_action(self, human_gate: HumanConfirmationGate, llm_extractor: LLMExtractor):
        c = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_ctrl_01")
        rule = llm_extractor.extract(c.clause_text)
        req = human_gate.prepare_request(c.clause_text, rule)

        # Human operator overrides nonline rule to platform_absorbs
        decision = ConfirmationDecision(
            action=ConfirmationAction.EDIT,
            reviewer_id="ops_lead_01",
            audit_note="Merchant bilateral agreement negotiated platform absorbs override.",
            overrides={"nonline_allocation": NonlineAllocation.platform_absorbs},
        )
        confirmed = human_gate.apply_decision(req, decision)
        assert confirmed.nonline_allocation == NonlineAllocation.platform_absorbs
        assert len(human_gate.audit_log) == 1
        assert human_gate.audit_log[0]["action"] == "EDIT"
        assert human_gate.audit_log[0]["confirmed_nonline"] == "platform_absorbs"

    def test_gate_reject_action(self, human_gate: HumanConfirmationGate, llm_extractor: LLMExtractor):
        c = next(c for c in TIER_C_CLAUSES if c.clause_id == "tc_ctrl_01")
        rule = llm_extractor.extract(c.clause_text)
        req = human_gate.prepare_request(c.clause_text, rule)

        decision = ConfirmationDecision(
            action=ConfirmationAction.REJECT,
            reviewer_id="compliance_auditor_9",
            audit_note="Agreement expired; dispute pending.",
        )
        confirmed = human_gate.apply_decision(req, decision)
        assert confirmed.abstain
        assert confirmed.abstain_reason == AbstainReason.unsupported
        assert confirmed.funding_map is None


# ── 6. End-to-End Allocation Integration ──────────────────────────────────────

class TestEndToEndAllocation:

    def test_confirmed_rule_produces_valid_allocation(
        self,
        human_gate: HumanConfirmationGate,
        llm_extractor: LLMExtractor,
    ):
        cases = generate(GenerationConfig(seed=2701, counts={"A1_shipping_fee": 1}))
        case = cases[0]
        obs = project(case)

        # Extract with LLM
        rule = llm_extractor.extract(obs.agreement_text)
        req = human_gate.prepare_request(obs.agreement_text, rule)
        decision = ConfirmationDecision(
            action=ConfirmationAction.APPROVE,
            reviewer_id="auto_approver",
            audit_note="Auto-approved standard case.",
        )

        pred = human_gate.confirm_and_allocate(obs, req, decision)
        assert not pred.abstained
        assert len(pred.allocations) > 0
        total_bear = sum(pa.allocated_paise for pa in pred.allocations)
        assert total_bear == obs.refunds[0].refund_amount_paise
