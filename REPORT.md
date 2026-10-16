# Quantum Oracle Forensics: technical report

*Team: (names) · Repository: quantum-oracle-forensics · All numbers are from `logs/summary_final.md`
(50 random oracles per family per experiment, same oracle seeds in every experiment).*

## 1. Approach

The solver identifies the family and recovers the secret using exact Bayesian inference with
the noise model inside the likelihoods. It chooses each next circuit adaptively and stops
sequentially, as soon as one answer is probable enough.

- **Hypotheses.** Every (family, secret) allowed by `m` is a hypothesis:
  - m = 1: 2 constant, 510 linear (a, b), 256 grover t, balanced, and randfun with a
    Binomial(256, 0.3) prior over its weight w.
  - m = 8: perm, 255 simon s, and all 10 795 two-dimensional subspaces for simon2.
- **Noise level.** It is not assumed. Each hypothesis is paired with nominal (4 % misfire,
  2 % flip) and doubled (8 %, 4 %) noise, and the posterior marginalises over both. This is
  what keeps the solver accurate in the stress setting without retuning.
- **Readout repetition (extension).** Right before measurement, spare qubits get CNOT copies
  of the measured qubits:
  - Each Grover/DJ circuit uses 9 + 8 = 17 qubits.
  - Each classical query uses 9 + 2 qubits.
  - Simon uses 16 + 4 qubits (the copied half alternates between shots).

  Readout flips are independent per measured bit, so agreeing copies are almost surely right
  and a disagreement becomes a known erasure. In channel-capacity terms, a 2 % flip becomes
  equivalent to 0.5 % (two copies) or 0.07 % (three). This costs no queries.
- **Stopping.** The solver answers when the top answer has posterior ≥ 1 − δ, with δ = 0.003,
  or when the budget is spent. δ was chosen by a sweep; see §4.

## 2. Circuits and exact likelihoods

**m = 8: one circuit, H·U·H.** The measured z is uniform on the annihilator V⊥ of the hidden
subspace V. A misfire gives z = 0, which is consistent with every hypothesis.

For one shot with per-bit reading likelihoods g_k(0) and g_k(1):

P(readings | V) ∝ (1 − p_m)/256 · Σ_{v ∈ V} Π_{k ∈ v} c_k + p_m · Π_k g_k(0)/(g_k(0) + g_k(1)),

where c_k = (g_k(0) − g_k(1)) / (g_k(0) + g_k(1)). This is the Walsh transform of the readout
kernel. Because of it, all 11 051 hypotheses are scored exactly after every shot in about 1 ms.

**m = 1: a menu of circuits.**

| circuit | queries | what it separates |
|---|---|---|
| G(1, H): Deutsch–Jozsa / Bernstein–Vazirani | 1 | constant & grover → z = 0; linear → z = a (every shot); balanced → z ≠ 0; randfun → z = 0 w.p. (1 − 2q)² |
| G(j, H), j = 2, 4: "Grover echo" | j | balanced (q = ½) returns **exactly** to z = 0 for even j; randfun does not |
| G(j, Z), j = 6, 8, 10, 12: Grover search | j | finds the marked t |
| C(x, y₀): classical query, answer qubit starts at y₀ | 1 | b, c, verification of a grover candidate |

G(j, ·) means: H on the inputs, answer qubit in |−⟩, then j repetitions of (oracle, diffusion).

For a function with a fraction q of marked inputs, the oracle and the diffusion are both
reflections in the plane spanned by the marked and unmarked superpositions. The solver
propagates a 2 × 2 density matrix ρ ← D[(1 − p_m) OρO + p_m ρ]D, which is exact under misfires.
That gives P(z = 0) = cos²(2jθ) with sin²θ = q in the noise-free case, and the probability of
measuring the marked input for Grover search. These formulas are exact for constant, linear
and grover, and exact in P(z = 0) for balanced and randfun, whose other outcomes are modelled
as uniform. A unit test checks them against the simulator's state vector.

Model values with nominal noise:

- **Echo with j = 4:** P(z = 0) is 0.86 for balanced and 0.09–0.35 for randfun with
  q ∈ [0.24, 0.36]. Compare 0.04 vs 0.12–0.29 for a single DJ shot.
- **Grover with misfires:** P(t) after j iterations is 0.45, 0.63, 0.75 and 0.79 for
  j = 6, 8, 10, 12. Per query that is best at j = 8–10 (0.078), not at the textbook j = 12
  (0.066), because a misfire part-way through breaks the rotation.
- **Classical queries:** misfires leave the answer qubit at y₀. Alternating y₀ = 0, 1 makes
  that error symmetric. The likelihood models it either way.

**Adaptive choice.** At each step the solver picks the circuit that maximises expected
information gain about the answer, divided by its query cost. For scoring candidate circuits
only, readout is approximated by a binary-symmetric channel of equal capacity; posterior
updates use the exact per-bit likelihoods. The typical paths that emerge are:

- **linear:** 2–3 DJ shots fix a, then 1–2 classical queries fix b.
- **constant-1:** DJ shots, then classical queries.
- **constant-0 / grover:** search shots with j = 8–10, each followed by a classical
  verification of the most likely t.
- **balanced / randfun:** a mix of echo and DJ shots.

## 3. Budget split (mean queries per family, nominal noise)

| family | mean queries | typical path chosen by the information-gain rule |
|---|---|---|
| linear | 5.2 | 2–3 DJ shots fix a; 1–2 classical reads fix b |
| constant | 33.9 (c = 1: 5.5; c = 0: 60) | c = 1: DJ, then classical reads. c = 0: search until the budget ends |
| grover | 23.5 | searches with j = 8–10, each followed by a classical check of the best t |
| balanced / randfun | 25.0 / 23.8 | echo (j = 2, 4) and DJ shots |
| simon / simon2 / perm | 29.1 / 22.9 / 32.7 | Simon sampling, one shot at a time, 4 of 8 bits duplicated |

