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

TBD_BUDGET_TABLE

Constant-0 is the most expensive family by necessity. Proving that no input is marked takes
Ω(√N) queries even for a quantum algorithm, so it costs more than grover itself.

## 4. Results

TBD_RESULTS

## 5. Where it fails, and where classical is enough

TBD_FAILURES

## 6. Reproducibility

`python -m pytest -q` runs the simulator checks (section-4 values, bit order, BV/Simon
sanity checks, model vs simulator). `python bench.py --per-family 50 --tag final` regenerates
`logs/summary_final.md` and `logs/bench_final.json`, which hold every task's answer and query
count. The solver's own compute is under 2 s per oracle. It makes at most 60 `run()` calls,
each with one shot.
