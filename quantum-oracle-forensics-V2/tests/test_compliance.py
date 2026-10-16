"""Rule-compliance and independent-verification tests (added during the code review).

* the simulator agrees with Qiskit's own Statevector when the oracle is an explicit unitary
* every circuit the solver builds keeps measurements at the end and stays within 20 qubits
* solver.py imports only qiskit / numpy / scipy / the standard library and never sim/
* solve() is reproducible when run() is seeded
"""
import ast
import sys
from pathlib import Path

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import UnitaryGate
from qiskit.quantum_info import Statevector

from sim.oracles import FAMILIES, random_oracle, reference_examples
from sim.runner import OracleRunner, measured_distribution
from solver import (MAX_QUBITS, classical_circuit, grover_circuit, m1_copies, simon_circuit,
                    solve)

ROOT = Path(__file__).resolve().parents[1]


def _oracle_unitary(f, m=1, n=8):
    """|x>|y> -> |x>|y xor f(x)> as an explicit permutation matrix (Qiskit little-endian)."""
    dim = 2 ** (n + m)
    U = np.zeros((dim, dim))
    for idx in range(dim):
        x, y = idx & (2 ** n - 1), idx >> n
        U[x | ((y ^ int(f[x])) << n), idx] = 1
    return UnitaryGate(U, label="oracle")


def _qiskit_distribution(qc, f, m=1):
    gate = _oracle_unitary(f, m)
    plain = QuantumCircuit(qc.num_qubits)
    meas = []
    for inst in qc.data:
        qs = [qc.find_bit(q).index for q in inst.qubits]
        if inst.operation.name == "measure":
            meas.append((qs[0], qc.find_bit(inst.clbits[0]).index))
        else:
            plain.append(gate if inst.operation.name == "oracle" else inst.operation, qs)
    dist = np.zeros(2 ** qc.num_clbits)
    for key, p in Statevector(plain).probabilities_dict().items():
        v, val = int(key, 2), 0
        for q, c in meas:
            val |= ((v >> q) & 1) << c
        dist[val] += p
    return dist


@pytest.mark.parametrize("family", ["linear", "grover", "balanced", "randfun", "constant"])
def test_simulator_matches_qiskit_statevector(family):
    o = random_oracle(family, np.random.default_rng(11))
    circuits = [grover_circuit(8, 1, True), grover_circuit(8, 2, True),
                grover_circuit(8, 4, False), classical_circuit(8, 77, 1, copies=3)]
    for qc in circuits:
        k = sum(i.operation.name == "oracle" for i in qc.data)
        ours, _ = measured_distribution(qc, o.f, 8, [True] * k)
        ref = _qiskit_distribution(qc, o.f)
        assert np.abs(ours - ref).max() < 1e-9


def _solver_circuits():
    yield grover_circuit(8, 1, True, m1_copies(8))
    yield grover_circuit(8, 4, True, m1_copies(8))
    yield grover_circuit(8, 12, False, m1_copies(8))
    yield classical_circuit(8, 200, 1, copies=3)
    yield simon_circuit(8, 8, (0, 1, 2, 3))
    yield simon_circuit(8, 8, (4, 5, 6, 7))


def test_measurements_at_end_and_qubit_cap():
    for qc in _solver_circuits():
        assert qc.num_qubits <= MAX_QUBITS
        measured = set()
        for inst in qc.data:
            qs = {qc.find_bit(q).index for q in inst.qubits}
            if inst.operation.name == "measure":
                measured |= qs
            else:
                assert not (measured & qs), "gate after measurement"


def test_runner_rejects_gate_after_measurement():
    qc = QuantumCircuit(9, 1)
    qc.measure(0, 0)
    qc.x(0)
    with pytest.raises(ValueError):
        measured_distribution(qc, reference_examples()["grover"].f, 8, [])


def test_solver_imports_only_allowed_modules():
    tree = ast.parse((ROOT / "solver.py").read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module.split(".")[0])
    allowed = {"qiskit", "numpy", "scipy"} | set(sys.stdlib_module_names)
    assert mods <= allowed, mods - allowed
    assert "sim" not in mods


def test_solve_is_reproducible():
    o = random_oracle("randfun", np.random.default_rng(5))
    answers = []
    for _ in range(2):
        run = OracleRunner(o, seed=99)
        answers.append((solve(8, 1, 60, list(FAMILIES), run), run.queries))
    assert answers[0] == answers[1]
