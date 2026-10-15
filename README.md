# quantum-oracle-forensics

Solver for **Quantum Oracle Forensics** (IBM Qiskit Fall Fest 2026, QC@IITI × QryptoNox):
given a sealed 8-bit oracle `U|x>|y> = |x>|y ⊕ f(x)>` and 60 noisy queries, identify which of
eight families it belongs to and recover its secret.

## Layout

| path | what |
|---|---|
| `solver.py` | the submission: `solve(n, m, budget, families, run) -> (family, secret)` |
| `sim/oracles.py` | random instances of all eight families + the section-4 reference examples |
| `sim/runner.py` | local `run(circuit, shots)`: numpy state-vector simulator with the section-3 noise model (oracle misfire, readout flips), Qiskit bit order and budget enforcement |
| `baselines.py` | section-9 baselines: classical-only, single-algorithm, non-adaptive, random guess |
| `bench.py` | accuracy, worst-family accuracy, query saving, stress noise, confusion matrix, accuracy vs budget; writes `logs/` |
| `tests/` | simulator checks against section 4, bit-order checks, model-vs-simulator checks, solver smoke tests |
| `logs/` | benchmark outputs referenced by the report |

`solver.py` imports only Qiskit, numpy, scipy and the standard library. It never imports
`sim/`; the oracle is reached only through `run()`.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt -r requirements-dev.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt    # Linux / macOS
```

Tested with Python 3.14, Qiskit 2.5.2, numpy 2.5.4, scipy 1.18.1.

## Run

```bash
python -m pytest -q                                   # tests
python bench.py --per-family 50 --workers 8           # full benchmark -> logs/
python bench.py --per-family 10 --only ours,ours_stress   # quick check
```

Use from a judge harness:

```python
from solver import solve
family, secret = solve(8, m, 60, families, run)
```

## Strategy in one paragraph

Every (family, secret) hypothesis allowed by `m` is scored exactly by Bayes' rule using the
section-3 noise model, marginalised over nominal and doubled noise. For `m = 8` a single Simon
sampling circuit suffices; closed-form Walsh-domain likelihoods score all 1 + 255 + 10 795
perm / simon / simon2 hypotheses after every shot. For `m = 1` the solver picks, shot by shot, the
circuit with the highest expected information gain per query from a menu of Deutsch–Jozsa /
Bernstein–Vazirani, "Grover echo" (even numbers of Grover iterations, which return a balanced
function exactly to z = 0 but not a randfun), Grover search, and classical queries. It stops
as soon as the top answer's posterior is at least 1 − δ. Spare qubits hold CNOT copies of measured qubits, so readout
flips show up as detected disagreements instead of silent errors, at no query cost.
Details, thresholds and results are in the report.
