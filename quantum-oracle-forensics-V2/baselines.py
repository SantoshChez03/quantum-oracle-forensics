"""Baselines required by section 9 of the statement (used by bench.py, not by the solver).

* classical_only   - never uses superposition: m = 1 runs the Bayesian engine restricted to
                     classical queries; m = 8 queries f at distinct random inputs and looks
                     for output collisions (x XOR x' lies in the hidden subspace).
* single_algorithm - always the same circuit: Deutsch-Jozsa for m = 1, Simon for m = 8.
* non_adaptive     - our circuits and decoder, but a fixed schedule that spends the whole
                     budget (no adaptive choice, no early stopping).
* random_guess     - a uniformly random family allowed by m and a uniformly random secret.
"""
import numpy as np
from qiskit import QuantumCircuit

import solver

M1_SCHEDULE = [("G", 1, True)] * 6 + [("C", None)] * 6 + [("G", 4, True)] * 3 + [("G", 12, False)] * 3


def _classical_m8_circuit(n, m, x, copy_bits):
    qc = QuantumCircuit(n + m + len(copy_bits), m + len(copy_bits))
    for k in range(n):
        if (x >> k) & 1:
            qc.x(k)
    qc.append(solver._oracle(n, m), list(range(n + m)))
    for i, k in enumerate(copy_bits):
        qc.cx(n + k, n + m + i)
    qc.measure(range(n, n + m), range(m))
    for i in range(len(copy_bits)):
        qc.measure(n + m + i, m + i)
    return qc


def classical_m8(n, m, budget, run, rng):
    """Birthday search: collect (x, f(x)); every repeated output gives a difference in H."""
    spare = solver.MAX_QUBITS - n - m
    groups = [tuple(range(spare)), tuple(range(spare, 2 * spare))]
    xs = rng.permutation(2 ** n)[:budget]
    seen = {}
    diffs = {}
    for i, x in enumerate(xs):
        cb = groups[i % 2]
        v = solver._expand_counts(run(_classical_m8_circuit(n, m, int(x), cb), 1))[0]
        y = v & (2 ** m - 1)
        # drop readings whose duplicated bits disagree (a flip was detected)
        if any(((v >> (m + j)) & 1) != ((y >> k) & 1) for j, k in enumerate(cb)):
            continue
        if y in seen:
            for x2 in seen[y]:
                d = int(x) ^ x2
                diffs[d] = diffs.get(d, 0) + 1
            seen[y].append(int(x))
        else:
            seen[y] = [int(x)]
    if not diffs:
        return "perm", None
    ranked = sorted(diffs, key=lambda d: -diffs[d])
    a = ranked[0]
    for b in ranked[1:]:
        if b != a:
            return "simon2", sorted([a, b, a ^ b])
    return "simon", a


def classical_only(n, m, budget, families, run, rng):
    if m == 1:
        return solver.solve_m1(n, budget, families, run, menu=("classical",), rng=rng)
    return classical_m8(n, m, budget, run, rng)


def single_algorithm(n, m, budget, families, run, rng):
    if m == 1:
        return solver.solve_m1(n, budget, families, run, menu=("dj",), rng=rng)
    return solver.solve_m8(n, m, budget, families, run)


def non_adaptive(n, m, budget, families, run, rng):
    if m == 1:
        return solver.solve_m1(n, budget, families, run, rng=rng, schedule=M1_SCHEDULE)
    return solver.solve_m8(n, m, budget, families, run, fixed_shots=budget)


def random_guess(n, m, budget, families, run, rng):
    fams = [f for f in families if f in (solver.M1_FAMILIES if m == 1 else solver.M8_FAMILIES)]
    fam = fams[rng.integers(len(fams))]
    N = 2 ** n
    if fam == "constant":
        return fam, int(rng.integers(2))
    if fam == "linear":
        return fam, [int(rng.integers(1, N)), int(rng.integers(2))]
    if fam == "grover":
        return fam, int(rng.integers(N))
    if fam == "simon":
        return fam, int(rng.integers(1, N))
    if fam == "simon2":
        a = int(rng.integers(1, N))
        b = int(rng.integers(1, N))
        while b == a:
            b = int(rng.integers(1, N))
        return fam, sorted([a, b, a ^ b])
    return fam, None
