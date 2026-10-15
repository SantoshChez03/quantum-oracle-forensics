# AI-use disclosure

*(Draft. The team must review, edit and sign this before submission.)*

**Assistant used:** Claude (Anthropic), through the Claude Code desktop app, during the hackathon.

**What the assistant did**
- Proposed the overall strategy: Bayesian identification with the noise model in the
  likelihoods, adaptive choice of experiments by information gain, sequential stopping, the
  "Grover echo" test for balanced vs randfun, and duplicated readout on spare qubits.
- Wrote the first versions of `solver.py`, the local simulator (`sim/`), `baselines.py`,
  `bench.py` and the tests.
- Ran the benchmarks and the stopping-threshold sweep that produced the files in `logs/`.

**How results were checked independently**
- The simulator is tested against every check value in section 4 of the statement, against
  Qiskit bit ordering, and against noise-free textbook outcomes (Bernstein–Vazirani returns
  `a`, Simon samples are orthogonal to `s`). See `tests/`.
- The analytic two-level Grover model used in the likelihoods is tested against the
  simulator's exact state vector (`test_two_level_model_matches_simulator`).
- Every number in the report comes from logs that `bench.py` writes, with fixed seeds, and
  can be reproduced by rerunning it.
- *(Team: list what you re-derived or re-checked by hand, and any changes you made.)*

**What the assistant did not do**
- It did not see or use any hidden oracle, seed list or judge code. All decisions in
  `solver.py` come from `run()` results only.
