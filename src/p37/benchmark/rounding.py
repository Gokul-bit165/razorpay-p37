from __future__ import annotations


def largest_remainder(total: int, numerators: list[int], denominators: list[int], keys: list[str]) -> list[int]:
    if total < 0 or len(numerators) != len(denominators) or len(keys) != len(numerators):
        raise ValueError("invalid largest-remainder inputs")
    if any(d <= 0 for d in denominators):
        raise ValueError("denominators must be positive")
    raw = [total * n / d for n, d in zip(numerators, denominators)]
    floors = [int(x) for x in raw]
    leftover = total - sum(floors)
    ranked = sorted(range(len(raw)), key=lambda i: (-(raw[i] - floors[i]), keys[i]))
    result = floors[:]
    for i in ranked[:leftover]:
        result[i] += 1
    return result
