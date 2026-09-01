"""
test_tier_c_role_binding.py

Phase-3 test suite covering:
  1. Role-binding extraction accuracy on canonical binding clauses.
  2. Conflict abstention on one-role → two-accounts cases.
  3. Amendment override precedence (last amendment wins for that role).
  4. Hard allocation ladder assertion: R2-Bound − R0 ≥ 0.5714 − epsilon.
  5. Tier-C failure-mode categorisation completeness (all 6 categories present).
  6. Backward-compatibility: existing R0/R1 construction paths produce valid
     StructuredRule objects after models.py change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure src is on sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from p37.extraction.extractor import extract
from p37.extraction.models import (
    AbstainReason,
    CommissionTreatment,
    NonlineAllocation,
    StructuredRule,
    TierCFailureCategory,
)
from p37.extraction.tier_c_dataset import TIER_C_CLAUSES
from p37.benchmark.models import ObservableCase


# ── 1. Role-binding extraction — canonical pattern ────────────────────────────

class TestRoleBindingCanonical:

    def _text_with_binding(self, account_id: str, role: str) -> str:
        return (
            "Refund allocation agreement:\n"
            "Goods: refund bears with the fulfilling vendor.\n"
            "Shipping: refund bears with the shipping-funding party.\n"
            "Platform fee: refund bears with the platform.\n"
            "Discount adjustments: refund bears with the party that funded the discount.\n"
            f"Non-line refund rule: {role} funder.\n"
            f"Funding account: {account_id} is designated {role}.\n"
            "Recovery order: acc_test_0 then acc_test_1."
        )

    def test_shipping_role_extracted(self):
        text = self._text_with_binding("acc_00060_1", "shipping")
        rule = extract(text)
        assert not rule.abstain
        assert rule.funding_map is not None
        assert rule.funding_map.get("shipping") == "acc_00060_1"

    def test_platform_role_extracted(self):
        text = self._text_with_binding("acc_00080_0", "platform")
        rule = extract(text)
        assert not rule.abstain
        assert rule.funding_map is not None
        assert rule.funding_map.get("platform") == "acc_00080_0"

    def test_discount_role_extracted(self):
        text = self._text_with_binding("acc_00100_1", "discount")
        rule = extract(text)
        assert not rule.abstain
        assert rule.funding_map is not None
        assert rule.funding_map.get("discount") == "acc_00100_1"

    def test_multiple_roles_same_account_allowed(self):
        """Two roles → same account is valid (multi-role account)."""
        text = (
            "Refund allocation agreement:\n"
            "Non-line refund rule: shipping funder.\n"
            "Funding account: acc_shared is designated shipping.\n"
            "Funding account: acc_shared is designated platform.\n"
            "Recovery order: acc_shared."
        )
        rule = extract(text)
        assert not rule.abstain
        assert rule.funding_map.get("shipping") == "acc_shared"
        assert rule.funding_map.get("platform") == "acc_shared"

    def test_same_role_same_account_duplicate_is_idempotent(self):
        """Same role → same account stated twice: deduplicate silently, no abstain."""
        text = (
            "Refund allocation agreement:\n"
            "Non-line refund rule: shipping funder.\n"
            "Funding account: acc_ship is designated shipping.\n"
            "Funding account: acc_ship is designated shipping.\n"
            "Recovery order: acc_ship."
        )
        rule = extract(text)
        assert not rule.abstain
        assert rule.funding_map.get("shipping") == "acc_ship"

    def test_role_binding_span_is_valid(self):
        """role_binding_spans must contain a valid SourceSpan for each role bound."""
        text = self._text_with_binding("acc_00060_1", "shipping")
        rule = extract(text)
        assert "shipping" in rule.role_binding_spans
        span = rule.role_binding_spans["shipping"]
        assert span.validate(text), "role_binding span positional validation failed"
        assert span.field_name == "role_shipping"

    def test_no_binding_clause_returns_none_funding_map(self):
        """Agreement text without a Funding account clause → funding_map is None."""
        text = (
            "Refund allocation agreement:\n"
            "Non-line refund rule: shipping funder.\n"
            "Commission is retained on refunds.\n"
            "Recovery order: acc_test_0 then acc_test_1."
        )
        rule = extract(text)
        assert not rule.abstain
        assert rule.funding_map is None
        assert rule.role_binding_spans == {}


# ── 2. Conflict abstention ────────────────────────────────────────────────────

class TestRoleBindingConflict:

    def test_one_role_two_accounts_abstains(self):
        """One role → two different accounts: must abstain with role_binding_conflict."""
        text = (
            "Refund allocation agreement:\n"
            "Non-line refund rule: shipping funder.\n"
            "Funding account: acc_A is designated shipping.\n"
            "Funding account: acc_B is designated shipping.\n"
            "Recovery order: acc_A then acc_B."
        )
        rule = extract(text)
        assert rule.abstain
        assert rule.abstain_reason == AbstainReason.role_binding_conflict
        assert rule.funding_map is None

    def test_conflict_clears_all_extracted_fields(self):
        """On role_binding_conflict, all fields are unknown (not partial result)."""
        text = (
            "Refund allocation agreement:\n"
            "Non-line refund rule: proportional.\n"
            "Commission is returned in full.\n"
            "Funding account: acc_A is designated platform.\n"
            "Funding account: acc_B is designated platform.\n"
            "Recovery order: acc_A then acc_B."
        )
        rule = extract(text)
        assert rule.abstain
        assert rule.nonline_allocation == NonlineAllocation.unknown
        assert rule.commission_treatment == CommissionTreatment.unknown
        assert rule.recovery_order == ()


# ── 3. Amendment override ─────────────────────────────────────────────────────

class TestAmendmentOverride:

    def test_amendment_overrides_earlier_binding_for_role(self):
        """AMENDMENT: header causes last-amendment-wins override for that role."""
        text = (
            "Original:\n"
            "Funding account: acc_original is designated shipping.\n"
            "\n"
            "AMENDMENT:\n"
            "Funding account: acc_amended is designated shipping.\n"
            "\n"
            "Non-line refund rule: shipping funder.\n"
            "Recovery order: acc_amended."
        )
        rule = extract(text)
        assert not rule.abstain
        assert rule.funding_map.get("shipping") == "acc_amended"

    def test_amendment_only_overrides_its_role(self):
        """Amendment overrides only the stated role; other roles keep first-mention."""
        text = (
            "Base agreement:\n"
            "Funding account: acc_platform_orig is designated platform.\n"
            "Funding account: acc_shipping_orig is designated shipping.\n"
            "\n"
            "AMENDMENT:\n"
            "Funding account: acc_shipping_new is designated shipping.\n"
            "\n"
            "Non-line refund rule: shipping funder.\n"
            "Recovery order: acc_shipping_new then acc_platform_orig."
        )
        rule = extract(text)
        assert not rule.abstain
        assert rule.funding_map.get("shipping") == "acc_shipping_new"
        assert rule.funding_map.get("platform") == "acc_platform_orig"

    def test_non_amendment_conflict_still_abstains(self):
        """Without AMENDMENT: header, two different accounts for same role → abstain."""
        text = (
            "Clause A: Funding account: acc_A is designated platform.\n"
            "Clause B: Funding account: acc_B is designated platform.\n"
            "Non-line refund rule: platform absorbs."
        )
        rule = extract(text)
        assert rule.abstain
        assert rule.abstain_reason == AbstainReason.role_binding_conflict


# ── 4. Hard allocation ladder assertion ───────────────────────────────────────

EPSILON = 0.001

class TestRoleBindingLadder:

    def _load_val_cases(self):
        """Load frozen validation set using the same config as run_tier_b.py."""
        import json
        from pathlib import Path
        from p37.benchmark.generator import GenerationConfig, generate
        root = Path(__file__).resolve().parents[1]
        config_path = root / "data" / "configs" / "gen_val.json"
        cfg = json.loads(config_path.read_text())
        return generate(GenerationConfig(seed=cfg["seed"], counts=cfg["counts"]))

    def _build_experiment_a_subset(self, all_cases):
        """140 ambiguous + commission-divergent cases matching experiment A."""
        target_types = {
            "A1_shipping_fee", "A2_goodwill_credit", "A3_discount_funded",
            "A4_platform_fee_only", "A5_proportional_cancellation",
            "C1_commission_retained", "C2_commission_full_return",
        }
        return [c for c in all_cases if c.case_type in target_types]

    def test_r2_bound_improvement_over_r0(self):
        """
        R2-Bound (extractor with role-binding) − R0 (default baseline) ≥ 0.5714 − epsilon
        on the 140 divergent validation cases.

        This is the hard assertion (D5) that verifies role-binding closes the oracle gap.
        Failure means the role-binding clause is not present in the benchmark-generated
        agreement text, or the extraction/allocation has a bug.
        """
        from p37.benchmark.groundtruth import resolve
        from p37.benchmark.project import project
        from p37.extraction.allocator import allocate
        from p37.extraction.oracle_rule import oracle_rule
        from p37.extraction.models import (
            AbstainReason as AR,
            NonlineAllocation as NL,
            CommissionTreatment as CT,
            StructuredRule,
        )

        all_cases = self._load_val_cases()
        subset = self._build_experiment_a_subset(all_cases)

        if not subset:
            pytest.skip("Could not load validation cases — check project config.")

        r0_correct = 0
        r2_bound_correct = 0
        r1_correct = 0
        total_resolvable = 0

        for gt_case in subset:
            gt_res = resolve(gt_case)
            if gt_res.unresolvable:
                continue
            total_resolvable += 1

            obs = project(gt_case)
            agreement_text = obs.agreement_text

            # R0: default assumptions
            r0_rule = StructuredRule(
                nonline_allocation=NL.proportional,
                commission_treatment=CT.unknown,
                recovery_order=tuple(t.linked_account_id for t in obs.transfers),
                funding_map=None,
                principal_bearer_verified=False,
                abstain=False,
                abstain_reason=AR.none,
                spans={},
            )
            r0_pred = allocate(obs, r0_rule)

            # R2-Bound: extractor with role-binding
            r2_rule = extract(agreement_text)
            r2_pred = allocate(obs, r2_rule)

            # R1: oracle
            r1_rule = oracle_rule(gt_case)
            r1_pred = allocate(obs, r1_rule)

            # Exact match: compare bear_paise per account
            def exact_match(pred, gt_resolution) -> bool:
                if pred.abstained:
                    return False
                pred_map = {a.linked_account_id: a.allocated_paise for a in pred.allocations}
                gt_map = {acc: alloc.bear_paise for acc, alloc in gt_resolution.allocations.items()}
                return pred_map == gt_map

            if exact_match(r0_pred, gt_res):
                r0_correct += 1
            if exact_match(r2_pred, gt_res):
                r2_bound_correct += 1
            if exact_match(r1_pred, gt_res):
                r1_correct += 1

        assert total_resolvable > 0, "No resolvable cases found in experiment-A subset"

        r0_rate = r0_correct / total_resolvable
        r2_rate = r2_bound_correct / total_resolvable
        r1_rate = r1_correct / total_resolvable
        improvement = r2_rate - r0_rate

        print(f"\nAllocation ladder ({total_resolvable} resolvable cases):")
        print(f"  R0 (default):      {r0_correct}/{total_resolvable} = {r0_rate:.4f}")
        print(f"  R1 (oracle):       {r1_correct}/{total_resolvable} = {r1_rate:.4f}")
        print(f"  R2-Bound:          {r2_bound_correct}/{total_resolvable} = {r2_rate:.4f}")
        print(f"  R2-Bound − R0:     {improvement:+.4f}")

        assert improvement >= 0.5714 - EPSILON, (
            f"FAIL: R2-Bound improvement {improvement:.4f} < expected {0.5714 - EPSILON:.4f}. "
            f"Role-binding failed to close the oracle gap. "
            f"R0={r0_rate:.4f}, R1={r1_rate:.4f}, R2={r2_rate:.4f}"
        )


# ── 5. Tier-C failure-mode categorisation ─────────────────────────────────────

class TestTierCCategories:

    def test_all_six_categories_present(self):
        """All six TierCFailureCategory values must appear in the dataset."""
        found = {clause.failure_category for clause in TIER_C_CLAUSES}
        for category in TierCFailureCategory:
            assert category in found, (
                f"Missing Tier-C category: {category.value}. "
                f"Add at least one clause with this category to tier_c_dataset.py."
            )

    def test_dataset_has_15_clauses(self):
        assert len(TIER_C_CLAUSES) == 15

    def test_control_clauses_extract_correctly(self):
        """Clauses tagged canonical_succeeds must be correctly extracted by regex."""
        for clause in TIER_C_CLAUSES:
            if not clause.regex_expected_to_succeed:
                continue
            rule = extract(clause.clause_text)
            assert not rule.abstain, (
                f"Clause {clause.clause_id} expected to succeed but abstained: "
                f"{rule.abstain_reason}"
            )
            assert rule.nonline_allocation == clause.expected_nonline, (
                f"Clause {clause.clause_id}: nonline mismatch. "
                f"Got {rule.nonline_allocation}, expected {clause.expected_nonline}"
            )

    def test_failure_clauses_do_not_hallucinate_canonical(self):
        """
        Clauses tagged regex_expected_to_succeed=False must NOT return
        canonical nonline values that don't appear literally in the text.
        (They may return unknown or a wrong match — both are acceptable
        for the failure-mode categorisation purpose.)
        """
        for clause in TIER_C_CLAUSES:
            if clause.regex_expected_to_succeed:
                continue
            try:
                rule = extract(clause.clause_text)
                # If extraction succeeded (not abstained), ensure the returned
                # nonline value matches the expectation (which may be wrong/unknown).
                if not rule.abstain:
                    assert rule.nonline_allocation == clause.expected_nonline, (
                        f"Clause {clause.clause_id}: unexpected nonline. "
                        f"Got {rule.nonline_allocation}, expected {clause.expected_nonline}"
                    )
            except Exception as e:
                pytest.fail(
                    f"Clause {clause.clause_id} raised an exception: {e}"
                )


# ── 6. Backward-compatibility ─────────────────────────────────────────────────

class TestBackwardCompatibility:

    def test_oracle_rule_still_produces_valid_structured_rule(self):
        """oracle_rule() must produce a valid StructuredRule with the new model."""
        import json
        from pathlib import Path
        from p37.benchmark.generator import GenerationConfig, generate
        from p37.extraction.oracle_rule import oracle_rule

        root = Path(__file__).resolve().parents[1]
        config_path = root / "data" / "configs" / "gen_val.json"
        cfg = json.loads(config_path.read_text())
        cases = generate(GenerationConfig(seed=cfg["seed"], counts=cfg["counts"]))
        sample = cases[:5]
        for case in sample:
            rule = oracle_rule(case)
            assert isinstance(rule, StructuredRule)
            assert rule.role_binding_spans == {}  # default, not populated by oracle path

    def test_manual_r0_construction_works(self):
        """Manually constructed R0 StructuredRule must work without role_binding_spans arg."""
        rule = StructuredRule(
            nonline_allocation=NonlineAllocation.proportional,
            commission_treatment=CommissionTreatment.unknown,
            recovery_order=("acc_0", "acc_1"),
            funding_map=None,
            principal_bearer_verified=False,
            abstain=False,
            abstain_reason=AbstainReason.none,
            spans={},
            # role_binding_spans omitted — must default to {}
        )
        assert rule.role_binding_spans == {}

    def test_existing_tier_b_clean_clauses_still_extract(self):
        """All 12 Tier-B clean clauses must still extract without abstaining."""
        from p37.extraction.tier_b_dataset import TIER_B_CLEAN
        for clause in TIER_B_CLEAN:
            rule = extract(clause.clause_text)
            assert not rule.abstain, (
                f"Clause {clause.clause_id} now abstains after Phase-3 changes: "
                f"{rule.abstain_reason}"
            )
            assert rule.nonline_allocation == clause.true_structure.nonline_allocation, (
                f"Clause {clause.clause_id}: nonline regression. "
                f"Got {rule.nonline_allocation}, expected {clause.true_structure.nonline_allocation}"
            )
