from __future__ import annotations

import json
from pathlib import Path

from p37.benchmark.generator import GenerationConfig, generate
from p37.benchmark.groundtruth import resolve
from p37.benchmark.project import observable_to_json, project

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    cfg = json.loads((ROOT / "data/configs/gen_val.json").read_text())
    cases = generate(GenerationConfig(seed=int(cfg["seed"]), counts=cfg["counts"]))
    for case in cases:
        truth = resolve(case)
        observed = project(case)
        payload = observable_to_json(observed)
        assert all(name not in payload for name in ("funding_map", "true_fulfilling_account", "true_commission_treatment", "balance_timeline", "true_line_coverage", "true_reason", "case_type"))
        if not truth.unresolvable:
            assert sum(a.bear_paise for a in truth.allocations.values()) <= case.refund.refund_amount_paise
    print(f"benchmark integrity OK: {len(cases)} cases")


if __name__ == "__main__":
    main()
