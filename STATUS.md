# Project status: Quantum Oracle Forensics

*Snapshot taken while the final benchmark run (`--tag final`) is still in progress. Nothing has been committed or pushed yet.*

---

## 1. Done so far

### 1.1 Environment
- Created a project virtual environment `.venv` with Python 3.14.8, Qiskit 2.5.2, numpy 2.5.4, scipy 1.18.1 and pytest.
- `requirements.txt` lists qiskit, numpy and scipy, the only libraries the rules allow. `requirements-dev.txt` adds pytest.
- Added `.gitignore` and `pytest.ini`.

### 1.2 Local simulator (`sim/`), which stands in for the judges' `run()`
- **`sim/oracles.py`** builds random instances of all 8 families:
  - constant, balanced (exactly 128 ones), linear (a ≠ 0, b), grover (one marked t), randfun (each f(x) = 1 with p = 0.3)
  - simon, simon2 (random output labels per coset), perm
  - the section 4 reference examples, built exactly as the statement gives them
- **`sim/runner.py`** provides `OracleRunner(oracle)`, a callable with the same interface as `run(circuit, shots)`:
  - Replaces the `Gate("oracle", n+m)` placeholder with |x⟩|y⟩ → |x⟩|y ⊕ f(x)⟩, with qubit k as bit k.
  - Noise: each oracle call misfires (acts as the identity) per shot with probability p; each measured bit flips with probability p. Both rates can be changed, which gives the stress setting.
  - Returns counts in Qiskit bit order (clbit 0 rightmost).
  - Counts queries (oracle gates × shots) and raises `BudgetExceeded` if the solver goes over budget.
  - Speed:
    - Only allocates qubits once a gate touches them.
    - Applies H and X as slice operations and CX as a masked flip.
    - Caches the oracle permutation.
    - Groups shots by misfire pattern.
    - About 0.1 s for a 20-qubit Simon shot.

### 1.3 Solver (`solver.py`, the submission)
- Entry point: `solve(n, m, budget, families, run) -> (family, secret)`. It uses only qiskit, numpy and scipy and never imports `sim/`.
- **Core method:** exact Bayesian inference over every (family, secret) hypothesis, with the noise model inside the likelihoods.
  - Each step runs the circuit with the highest expected information gain per query.
  - The solver stops once the top answer has posterior ≥ 1 − δ, with **δ = 0.003**.
- **Noise robustness:** each hypothesis is paired with both nominal (4%/2%) and doubled (8%/4%) noise, and the posterior averages over both. No retuning is needed for the stress setting.
- **Readout repetition (innovation):** CNOT copies of measured qubits go onto spare qubits (up to the 20-qubit cap).
  - Turns readout flips into detected erasures.
  - Costs no queries.
- **m = 8 (simon / simon2 / perm):**
  - One circuit, H·U·H.
  - A closed-form Walsh-domain likelihood scores all 11,051 hypotheses (perm, 255 simon, 10,795 simon2 subspaces) exactly after every shot.
- **m = 1 (constant / linear / grover / balanced / randfun):** the solver chooses from this menu:
  - Deutsch–Jozsa / Bernstein–Vazirani (1 query)
  - **"Grover echo"** with j = 2 or 4 (even j returns a balanced function exactly to z = 0, but not a randfun)
  - Grover search with j = 6–12
  - classical queries, with the answer qubit's start value alternated to cancel misfire bias
- **Outcome model:** an exact 2×2 density-matrix model of Grover iterations under misfires.

### 1.4 Baselines and benchmark
- **`baselines.py`**:
  - classical-only (no superposition; birthday-collision search for m = 8)
  - single algorithm (DJ only for m = 1, Simon for m = 8)
  - non-adaptive (fixed 60-query schedule)
  - random guess
- **`bench.py`** runs every experiment on the same oracle seeds (a paired comparison). It reports accuracy, worst-family accuracy, query saving, mean queries and runtime, plus confusion matrices and a failure list. It writes `logs/bench_<tag>.json` (every task) and `logs/summary_<tag>.md`.
  - Its experiments: ours (nominal and stress), budget caps 20/30/40/50, an ablation without readout copies, and the 4 baselines.

### 1.5 Tests (`tests/test_sim.py`, 25 passing)
- Section 4 check values for all 6 examples.
- Classical queries read f(x) correctly, and the m = 8 bit order is right.
- Noise-free Bernstein–Vazirani returns a, and Simon samples are orthogonal to s.
- The 2-level Grover model matches the simulator's state vector for j = 1, 4 and 10.
- The budget limit is enforced.
- The solver is exactly right on all 6 reference examples without noise.
- Noisy smoke test: at least 3 of 5 correct for each of the 8 families.

### 1.6 Tuning and results so far

