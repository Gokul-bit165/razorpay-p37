# P37 — Independent Ground-Truth Benchmark

This milestone implements the benchmark contract defined by the research specification.

## Core guarantee

Ground truth is generated from hidden world state. Predictors receive only an observable projection. The ground-truth resolver does not import predictor/baseline code.

## Versions

- schema_version: 1.0
- generator_version: 1.0
- resolver_version: 1.0
- benchmark_version: 1.0

## Split policy

- `dev`: inspectable during development
- `val`: balanced coverage across case families
- `test`: separate seed/distribution, reserved for final evaluation

Generated datasets are deterministic and content-hashed.
