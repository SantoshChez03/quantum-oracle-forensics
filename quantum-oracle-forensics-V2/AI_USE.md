# AI-use disclosure

*(Draft. The team must review, edit and sign this before submission.)*

**Assistant used:** Claude (Anthropic), during the hackathon, in two ways:

1. **Claude Code** (desktop app), working in this repository.
2. **Claude chat** (claude.ai), used by a team member for design discussion, quick
   simulations, an independent reference solver and a code review of this repository.

**What the assistant did**
- Proposed the overall strategy: Bayesian identification with the noise model in the
  likelihoods, adaptive choice of experiments by information gain, sequential stopping, the
  "Grover echo" test for balanced vs randfun, and duplicated readout on spare qubits.
- Wrote the first versions of `solver.py`, the local simulator (`sim/`), `baselines.py`,
  `bench.py` and the tests.
- Ran the benchmarks and the stopping-threshold sweep that produced the files in `logs/`.
- In the chat sessions:
  - explained the problem statement and checked design choices against Nielsen & Chuang;
  - simulated an alternative plan proposed by another AI assistant (Gemini) before deciding
    what to adopt (only its 6-probe constant-1 check was taken up);
  - wrote `reference/claude_solver.py`, an independent second solver with its own simulator,
    used only for comparison;
  - reviewed this repository, added `tests/test_compliance.py`, the measurement-at-end check
    in `sim/runner.py`, the fixed solver seed and the `--reference` benchmark option, ran the
    final benchmark and drafted `MANUAL.md` and the results sections of `REPORT.md`.

**How results were checked independently**
- The simulator is tested against every check value in section 4 of the statement, against
  Qiskit bit ordering, and against noise-free textbook outcomes (Bernstein–Vazirani returns
  `a`, Simon samples are orthogonal to `s`). See `tests/`.
- The simulator is compared with **Qiskit's own `Statevector`** (oracle as an explicit
  unitary) in `tests/test_compliance.py`, and with a **second, independently written
  simulator** (differences below 10⁻¹³ on every circuit type, including 20-qubit Simon
  circuits with and without misfires).
- The analytic two-level Grover model used in the likelihoods is tested against the
  simulator's exact state vector (`test_two_level_model_matches_simulator`).
- Two independently written solvers were run on the same oracles; their results agree in
  the families where both are strong (see `logs/summary_final.md`).
- Every number in the report comes from logs that `bench.py` writes, with fixed seeds, and
  can be reproduced by rerunning it.
- *(Team: list what you re-derived or re-checked by hand, and any changes you made.)*

**What the assistant did not do**
- It did not see or use any hidden oracle, seed list or judge code. All decisions in
  `solver.py` come from `run()` results only.