Constant-0 always spends the full budget. Deciding "no marked input" is the OR problem:
Θ(√N) queries for a quantum algorithm and Θ(N) for a randomized classical one (N&C §6.7).
Each failed search shot (j = 10) multiplies the grover posterior by only about 0.36, so
1 − δ is not reached within 60 queries. Stopping earlier would save at most about 1.5% of
query saving overall, but it would cost grover accuracy (0.92 at a 30-query cap). We keep
the full search.

## 4. Results

Same 400 oracles (50 per family) in every row. Query saving is over correct tasks.

| experiment | accuracy | worst family | query saving | mean queries |
|---|---|---|---|---|
| **ours** (nominal 4 % / 2 %) | **0.998** | 0.980 | **0.591** | 24.5 |
| **ours, stress** (8 % / 4 %) | **0.990** | 0.960 | 0.463 | 32.2 |
| ours, budget cap 20 / 30 / 40 / 50 | 0.917 / 0.983 / 0.993 / 0.998 | 0.68 / 0.92 / 0.96 / 0.98 | 0.73 / 0.65 / 0.62 / 0.60 | 16.7 / 21.1 / 22.8 / 23.8 |
| no readout copies (ablation) | 1.000 | 1.000 | 0.486 | 30.9 |
| no readout copies, stress | 0.960 | 0.860 | 0.400 | 36.9 |
| non-adaptive (fixed 60-query schedule) | 0.970 | 0.900 | 0 | 60 |
| single algorithm (DJ / Simon only) | 0.752 | 0.000 | 0.326 | 45.3 |
| classical only (no superposition) | 0.680 | 0.160 | 0.232 | 50.5 |
| random guess | 0.113 | 0.000 | n/a | 0 |
| independent second solver (`reference/`) | 1.000 / 0.983 stress | 1.00 / 0.90 | 0.518 / 0.418 | 28.9 / 35.3 |

- **Adaptivity** is worth 2.8 points of accuracy and all of the query saving: the
  non-adaptive schedule spends 60 queries and still misses 12 tasks.
- **Readout copies** (extension, §1) leave nominal accuracy unchanged but save 6.4
  queries per task (saving 0.486 → 0.591). Under stress they raise accuracy from 0.960 to
  0.990, and worst-family accuracy from 0.86 to 0.96 (grover: 0.86 → 0.96).
- **Accuracy vs budget.** 30 queries already give 0.983, and 50 match 60. grover is the
  family that needs budget (0.68 at a 20-query cap).
- **Confusion matrix.** Nominal: one error in 400 (randfun → constant). Stress: four errors
  (balanced → randfun, randfun → constant, 2 × grover → constant-0). Full matrices are in
  `logs/summary_final.md`.
- **Independent check.** A second solver, written separately with a different m = 1 design,
  reaches the same accuracy band on the same oracles but uses about 4.4 more queries per task.

## 5. Where it fails, and where classical is enough

**Failures.**

- **grover → constant-0** (stress, 2 / 50). Under 8 % misfires a j = 10 search succeeds
  less often, and occasionally every search in the budget fails. With 60 queries, a longer
  search is not affordable.
- **randfun → constant-1** (1 / 50 in both settings). The trace shows three near-zero DJ
  outcomes and two reads of f = 1 at different inputs: about 1000 : 1 evidence for
  constant-1 on that data. The posterior was right to be confident; this is the rare event
  δ = 0.003 allows (about 1 error in 400 tasks is expected).
- **balanced → randfun** (stress, 1 / 50): a run of echo shots far from z = 0.

None of the failures is a bug; each is a low-probability outcome under the model itself.
During the review we fixed one modelling error. Repeated classical reads of the same x
had been treated as independent samples for balanced and randfun, but f(x) is fixed, so
they are only independent given f(x). This barely changes our solver, because it rarely
re-reads an x outside grover checks. It lifted the classical-only baseline on randfun from
0.00 to 0.90.

**Where classical is enough.** The classical-only baseline solves constant (1.00, 37
queries), linear (1.00, 21), balanced (0.98, 57), randfun (0.90, 53) and simon2 (0.98).
With 60 queries, 4-to-1 output collisions are frequent, so a birthday search finds H.
Quantum circuits make these families 2–4× cheaper (linear: 5 vs 21 queries;
balanced/randfun: about 24 vs 55), but they are not needed for correctness.

**Where quantum is necessary.**

- **grover:** classical 0.20 vs 1.00. Finding one marked input among 256 takes about
  128 classical queries on average, against about 23 with Grover search, and no classical
  strategy fits in 60.
- **simon and perm:** classical 0.16 and 0.22 vs 1.00. 2-to-1 collisions are rare within
  60 queries, while Simon sampling identifies s or rules out every subspace in about
  30 queries.
- The single-algorithm baseline shows the same split. DJ alone cannot see b or c and
  cannot find t (constant 0.52, linear 0.56, grover 0.00), while Simon alone is already
  enough for m = 8.

## 6. Reproducibility

`python -m pytest -q` runs the simulator checks (section-4 values, bit order, BV/Simon
sanity checks, model vs simulator). `python bench.py --per-family 50 --tag final` regenerates
`logs/summary_final.md` and `logs/bench_final.json`, which hold every task's answer and query
count. The solver's own compute is under 2 s per oracle. It makes at most 60 `run()` calls,
each with one shot.
