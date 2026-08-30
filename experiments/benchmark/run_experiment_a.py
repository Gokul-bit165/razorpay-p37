from __future__ import annotations
import json
from pathlib import Path
from p37.benchmark.dataset import config_from_dict, generate_split, BENCHMARK_VERSION, SCHEMA_VERSION, GENERATOR_VERSION, RESOLVER_VERSION
from p37.benchmark.baseline_adapter import predict as legacy_baseline
from p37.benchmark.oracle_rule import oracle_rule
from p37.benchmark.rule_resolver import resolve
from p37.benchmark.project import project
from p37.benchmark.groundtruth import resolve as truth_resolve

ROOT=Path(__file__).resolve().parents[2]
STRATA=["determinate","ambiguous","commission-divergent","boundary","invalid"]
def family(ct):
    return "determinate" if ct.startswith("D") else "ambiguous" if ct.startswith("A") else "commission-divergent" if ct.startswith("C") else "boundary" if ct.startswith("B") else "invalid"

def metrics(cases, predictor):
    out={}
    for fam in STRATA:
        rows=[]
        for c in cases:
            if family(c.case_type)!=fam: continue
            pred=predictor(c); truth=truth_resolve(c)
            pm={x.linked_account_id:x.allocated_paise for x in pred.allocations}
            tm={k:v.bear_paise for k,v in truth.allocations.items()}
            exact=(not pred.abstained and not truth.unresolvable and pm==tm)
            errors=[abs(pm.get(a,0)-tm.get(a,0)) for a in set(pm)|set(tm)]
            false_invalid=truth.unresolvable and not pred.abstained
            wrong=(not pred.abstained) and (truth.unresolvable or pm!=tm)
            rows.append((exact,sum(errors),wrong,false_invalid))
        n=len(rows)
        out[fam]={"n":n,"exact_match":sum(x[0] for x in rows)/n if n else 0.0,"mean_alloc_error_paise":sum(x[1] for x in rows)/n if n else 0.0,"total_misallocated_paise":sum(x[1] for x in rows),"wrong_allocation_rate":sum(x[2] for x in rows)/n if n else 0.0,"false_on_invalid_rate":sum(x[3] for x in rows)/n if n else 0.0}
    return out

def main():
    cfg=config_from_dict(json.loads((ROOT/"data/configs/gen_val.json").read_text()))
    cases,dhash=generate_split(cfg)
    # R0 and R1 use the SAME rule-driven resolver implementation.
    r0=metrics(cases,lambda c: resolve(project(c)))
    r1=metrics(cases,lambda c: resolve(project(c),oracle_rule(c)))
    legacy=metrics(cases,lambda c: legacy_baseline(project(c)))
    r0_regression={s:round(r0[s]['exact_match']-legacy[s]['exact_match'],4) for s in STRATA}
    na,nc=r0['ambiguous']['n'],r0['commission-divergent']['n']
    gate0=(r0['ambiguous']['exact_match']*na+r0['commission-divergent']['exact_match']*nc)/(na+nc)
    gate1=(r1['ambiguous']['exact_match']*na+r1['commission-divergent']['exact_match']*nc)/(na+nc)
    delta=round((gate1-gate0)*100,2)
    verdict='PASS' if delta>=40 else 'FAIL' if delta<10 else 'SPLIT'
    result={"experiment":"A_knowing_the_correct_rule","benchmark_version":BENCHMARK_VERSION,"schema_version":SCHEMA_VERSION,"generator_version":GENERATOR_VERSION,"resolver_version":RESOLVER_VERSION,"dataset_split":"val","dataset_hash":dhash,"R0":r0,"R1":r1,"legacy_baseline_regression_delta":r0_regression,"gate":{"combined_R0":round(gate0,4),"combined_R1":round(gate1,4),"delta_percentage_points":delta,"thresholds":{"PASS":">=40pp","FAIL":"<10pp","SPLIT":"10-40pp"},"verdict":verdict}}
    out=ROOT/"reports/generated/exp_a.json"; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2,sort_keys=True)); print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__': main()
