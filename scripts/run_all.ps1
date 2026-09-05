# PowerShell runner for Windows development environments
param(
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

switch ($Target) {
    "test" {
        py -m pytest tests/ -v
    }
    "bench" {
        py experiments/run_tier_b.py
        py experiments/run_tier_c.py
        py experiments/run_phase4_llm.py
    }
    "demo" {
        py -m streamlit run app.py
    }
    "all" {
        py -m pytest tests/ -v
        py experiments/run_tier_b.py
        py experiments/run_tier_c.py
        py experiments/run_phase4_llm.py
    }
    default {
        Write-Host "Unknown target: $Target. Supported: test, bench, demo, all"
        exit 1
    }
}
