# Project manual: Quantum Oracle Forensics

A complete record of how this project was built: how we read the problem, the
directions we tried, the problems we hit and how we solved them, how the final
method works, how it was checked, where it is weak, and how to work on the code.

*Audience: the team, and anyone reviewing the repository. The 3-page
`REPORT.md` is the scored summary; this manual is the long version behind it.*

---

## Contents

1. [The problem in one page](#1-the-problem-in-one-page)
2. [How we assessed the problem statement](#2-how-we-assessed-the-problem-statement)
3. [Timeline: how the work progressed](#3-timeline-how-the-work-progressed)
4. [Final method (the submitted solver)](#4-final-method-the-submitted-solver)
5. [The two codebases and how they compare](#5-the-two-codebases-and-how-they-compare)
6. [Verification: how we know the numbers are right](#6-verification-how-we-know-the-numbers-are-right)
7. [Results](#7-results)
8. [Problems we faced and how we handled them](#8-problems-we-faced-and-how-we-handled-them)
9. [Limitations and risks](#9-limitations-and-risks)
10. [Repository map and how to run things](#10-repository-map-and-how-to-run-things)
11. [Working on the GitHub repository](#11-working-on-the-github-repository)
12. [Checklist before the deadline](#12-checklist-before-the-deadline)
13. [References](#13-references)

---

## 1. The problem in one page

**Input.** A sealed oracle U|x⟩|y⟩ = |x⟩|y ⊕ f(x)⟩ on n = 8 input bits, with m = 1 or
m = 8 output bits. The solver is told n, m, the budget (60) and the family list, nothing else.

**Task.** Name the family of f out of eight, and report its secret exactly.

| Family | m | f | Secret |
|---|---|---|---|
| constant | 1 | f(x) = c | c |
| balanced | 1 | exactly 128 ones | none |
| linear | 1 | a·x ⊕ b, a ≠ 0 | [a, b] |
| grover | 1 | 1 only at t | t |
| randfun | 1 | each f(x) = 1 with prob. 0.3 | none |
| simon | 8 | f(x) = f(x ⊕ s), otherwise distinct | s |
| simon2 | 8 | constant on cosets of a 2-dim subspace H | the 3 nonzero elements of H, ascending |
| perm | 8 | random permutation | none |

**Cost model.** One query = one oracle gate in one shot. A circuit with k oracle gates run
for s shots costs k·s. The budget is 60 per oracle; going over ends the task with no answer.

**Noise.** Each oracle application misfires with probability 4% (acts as the identity);
each measured bit flips with probability 2%. The stress test doubles both (8%, 4%).

**Scoring (100 marks).** Accuracy 35, query saving on correct tasks 15, robustness 15
(worst-family accuracy 8, stress accuracy 7), report 20, code 10, extensions 5.
A secret with one wrong bit scores zero for that task.

---

## 2. How we assessed the problem statement

We read the statement looking for structure that could be exploited before writing code.

**2.1 m is free information.** Since the solver is told m, the eight families split into a
5-way problem (m = 1) and a 3-way problem (m = 8) at zero cost.

**2.2 Each family maps to a known algorithm, but none covers all of them.**

| Algorithm | What it reveals | Families it handles |
|---|---|---|
| Deutsch–Jozsa / Bernstein–Vazirani | Walsh spectrum of f: P(z) = [Σₓ(−1)^{f(x)+x·z}/2ⁿ]² | constant vs linear vs balanced vs randfun; gives a directly |
| Grover search | the marked input | grover (finds t) |
| Simon sampling | vectors z orthogonal to the hidden subspace | simon, simon2, perm |
| Classical queries | f at a chosen x | b for linear, c for constant, verification |

The statement warns that "one textbook algorithm for everything" scores poorly, so the
real task is **experiment design**: which circuit to run next, given what has been seen.

**2.3 The hard pairs, identified on day one.**

- **constant-0 vs grover.** DJ cannot tell them apart (P(z = 0) is 1 vs 0.984). Only
  finding t, or failing to find it with enough effort, separates them. This is the OR
  problem, which needs Θ(√N) quantum queries and Θ(N) classical ones (N&C §6.7).
- **balanced vs randfun.** Both have spread-out spectra. The only clean DJ signal is
  P(z = 0): exactly 0 for balanced, (1 − 2w)² ≈ 0.16 for randfun, where w is its fraction of ones.
- **linear b and constant c.** DJ cannot see them (global phase), so classical reads are required.
- **simon vs simon2 vs perm.** All three use the same circuit. They differ in the dimension
  of the hidden subspace: 1, 2 or 0.

**2.4 Noise turns every decision into a statistical test.** About 15% of 8-bit readouts
contain at least one flipped bit, and a 10-call Grover circuit runs without misfires only
66% of the time. No single shot can be trusted, so every answer had to come from a
likelihood or posterior, not a rule like "measure once and read the answer".

**2.5 The scoring rewards caution first and thrift second.** Query saving only counts on
correct tasks, and a worst-family term punishes sacrificing any one family. So we aimed for
accuracy first, then spent as few queries as possible.

---

## 3. Timeline: how the work progressed

The project was built in two parallel streams that were later compared:

- **Stream A, chat design track** (Claude chat sessions with Faaz): understanding, design
  experiments, quick simulations, a reference solver (`reference/claude_solver.py`).
- **Stream B, the repository** (built in Claude Code with the team): the submitted
  `solver.py`, simulator, baselines, benchmark, tests and report.

### Phase 1: Understanding the statement (Stream A)

- Clarified the basic vocabulary: an *oracle* is a black-box gate; a *shot* is one run of a
  circuit ending in one measurement; a *query* is one oracle gate in one shot.
- Mapped families to algorithms (§2.2). An early simplification, "it's basically
  Deutsch–Jozsa", was corrected: DJ is the right *first* experiment for m = 1, but the
  solver also needs Grover, Simon and classical reads.

### Phase 2: First m = 1 plan (Stream A)

DJ triage into three buckets: *mostly zeros* (constant or grover), *one dominant nonzero
string* (linear, string = a) and *spread* (balanced or randfun), followed by a targeted
follow-up for each bucket. Rough budget estimates showed every family could fit under 60.

### Phase 3: Hardening the constant/grover classifier (Stream A)

A first rule-based version (f(0) twice, then Grover with 12 iterations and one
classical check) was simulated at 94–96%. Three leaks were found and fixed:

| Leak | Fix | Effect |
|---|---|---|
| constant-1 decided from 2–3 reads of f(0) | probe 6 distinct points f(0..5); ≥ 3 ones means constant-1 | 94% → 99.7–100% |
| constant-0 falsely called grover by a single flipped verification bit | **flag oracle call**: one extra oracle application writes f(x) for the measured x | 94% → 99.6% |
| grover shots wasted by a flipped bit in x | **duplicate readout**: CNOT-copy x and the flag onto spare qubits (free) | grover 96.4% → 98% |

We also found that **10 Grover iterations beat the textbook 12** under misfires. A shot
succeeds about 75% of the time at k = 10 and 79% at k = 12, so 12 is not worth 20% more queries.

### Phase 4: Checking an outside proposal (Stream A)

A plan from another AI assistant (Gemini) was simulated on the same model:

| | Gemini plan | Our plan |
|---|---|---|
| grover | 87–88% | 97.9% |
| constant-0 | 92–99.8% (rule ambiguous) | 99.5% |
| constant-1 | **100%** | 99.6% |

Its fixed 3 Grover shots and bitwise majority vote failed under noise. Its 6-probe
constant-1 check was better than ours and **was adopted**. Lesson: simulate every claim
before adopting it, including our own.

### Phase 5: Literature check (Stream A)

We read the relevant parts of Nielsen & Chuang (N&C), the IBM Quantum Learning lesson on
Deutsch–Jozsa, and a 2026 critique of Grover-based search. What we took from each:

- **N&C §1.4.4 and the IBM lesson:** the outcome amplitude formula used for every DJ
  likelihood. Both note that random classical sampling already solves the DJ promise
  problem with high probability, which supports reporting honestly where classical is enough.
- **N&C §6.1 (pp. 248–254):** Grover's iteration is a rotation by θ with
  sin(θ/2) = √(M/N). The optimum is R = CI(arccos√(M/N)/θ) = 12 for N = 256, M = 1.
  We deliberately use fewer iterations because of noise.
- **N&C §6.3:** quantum counting decides whether M = 0, but it needs at least 63
  controlled-Grover queries before noise and returns M, not t. **Rejected.**
- **N&C §6.7 (pp. 271–274):** OR has quantum query complexity Θ(√N) and randomized
  classical complexity Θ(N). This justifies why constant-0 costs the most and why grover is
  the one family where quantum clearly wins at n = 8.
- **N&C Fig. 5.5 (p. 241):** simon, simon2 and perm are one hidden-subgroup problem
  over (Z₂⁸, ⊕) with |K| = 2, 4, 1. One circuit and one inference handle all three.
- **N&C §8.3.3 (p. 376):** the misfire is a mixed-unitary channel (1−p)UρU† + pρ, so
  sampling one misfire pattern per shot is a correct simulation of it.
- **Liu (2026):** argues that oracle construction costs can erase Grover's advantage. That
  does not apply here: the oracle is given and charged per call, which is exactly the
  query model where the √N advantage holds.

### Phase 6: Stream A full reference solver

- **m = 8:** an exact Bayesian posterior over all 1 + 255 + 10 795 hypotheses. Fourier-only
  sampling used 46 / 32 / 58 queries (simon / simon2 / perm). Adding duplicated readout on
  4 of the 8 bits, plus collision checks f(x) =? f(x ⊕ d), brought this to 36 / 29 / 40.
  - *Bug found:* the first collision-check rule kept re-checking s forever, because a match
    on s cannot rule out the subspaces that contain s. Fixed by checking each element at
    most until it matches and sending everything else to Fourier sampling.
- **balanced vs randfun:** plain DJ needed 54 queries with randfun at 93%. Amplitude-amplified
  DJ (A·R·A·R·A, 3 calls, P(z = 0) = sin²(3θ) with sin θ = |1 − 2w|) gave 31 queries at 100%.
  The misfire patterns were derived by hand and checked against brute-force linear algebra.
  - *Bug found:* amplified-shot evidence was only added to the balanced/randfun
    likelihoods, so the full posterior drifted toward "constant". Fixed by comparing only
    those two families once in that stage.
- Result: normal 99.8% (worst 98.3%), stress 98.3% (worst 90.0%), query saving 0.52 / 0.39.

### Phase 7: Stream B, the repository

Built independently with the same principles, but more systematically:

- one Bayesian engine per m, with every hypothesis atom (2 constant, 510 linear (a, b),
  256 grover t, balanced, 257 randfun weights) and both noise levels;
- **adaptive design by expected information gain per query** over a menu of circuits,
  instead of hand-written stages;
- **"Grover echo"**: an even number of Grover iterations returns a balanced function
  exactly to z = 0 but not a randfun. It uses 2–4 queries per shot and is stronger than Stream A's amplified DJ;
- an exact 2×2 density-matrix model of Grover iterations under misfires;
- the closed-form Walsh likelihood for m = 8;
- readout repetition on spare qubits;
- a δ sweep (0.01 / 0.003 / 0.001), with δ = 0.003 chosen;
- section-9 baselines, a paired benchmark, 25 tests, a draft report and an AI-use disclosure.

### Phase 8: Code review and comparison (this step)

- The two independently written simulators were cross-checked against each other and
  against Qiskit's own `Statevector`. They agree to 10⁻¹³ (§6).
- Both solvers were benchmarked on **the same 400 oracles** (§5, §7).
- The benchmark exposed one modelling error. Repeated classical reads of the same x were
  treated as independent samples for balanced and randfun, which drove the classical-only
  baseline to 0% on randfun. It was fixed, and only the affected m = 1 records were rerun.
- Rule checks were added as tests, the final benchmark was completed, and the report's
  results sections were filled in (§5.4).

---

## 4. Final method (the submitted solver)

`solver.py` is the submission. It imports only qiskit, numpy and scipy.

### 4.1 Principles

1. **Exact likelihoods.** Every (family, secret) hypothesis is scored with the section-3
   noise model built into the likelihood.
2. **Noise level is not assumed.** Each hypothesis is paired with nominal (4%, 2%) and
   doubled (8%, 4%) noise, and the posterior averages over both. The same code handles
   the stress test without retuning.
3. **Adaptive experiment design.** Each step runs the circuit with the highest expected
   information gain about the answer, divided by its query cost.
4. **Sequential stopping.** The solver answers when the top answer has posterior
   ≥ 1 − δ (δ = 0.003), or when the budget runs out.
5. **Readout repetition.** Spare qubits receive CNOT copies of measured qubits. Agreeing
   copies are almost surely right, and disagreements become known erasures. This costs no queries.

### 4.2 m = 1 circuit menu

| Circuit | Queries | Purpose |
|---|---|---|
| G(1, H): DJ / BV | 1 | constant & grover → z = 0; linear → z = a; balanced → z ≠ 0; randfun → z = 0 w.p. (1 − 2w)² |
| G(2 or 4, H): Grover echo | 2 or 4 | balanced returns exactly to z = 0 for even j; randfun does not |
| G(6–12, Z): Grover search | j | finds t |
| C(x, y₀): classical query | 1 | b, c, verifying a grover candidate; y₀ alternates so misfires don't bias the bit |

Typical paths that emerge from the information-gain rule:

- **linear:** 2–3 DJ shots fix a, then 1–2 classical reads fix b (~5 queries).
- **constant-1:** DJ, then classical reads.
- **grover / constant-0:** Grover search shots with j = 8–10, each followed by a
  classical check of the most likely t.
- **balanced / randfun:** a mix of echo and DJ shots.

### 4.3 m = 8

One circuit, H·U·H with 4 of the 8 input bits duplicated (20 qubits; the duplicated half
rotates between shots). For per-bit reading likelihoods g_k(0), g_k(1), the likelihood of a
shot under hidden subspace V is

P(readings | V) ∝ (1 − p_m)/256 · Σ_{v∈V} Π_{k∈v} c_k + p_m · Π_k g_k(0)/(g_k(0)+g_k(1)),
with c_k = (g_k(0) − g_k(1))/(g_k(0) + g_k(1)).

This scores all 11 051 hypotheses exactly after every shot in about 1 ms.

### 4.4 Why these choices

| Choice | Alternative considered | Why |
|---|---|---|
| Bayesian posterior | hand thresholds | one principled stopping rule for every family; error ≈ δ when the model is right |
| marginalise noise level | assume nominal | the stress test doubles noise without telling the solver |
| j = 8–10 search | textbook j = 12 | best success per query under misfires (0.078 vs 0.066) |
| Grover echo | plain DJ / amplified DJ | balanced returns exactly to z = 0, making it the strongest separation per query |
| one Simon circuit for m = 8 | separate tests per family | the hidden-subgroup view makes the three families one inference |
| readout copies | none | free; turns silent errors into erasures |
| δ = 0.003 | 0.01, 0.001 | 0.001 had the same failures and cost more queries; 0.01 lost accuracy |

---

## 5. The two codebases and how they compare

### 5.1 What each one is

| | Repository (`solver.py`) | Reference (`reference/claude_solver.py`) |
|---|---|---|
| Built in | Claude Code, with the team | Claude chat, with Faaz |
| Purpose | the submission | an independent second implementation for checking and comparison |
| m = 1 control | information gain per query over a circuit menu | hand-designed stages (DJ triage → branches) |
| balanced vs randfun | Grover echo (j = 2, 4) | amplitude-amplified DJ (3 calls) |
| grover search | j = 6–12 search + classical verification | k = 10 search + flag oracle call + duplicated x |
| m = 8 | Fourier sampling only, one shot at a time | Fourier sampling in batches + collision checks |
| noise handling | marginalised over two levels | marginalised over two levels |
| readout copies | yes, in every circuit | yes, in every circuit |
| stopping | δ = 0.003 | ε = 0.001 |
| simulator | `sim/runner.py` | `oracle_sim.py` (not in this repo) |
| tests | 25 + 9 added | quick scripts |

The two streams reached the same core ideas independently: Bayesian decisions, noise
marginalisation, readout copies and the hidden-subgroup view of m = 8. That convergence is
itself some evidence that the approach is sound.

### 5.2 Head-to-head results

Both solvers on the **same 400 oracles** (50 per family), from `logs/summary_final.md`:

| | repository, nominal | reference, nominal | repository, stress | reference, stress |
|---|---|---|---|---|
| accuracy | 0.998 | 1.000 | **0.990** | 0.983 |
| worst-family accuracy | 0.980 | 1.000 | **0.960** | 0.900 |
| query saving | **0.591** | 0.518 | **0.463** | 0.418 |
| mean queries | **24.5** | 28.9 | **32.2** | 35.3 |

Mean queries per family, nominal noise (repository / reference):

| constant | balanced | linear | grover | randfun | simon | simon2 | perm |
|---|---|---|---|---|---|---|---|
| 33.9 / 35.0 | 25.0 / 32.8 | 5.2 / 6.2 | 23.5 / 28.0 | 23.8 / 24.8 | 29.1 / 36.2 | 22.9 / 29.6 | 32.7 / 38.6 |

At nominal noise the two are equally accurate: one error in 400 versus none is well within
chance. The repository solver uses fewer queries in every family and holds up better under
stress (grover 0.96 vs 0.90).

### 5.3 What each does better

- **The repository solver is the stronger submission.** It matches or beats the reference
  on accuracy and clearly beats it on query saving, because:
  - the information-gain rule picks the next circuit better than fixed stages;
  - the Grover echo needs fewer queries than amplified DJ;
  - shot-by-shot stopping for m = 8 wastes less than batches of 4;
  - search plus classical verification is cheaper than search plus a flag call.
- **What the reference contributed:** an independent simulator that agrees with the team's
  to 10⁻¹³, a second solver for paired comparison, and the collision-check and flag-call
  ideas. Neither of those ideas beat the repository's approach, so neither was merged.

### 5.4 Edits made to the repository during the review

| File | Change | Why |
|---|---|---|
| `solver.py` | repeated classical reads of the same x are combined as log[π·L₁ + (1−π)·L₀] instead of being treated as independent samples | f(x) is fixed, so for balanced / randfun the reads are only independent *given* f(x). The old model made the classical-only baseline score 0.00 on randfun (now 0.90). Our solver is essentially unaffected (it rarely re-reads one x) |
| `solver.py` | `solve()` seeds its own random generator (`SEED = 2026`) | solver runs are now reproducible whenever `run()` is seeded; logs can be regenerated exactly |
| `sim/runner.py` | raises an error on any gate after a measurement | section 3 requires measurements at the end; the simulator now enforces it |
| `tests/test_compliance.py` (new, 9 tests) | simulator vs Qiskit `Statevector`; measurements at end and ≤ 20 qubits for every solver circuit; solver imports only allowed modules and never `sim/`; `solve()` reproducible | turns the rules of sections 3 and 6 into automatic checks, and gives the simulator an independent reference |
| `reference/claude_solver.py` (new) | the Stream A solver, self-contained | paired comparison (`python bench.py --reference`) |
| `bench.py` | `--reference` adds the reference solver on the same oracles; `--update --only ... --families ...` reruns part of an existing log in place | head-to-head numbers in §5.2; after the solver fix, only the m = 1 records had to be regenerated |
| `report_tables.py` (new) | prints the report's tables from `logs/bench_final.json` | keeps the report and the logs in sync after reruns |
| `logs/summary_final.md`, `logs/bench_final.json` | the final 50-per-family run | the report's numbers come from these files |
| `REPORT.md` | sections 3–5 filled from the final logs | they were `TBD_` placeholders |
| `STATUS.md`, `README.md`, `AI_USE.md` | updated | reflect the review and the new files |
| `MANUAL.md` (this file) | new | the full methodology record |

The review found one modelling error (repeated reads) and fixed it. No other change was
made to the solver's algorithm, and its accuracy and query numbers are unchanged within
noise (§7).

---

## 6. Verification: how we know the numbers are right

| Check | How | Result |
|---|---|---|
| Section 4 reference values | `tests/test_sim.py::test_section4_check_values` | all match |
| Qiskit bit order | classical reads of f(x) for m = 1 and m = 8 | correct |
| Textbook outcomes | noise-free BV returns a; Simon samples ⟂ s | correct |
| Two-level Grover model | vs simulator state vector, j = 1, 4, 10 | exact (< 10⁻⁹) |
| **Simulator vs Qiskit** | DJ, echo, search and classical circuits; oracle as an explicit unitary in Qiskit `Statevector` | agree to < 10⁻⁹ (`test_compliance.py`) |
| **Two independent simulators** | `sim/runner.py` vs `oracle_sim.py`, every circuit type including 20-qubit Simon, with and without misfires | max difference 5 × 10⁻¹⁴ |
| Amplified-DJ misfire formulas (reference) | brute-force 256×256 matrices | exact |
| Rules of sections 3 and 6 | measurement at end, ≤ 20 qubits, allowed imports only | automatic tests |
| Reproducibility | `ours` in the final run reproduced the earlier STATUS numbers exactly (0.998 / 0.980 / 0.592 / 24.4) | identical |

---

## 7. Results

From `logs/summary_final.md` (50 random oracles per family, the same seeds in every experiment):

| experiment | accuracy | worst family | query saving | mean queries |
|---|---|---|---|---|
| ours (nominal) | 0.998 | 0.980 | 0.591 | 24.5 |
| ours, stress | 0.990 | 0.960 | 0.463 | 32.2 |
| ours, budget 20 | 0.917 | 0.680 | 0.726 | 16.7 |
| ours, budget 30 | 0.983 | 0.920 | 0.650 | 21.1 |
| ours, budget 40 | 0.993 | 0.960 | 0.620 | 22.8 |
| ours, budget 50 | 0.998 | 0.980 | 0.603 | 23.8 |
| no readout copies | 1.000 | 1.000 | 0.486 | 30.9 |
| no readout copies, stress | 0.960 | 0.860 | 0.400 | 36.9 |
| non-adaptive | 0.970 | 0.900 | 0.000 | 60.0 |
| single algorithm | 0.752 | 0.000 | 0.326 | 45.3 |
| classical only | 0.680 | 0.160 | 0.232 | 50.5 |
| random guess | 0.113 | 0.000 | n/a | 0.0 |
| reference solver | 1.000 | 1.000 | 0.518 | 28.9 |
| reference solver, stress | 0.983 | 0.900 | 0.418 | 35.3 |

Per-family accuracy:

| experiment | constant | balanced | linear | grover | randfun | simon | simon2 | perm |
|---|---|---|---|---|---|---|---|---|
| ours | 1.00 | 1.00 | 1.00 | 1.00 | 0.98 | 1.00 | 1.00 | 1.00 |
| ours, stress | 1.00 | 0.98 | 1.00 | 0.96 | 0.98 | 1.00 | 1.00 | 1.00 |
| no readout copies, stress | 0.98 | 1.00 | 1.00 | 0.86 | 1.00 | 0.92 | 0.96 | 0.96 |
| classical only | 1.00 | 0.98 | 1.00 | 0.20 | 0.90 | 0.16 | 0.98 | 0.22 |
| single algorithm | 0.52 | 1.00 | 0.56 | 0.00 | 0.94 | 1.00 | 1.00 | 1.00 |

What the numbers say:

- **Adaptivity:** +2.8 points of accuracy and all of the query saving (non-adaptive uses 60).
- **Readout copies:** at nominal noise, the same accuracy with 6.4 fewer queries per task;
  under stress, accuracy rises from 0.960 to 0.990 and grover from 0.86 to 0.96.
- **Budget:** 30 queries already give 0.983; grover is the family that needs budget.
- **constant-0 always uses all 60 queries** (constant-1 uses 5.5). This is expected: see §9.
- **Classical is enough** for constant, linear, balanced, randfun and simon2, at 2–4× the
  queries. **Quantum is necessary** for grover (0.20 classical) and for simon and perm
  (0.16 and 0.22 classical).
- **Failures:** 1 of 400 at nominal noise (randfun → constant-1, a rare but legitimate
  outcome: the data favoured constant-1 about 1000 : 1). 4 of 400 under stress
  (2 × grover → constant-0, balanced → randfun, randfun → constant-1).

---

## 8. Problems we faced and how we handled them

| # | Problem | How it showed up | What we did |
|---|---|---|---|
| 1 | DJ cannot separate constant-0 from grover | P(z = 0) 1 vs 0.984 | treat it as a search problem; accept the Θ(√N) cost (N&C §6.7) |
| 2 | Grover shots fail under misfires | 12 iterations succeed only ~79% | fewer iterations (8–10), more shots, classical verification |
| 3 | Single readout flips poison answers | wrong t, wrong a, false constant-0 alarms | readout copies on spare qubits (free) |
| 4 | constant-1 vs grover t = 0 | both have f(0) = 1 | probe several points, not just f(0) |
| 5 | balanced vs randfun is weak with DJ | 54 queries, randfun 93% | echo (repo) / amplified DJ (reference): balanced and randfun separate sharply |
| 6 | Noise level unknown under stress | thresholds tuned to 4%/2% would break | marginalise every likelihood over both noise levels |
| 7 | m = 8 query cost | Fourier-only 46–58 queries at ε = 10⁻³ | exact Walsh likelihood, readout copies, shot-by-shot stopping |
| 8 | Collision checks stuck on simon(s) (reference) | simon used ~59 queries | check each element until it matches, then return to Fourier sampling |
| 9 | Posterior drift from partial evidence (reference) | balanced answered as constant | compare only the two live families in that stage |
| 10 | Outside advice of mixed quality | Gemini plan: grover 87% | simulate before adopting; kept only the 6-probe check |
| 11 | Can we trust our own simulator? | everything depends on it | section 4 values, Qiskit `Statevector`, and a second independent simulator |
| 12 | Unseeded solver randomness | runs not exactly repeatable | fixed solver seed |
| 13 | Repeated reads of one x counted as fresh evidence | classical-only baseline: randfun 0.00 | combine all reads of x through log[π·L₁ + (1−π)·L₀] |
| 14 | Long benchmark runs (~1.5 h on 2 cores) | slow iteration | `bench.py --update` reruns only the affected experiments and families |

---

## 9. Limitations and risks

**Modelling assumptions**

- For balanced and randfun, only P(z = 0) is modelled exactly; other outcomes are treated
  as uniform. If a hidden oracle has a strongly structured spectrum, the likelihood is
  slightly wrong. `FLOOR` (a small uniform mixture) limits the damage.
- The noise model is the statement's: independent misfires and independent readout flips.
  Correlated errors (for example a misfire rate that changes over time) are not modelled.
- Noise is marginalised over exactly two levels. A stress level other than "doubled" would
  be handled approximately, not exactly.
- Families are assumed equally likely a priori. The hidden suites are balanced (6 per
  family), so this is correct for Stage 1.
- The stopping guarantee ("error ≈ δ") holds only when the model is right. It is
  well calibrated in our benchmarks, but it is not a proof for unmodelled noise.

**Known weak spots**

- **grover under stress noise:** misfires break more Grover shots, so some runs end as
  "constant 0" after the budget is spent.
- **constant-0 always uses the full 60 queries.** Ruling out a marked input is the OR
  problem. Each failed j = 10 search only multiplies the grover posterior by about 0.36, so
  1 − δ is never reached within 60 queries; the answer is still correct. Stopping earlier
  would gain at most ~1.5% overall query saving and cost grover accuracy.
- **Rare randfun instances** with unusually few ones can look like constant-1 or grover early on.

**Harness unknowns**

- The judges' `run()` may transpile circuits. The diffusion uses a 7-control `mcx`, and the
  largest circuits use 17–20 qubits. Both should be fine in Qiskit 2.x, but we have not run
  on the official harness.
- The solver makes up to 60 one-shot `run()` calls. If each call is slow on the judges'
  side, total time is still well under 120 s unless a call takes more than ~1.5 s.

**What we did not do**

- No hardware run, no error mitigation beyond readout copies, and no larger-n experiments.

---

## 10. Repository map and how to run things

| Path | What |
|---|---|
| `solver.py` | **the submission**: `solve(n, m, budget, families, run)` |
| `sim/oracles.py` | random instances of all 8 families + the section 4 examples |
| `sim/runner.py` | local `run()`: noise model, Qiskit bit order, budget and rule checks |
| `baselines.py` | section 9 baselines |
| `bench.py` | full benchmark → `logs/` (`--reference` adds the reference solver) |
| `tests/` | 34 tests (simulator, model, rules, solver) |
| `report_tables.py` | report tables from a benchmark log |
| `reference/claude_solver.py` | independent second solver, for comparison only |
| `REPORT.md` | 3-page technical report |
| `AI_USE.md` | AI-use disclosure (team must review and sign) |
| `MANUAL.md` | this manual |

```bash
python -m pytest -q                                   # all tests, ~1 min
python bench.py --per-family 10 --only ours,ours_stress     # quick check, ~2 min
python bench.py --per-family 50 --tag final --reference     # full run (long: 1–2 h on 2 cores)
```

---

## 11. Working on the GitHub repository

### 11.1 One-time setup

1. Install **Git** (git-scm.com), **Python 3.10+**, and **VS Code** with the Python extension.
2. Tell Git who you are:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
3. Make sure you can push. Either the repository owner adds you as a collaborator
   (GitHub → repo → Settings → Collaborators), or you fork it and open pull requests.
   For pushing over HTTPS, GitHub asks for a *personal access token* instead of a
   password (GitHub → Settings → Developer settings → Personal access tokens).

### 11.2 Clone and set up

```bash
git clone https://github.com/SantoshChez03/quantum-oracle-forensics.git
cd quantum-oracle-forensics
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
code .                      # opens the folder in VS Code
```

In VS Code: *Ctrl+Shift+P → Python: Select Interpreter* → pick the one in `.venv`.

### 11.3 Day-to-day editing

```bash
git pull                                  # get teammates' latest work first
git checkout -b my-change                 # work on a branch
# ... edit files in VS Code ...
python -m pytest -q                       # make sure nothing broke
git add -A
git commit -m "Short description of the change"
git push -u origin my-change              # then open a pull request on GitHub
```

Small teams can also commit straight to `main`, but run `git pull` first and the tests
before every push.

### 11.4 Tagging the submission

The rules require a **tagged** repository. Once the final commit is on `main`:

```bash
git checkout main && git pull
git tag -a v1.0-submission -m "Qiskit Fall Fest 2026 submission"
git push origin v1.0-submission
```

Then check on GitHub that the repository is **public** and the tag is visible.

---

## 12. Checklist before the deadline

- [ ] `python -m pytest -q` passes on a fresh clone.
- [ ] `logs/summary_final.md` is committed and matches the numbers in `REPORT.md`.
- [ ] `REPORT.md` has team names and renders to at most 3 pages.
- [ ] `AI_USE.md` is reviewed, edited and signed by the team (it must mention both the
      Claude Code sessions and the Claude chat sessions).
- [ ] Repository is public; submission commit is tagged.
- [ ] Optional: 3-minute video.

---

## 13. References

- Nielsen & Chuang, *Quantum Computation and Quantum Information*, 10th anniversary
  edition: §1.4.4 (pp. 34–36), §5.4.3 fig. 5.5 (p. 241), §6.1 (pp. 248–254),
  §6.3 (pp. 261–262), §6.6–6.7 (pp. 269–274), §8.3.3 (p. 376).
- IBM Quantum Learning, *Fundamentals of quantum algorithms: Deutsch–Jozsa algorithm*.
- Y. Liu, "The Grover Dilemma and Three Fundamental Barriers to Oracle-Based Quantum
  Search Algorithms", *Journal of Quantum Information Science* 16(1), 2026.
- QryptoNox, *Quantum Oracle Forensics* problem statement (IBM Qiskit Fall Fest 2026, QC@IITI).
