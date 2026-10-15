import numpy as np
import pytest
from qiskit import QuantumCircuit

from sim.oracles import FAMILIES, random_oracle, reference_examples
from sim.runner import BudgetExceeded, OracleRunner
from solver import classical_circuit, grover_circuit, simon_circuit, solve, two_level

REF = reference_examples()


def test_section4_check_values():
    f = {k: o.f for k, o in REF.items()}
    assert [f["linear"][x] for x in (0, 1, 2, 255)] == [1, 1, 0, 1]
    assert [f["simon"][x] for x in (5, 108, 105, 200)] == [5, 5, 0, 161]
    assert [f["simon2"][x] for x in (0, 15, 49, 62, 1, 200)] == [0, 0, 0, 0, 1, 199]
    assert [f["perm"][x] for x in (0, 1, 2, 255)] == [11, 48, 85, 230]
    assert f["grover"][173] == 1 and f["grover"].sum() == 1
    assert (f["constant"] == 1).all()


@pytest.mark.parametrize("x", [0, 1, 2, 77, 255])
def test_classical_query_reads_f(x):
    for o in (REF["linear"], REF["grover"], REF["constant"]):
        run = OracleRunner(o, p_misfire=0, p_flip=0, seed=1)
        for y0 in (0, 1):
            counts = run(classical_circuit(8, x, y0), 1)
            assert int(next(iter(counts)), 2) == o.f[x] ^ y0


def test_m8_classical_readout_bit_order():
    """Write f(x) into the output register and read it back: qubit k must be bit k."""
    o = REF["perm"]
    run = OracleRunner(o, p_misfire=0, p_flip=0, seed=1)
    for x in (0, 1, 2, 255, 100):
        qc = QuantumCircuit(16, 8)
        for k in range(8):
            if (x >> k) & 1:
                qc.x(k)
        from solver import _oracle
        qc.append(_oracle(8, 8), range(16))
        qc.measure(range(8, 16), range(8))
        assert int(next(iter(run(qc, 1))), 2) == o.f[x]


def test_bernstein_vazirani_noise_free():
    run = OracleRunner(REF["linear"], p_misfire=0, p_flip=0, seed=1)
    counts = run(grover_circuit(8, 1, True), 20)
    assert counts == {format(178, "08b"): 20}


def test_simon_samples_orthogonal_to_s():
    run = OracleRunner(REF["simon"], p_misfire=0, p_flip=0, seed=1)
    for key in run(simon_circuit(8, 8), 30):
        assert bin(int(key, 2) & 105).count("1") % 2 == 0


def test_two_level_model_matches_simulator():
    o = REF["grover"]
    run = OracleRunner(o, budget=10 ** 6, p_misfire=0, p_flip=0, seed=1)
    from sim.runner import measured_distribution
    for j in (1, 4, 10):
        dist, _ = measured_distribution(grover_circuit(8, j, False), o.f, 8, [True] * j)
        _, pg = two_level([1 / 256], j, 0.0)
        assert abs(dist[173] - pg[0]) < 1e-9
        dist, _ = measured_distribution(grover_circuit(8, j, True), o.f, 8, [True] * j)
        p0, _ = two_level([1 / 256], j, 0.0)
        assert abs(dist[0] - p0[0]) < 1e-9


def test_budget_enforced():
    run = OracleRunner(REF["grover"], budget=10)
    with pytest.raises(BudgetExceeded):
        run(grover_circuit(8, 6, False), 2)


@pytest.mark.parametrize("name", list(REF))
def test_solver_on_reference_examples_noise_free(name):
    o = REF[name]
    run = OracleRunner(o, p_misfire=0, p_flip=0, seed=3)
    fam, secret = solve(8, o.m, 60, list(FAMILIES), run)
    assert fam == o.family and secret == o.secret
    assert run.queries <= 60


@pytest.mark.parametrize("family", FAMILIES)
def test_solver_random_noisy(family):
    rng = np.random.default_rng(7)
    ok = 0
    for i in range(5):
        o = random_oracle(family, rng)
        run = OracleRunner(o, seed=i)
        fam, secret = solve(8, o.m, 60, list(FAMILIES), run)
        ok += fam == o.family and secret == o.secret
    assert ok >= 3
