# Project status: Quantum Oracle Forensics

*Updated after the code review and the final benchmark. See `MANUAL.md` for the full
history and methodology.*

---

## 1. Done

### 1.1 Environment
- Virtual environment `.venv`; tested with Python 3.13–3.14, Qiskit 2.5.2, numpy 2.x, scipy 1.18.
- `requirements.txt`: qiskit, numpy, scipy (the only libraries the rules allow).
  `requirements-dev.txt`: pytest.

### 1.2 Local simulator (`sim/`)
- `sim/oracles.py`: random instances of all 8 families and the section 4 examples.
- `sim/runner.py`: `OracleRunner(oracle)` with the same interface as `run(circuit, shots)`.
  It substitutes the oracle placeholder, applies per-shot per-call misfires and readout flips,
  returns Qiskit-order counts, counts queries and raises `BudgetExceeded`, and
  (new) rejects any gate after a measurement.
- Verified against the section 4 values, Qiskit's `Statevector`, and a second independently
  written simulator (differences below 10⁻¹³).

### 1.3 Solver (`solver.py`, the submission)
- Exact Bayesian inference over every (family, secret) hypothesis, noise level marginalised
  over nominal and doubled, information-gain experiment choice, stopping at posterior ≥ 1 − δ
  (δ = 0.003), readout repetition on spare qubits.
- Review changes:
  - repeated classical reads of the same input are now modelled correctly for balanced /
    randfun (f(x) is fixed, so reads are only independent given f(x));
  - the solver's own random choices use a fixed seed, so runs are reproducible.

### 1.4 Baselines, benchmark, reference
- `baselines.py`: classical-only, single-algorithm, non-adaptive, random guess.
- `bench.py`: paired benchmark on fixed seeds. New options:
  - `--reference` adds `reference/claude_solver.py` (an independent second solver);
  - `--update --only ... --families ...` reruns part of an existing log in place.
- `report_tables.py`: prints the report's tables from a benchmark log.

### 1.5 Tests (34 passing)
- `tests/test_sim.py` (25): section 4 values, bit order, BV/Simon sanity, two-level model,
  budget, solver on reference examples and noisy smoke tests.
- `tests/test_compliance.py` (9, new): simulator vs Qiskit `Statevector`; measurements at
  the end and ≤ 20 qubits for every solver circuit; solver imports only allowed modules and
  never `sim/`; `solve()` is reproducible.

### 1.6 Results (`logs/summary_final.md`, 50 oracles per family)
See `REPORT.md` §4 and `MANUAL.md` §7.

### 1.7 Documents
- `README.md`, `REPORT.md` (sections 3–5 now filled), `AI_USE.md` (updated, still to be
  signed), `MANUAL.md` (new).

---

## 2. Left to do

### Must do
- [ ] Add team names to `REPORT.md`; check it renders to at most 3 pages.
- [ ] Team review of `AI_USE.md`: names, what you checked by hand, sign.
- [ ] Commit, push, **tag** the submission commit, make sure the repository is public.

### Should do
- [ ] Clean-install check on a fresh clone: `pip install -r requirements.txt -r requirements-dev.txt`
      then `python -m pytest -q`.
- [ ] Decide whether to keep the large `logs/bench_*.json` files in the repository
      (`bench_final.json` is ~1.8 MB; the report cites `summary_final.md`).

### Could do
- [ ] Grover under stress noise is the weakest family (0.96); a flag oracle call in search
      shots (tried in the reference solver) did not beat the current design, so no change made.
- [ ] Calibration plot: posterior at stopping vs observed error rate, from `bench_final.json`.
- [ ] Optional 3-minute video.
