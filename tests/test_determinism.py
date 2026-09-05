"""
Determinism and zero-drift verification test suite (P0-5).

Ensures that benchmark runs, generator outputs, and ladder evaluations
produce 100% bitwise-identical results across repeated runs.
Runs strictly inside pytest's isolated tmp_path so the repository working tree
is never dirtied.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from p37.benchmark.contract_renderer import ContractRenderer
from p37.benchmark.generator import GenerationConfig, generate
from p37.benchmark.groundtruth import resolve
from p37.benchmark.project import project
from p37.extraction.allocator import allocate
from p37.extraction.extractor import extract as extract_regex
from p37.extraction.llm_client import MockLLMClient
from p37.extraction.llm_extractor import LLMExtractor
from p37.extraction.oracle_rule import oracle_rule


def _execute_isolated_ladder(out_dir: Path) -> dict[str, str]:
    """Execute ladder evaluation and save to out_dir, returning {filename: file_content}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = REPO_ROOT / "data" / "configs" / "gen_val.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    cases = generate(GenerationConfig(seed=cfg["seed"], counts=cfg["counts"]))
    _EXPERIMENT_A_TYPES = sorted([
        "A1_shipping_fee", "A2_goodwill_credit", "A3_discount_funded",
        "A4_platform_fee_only", "C1_commission_retained",
        "C2_commission_full_return", "N4_line_maps_to_multiple",
    ])
    subset = [c for c in cases if c.case_type in _EXPERIMENT_A_TYPES]

    renderer = ContractRenderer(seed=3701)
    llm = LLMExtractor(client=MockLLMClient())

    file_contents = {}
    for regime in ["a", "b", "c"]:
        results = {}
        for idx, c in enumerate(subset):
            text = renderer.render(c, regime, idx)
            obs = project(c)
            # Recreate obs with rendered text
            from dataclasses import replace
            obs_rendered = replace(obs, agreement_text=text)
            pred = allocate(obs_rendered, llm.extract(text))
            results[c.case_id] = {
                "abstained": pred.abstained,
                "allocations": [(pa.linked_account_id, pa.allocated_paise) for pa in pred.allocations],
            }

        fname = f"ladder_regime_{regime}.json"
        content = json.dumps(results, indent=2, sort_keys=True)
        (out_dir / fname).write_text(content, encoding="utf-8")
        file_contents[fname] = content

    return file_contents


def test_consecutive_runs_produce_bit_identical_outputs(tmp_path: Path):
    """Verify two independent runs into isolated directories are byte-identical."""
    run1_dir = tmp_path / "run_1"
    run2_dir = tmp_path / "run_2"

    contents_1 = _execute_isolated_ladder(run1_dir)
    contents_2 = _execute_isolated_ladder(run2_dir)

    assert set(contents_1.keys()) == set(contents_2.keys())
    for fname in contents_1:
        assert contents_1[fname] == contents_2[fname], f"Bitwise drift detected in {fname}"


def test_generator_determinism(tmp_path: Path):
    """Verify transaction generation config produces identical cases."""
    cfg_path = REPO_ROOT / "data" / "configs" / "gen_val.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    cases_a = generate(GenerationConfig(seed=cfg["seed"], counts=cfg["counts"]))
    cases_b = generate(GenerationConfig(seed=cfg["seed"], counts=cfg["counts"]))

    assert len(cases_a) == len(cases_b)
    for ca, cb in zip(cases_a, cases_b):
        assert ca.case_id == cb.case_id
        assert ca.gross_amount_paise == cb.gross_amount_paise
        assert ca.funding_map == cb.funding_map
