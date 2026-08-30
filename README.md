# Razorpay P37

Research-first prototype for the Razorpay AI Buildathon.

**Selected problem:** P37 — partial-refund allocation and clawback on split payments where contract-specific bearing rules can differ from proportional/default handling.

## Current milestone

**Independent ground-truth benchmark.** The benchmark starts from hidden true transaction state, projects only predictor-visible inputs, and keeps the ground-truth resolver independent from any predictor.

Implemented locally and being mirrored into this repository:

- distinct `GroundTruthCase` / `ObservableCase` models
- one-way projection boundary
- deterministic true-state generator
- integer-paise largest-remainder rounding
- independent ground-truth resolver
- adversarial leakage/boundary tests
- reproducible seeded datasets

## Engineering principle

> Problem → evidence → root cause → decision → hypothesis → baseline → AI necessity → implementation → evaluation.

AI/LLM/agent components will be added only after the benchmark proves exactly where they add measurable value.

## Research

The research decision and benchmark specification are recorded under `research/` and `docs/`.