**Stopping-threshold sweep** (40 oracles per family; files `logs/summary_delta_*.md`):

| δ | nominal acc | stress acc | nominal saving | stress saving |
|---|---|---|---|---|
| 0.01 | 0.991 | 0.981 | 0.642 | 0.528 |
| **0.003** (chosen) | 0.997 | 0.988 | 0.602 | 0.473 |
| 0.001 | 0.997 | 0.988 | 0.560 | 0.422 |

δ = 0.001 had exactly the same failures as 0.003 and only cost more queries.

**Final run** (50 oracles per family; finished rows so far):

| experiment | accuracy | worst family | query saving | mean queries |
|---|---|---|---|---|
| ours, nominal noise | **0.998** | 0.980 | 0.592 | 24.4 |
| ours, stress noise | **0.990** | 0.960 | 0.464 | 32.2 |
| budget cap 20 | 0.917 | 0.680 | 0.726 | 16.7 |
| budget cap 30 | 0.983 | 0.920 | 0.651 | 21.0 |
| budget cap 40 | 0.993 | 0.960 | 0.621 | 22.8 |
| budget cap 50 | 0.998 | 0.980 | 0.604 | 23.7 |

Still running: the readout-copy ablation, non-adaptive, single-algorithm, classical-only and random-guess baselines.

**Findings for the report:**
- With misfires, **j = 8–10 Grover iterations** give the best success per query (0.078), better than the textbook j = 12 (0.066).
- The echo test (j = 4) separates balanced from randfun far better than one DJ shot. P(z = 0) is 0.86 for balanced against 0.09–0.35 for randfun, compared with 0.04 vs 0.12–0.29 for a single DJ shot.
- Constant-0 is the most expensive family by necessity: ruling out a hidden marked input takes at least about √N queries.
- **Remaining failure types:**
  - grover reported as constant-0 when the search keeps failing (mostly under stress noise)
  - rare low-weight randfun runs that look exactly like constant-1 or grover
  - one balanced oracle that looks like randfun

  All of these are rare events the model itself predicts, not bugs.
- The solver's own compute is under 2 s per oracle. Total time is at most about 17 s per oracle with the local simulator (limit 120 s).

### 1.7 Documents
- `README.md`: layout, setup, run commands and a one-paragraph strategy.
- `REPORT.md`: draft technical report. Sections 1, 2 and 6 are written; sections 3–5 have `TBD_` placeholders.
- `AI_USE.md`: draft AI-use disclosure, which the team must review and sign.

---

## 2. Left to do

### Must do (deliverables)
- [ ] **Let the final benchmark finish** (`logs/summary_final.md`, `logs/bench_final.json`).
- [ ] **Fill in REPORT.md sections 3–5** from `logs/summary_final.md`: budget-split table, results and baselines table, confusion matrix, accuracy vs budget, failure analysis, and where classical is enough.
- [ ] **Keep REPORT.md to at most 3 pages** once rendered. Export it to PDF if the organisers want a PDF.
- [ ] **Team review of AI_USE.md:** add names, what you verified by hand, and any changes you made.
- [ ] **Add team names** to REPORT.md.
- [ ] **Commit and push to GitHub** (`origin` = github.com/SantoshChez03/quantum-oracle-forensics), then **tag the submission commit**. The rules require a tagged repository. I will only commit or push when you ask.
- [ ] **Check the repo is public** before the deadline.

### Should do (lower risk / higher score)
- [ ] **Clean install check:** in a fresh environment, `pip install -r requirements.txt` then run the tests. Pin exact versions if the organisers want them.
- [ ] **Check against the official harness behaviour once it's known.** If the judges' `run()` transpiles circuits, confirm the multi-controlled X in the diffusion and the 20-qubit circuits are accepted. If each `run()` call is slow, batch the Simon shots, because the solver currently makes up to 60 one-shot calls.
- [ ] **Clean up the `logs/` folder:** keep `summary_final.*` and the δ-sweep summaries, and decide whether the large `bench_*.json` files should go in the repo.

### Could do (optional improvements)
- [ ] **Cheaper constant-0:** lower the search cost, for example by allowing a slightly larger δ only for constant-0 and grover. Constant-0 is now the main drag on query saving (mean of about 30–35 queries).
- [ ] **Balanced vs randfun:** test whether adding j = 6 echo to the menu reduces the remaining confusions.
- [ ] **Extension write-up:** give readout repetition its own short "precise definition + evidence" paragraph using the no-copies ablation numbers (section 11 of the statement asks for this).
- [ ] **Sequential-test guarantee:** state formally that the stopping rule gives error ≤ δ when the model is right, and show calibration (posterior vs observed error) from the logs.
- [ ] **Optional 3-minute video** (not scored).
