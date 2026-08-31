"""
p37.extraction — Deterministic rule extraction (Tier B).

Package boundary: modules in this package must NOT import GroundTruthCase,
AgreementTruth, TrueTransfer, TrueLine, RefundTruth, or GroundTruthResolution.

Exception: oracle_rule.py is explicitly allowed to read hidden types,
but must NOT be imported by extractor.py or allocator.py.
"""
