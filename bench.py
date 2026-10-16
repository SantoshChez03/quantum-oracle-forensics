"""Benchmark harness: accuracy, worst-family accuracy, query saving, stress noise, baselines,
confusion matrix and accuracy-vs-budget (section 9).  Writes logs/bench_<tag>.json (one
record per task) and logs/summary_<tag>.md.

    python bench.py --per-family 50 --workers 8 --tag final
    python bench.py --per-family 10 --only ours          # quick check
    python bench.py --per-family 50 --tag final --reference          # + reference solver
    # after a change that only affects m = 1, rerun just those records in place:
    python bench.py --tag final --update --only ours,ours_stress --families constant,balanced,linear,grover,randfun
"""
import argparse
import json
import os
import time
from multiprocessing import Pool

import numpy as np

import baselines
import solver
from reference import claude_solver
from sim.oracles import FAMILIES, random_oracle
from sim.runner import BudgetExceeded, OracleRunner

NOMINAL = (0.04, 0.02)
STRESS = (0.08, 0.04)

EXPERIMENTS_ALL = {   # name -> (strategy, noise, budget)
    "ours": ("ours", NOMINAL, 60),
    "ours_stress": ("ours", STRESS, 60),
    "ours_budget20": ("ours", NOMINAL, 20),
    "ours_budget30": ("ours", NOMINAL, 30),
    "ours_budget40": ("ours", NOMINAL, 40),
    "ours_budget50": ("ours", NOMINAL, 50),
    "no_readout_copies": ("ours_no_readout_copies", NOMINAL, 60),
    "no_readout_copies_stress": ("ours_no_readout_copies", STRESS, 60),
    "non_adaptive": ("non_adaptive", NOMINAL, 60),
    "single_algorithm": ("single_algorithm", NOMINAL, 60),
    "classical_only": ("classical_only", NOMINAL, 60),
    "random_guess": ("random_guess", NOMINAL, 60),
    "claude_reference": ("claude_reference", NOMINAL, 60),          # only with --reference
    "claude_reference_stress": ("claude_reference", STRESS, 60),    # only with --reference
}


DELTA = solver.DELTA


def _set_delta(delta):
    global DELTA
    DELTA = delta


def _ours(n, m, budget, families, run, rng, copies=True):
    if m == 1:
        return solver.solve_m1(n, budget, families, run, rng=rng, readout_copies=copies, delta=DELTA)
    return solver.solve_m8(n, m, budget, families, run, readout_copies=copies, delta=DELTA)


STRATEGIES = {
    "ours": _ours,
    "ours_no_readout_copies": lambda *a: _ours(*a, copies=False),
    "classical_only": baselines.classical_only,
    "single_algorithm": baselines.single_algorithm,
    "non_adaptive": baselines.non_adaptive,
    "random_guess": baselines.random_guess,
    # independent second solver (reference/claude_solver.py), for a paired comparison
    "claude_reference": lambda n, m, budget, families, run, rng:
        claude_solver.solve(n, m, budget, families, run),
}


def run_task(args):
    strategy, family, seed, noise, budget = args
    rng = np.random.default_rng(seed)
    oracle = random_oracle(family, rng)
    runner = OracleRunner(oracle, budget=budget, p_misfire=noise[0], p_flip=noise[1], seed=seed + 1)
    t0 = time.time()
    try:
        fam, secret = STRATEGIES[strategy](8, oracle.m, budget, list(FAMILIES), runner,
                                           np.random.default_rng(seed + 2))
        error = None
    except BudgetExceeded as e:                       # counts as no answer
        fam, secret, error = None, None, str(e)
    correct = fam == oracle.family and (oracle.secret is None or secret == oracle.secret)
    return {"strategy": strategy, "noise": list(noise), "budget": budget, "seed": seed,
            "family": family, "secret": oracle.secret, "answer_family": fam, "answer_secret": secret,
            "correct": bool(correct), "queries": runner.queries, "seconds": round(time.time() - t0, 2),
            "error": error}


def summarize(records, budget):
    by_fam = {}
    for f in FAMILIES:
        r = [x for x in records if x["family"] == f]
        by_fam[f] = (sum(x["correct"] for x in r) / len(r)) if r else float("nan")
    correct = [x for x in records if x["correct"]]
    return {
        "accuracy": sum(x["correct"] for x in records) / len(records),
        "worst_family_accuracy": min(by_fam.values()),
        "query_saving": float(np.mean([1 - x["queries"] / budget for x in correct])) if correct else 0.0,
        "mean_queries": float(np.mean([x["queries"] for x in records])),
        "max_seconds": max(x["seconds"] for x in records),
        "per_family": by_fam,
        "per_family_queries": {f: float(np.mean([x["queries"] for x in records if x["family"] == f]))
                               for f in FAMILIES},
    }


def confusion(records):
    labels = list(FAMILIES) + ["none"]
    M = {f: {g: 0 for g in labels} for f in FAMILIES}
    for x in records:
        M[x["family"]][x["answer_family"] or "none"] += 1
    return M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-family", type=int, default=50)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--only", default=None, help="comma-separated subset of experiments")
    ap.add_argument("--tag", default=time.strftime("%Y%m%d_%H%M%S"))
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--delta", type=float, default=solver.DELTA, help="stopping threshold for 'ours'")
    ap.add_argument("--families", default=None,
                    help="comma-separated subset of families (default: all eight)")
    ap.add_argument("--update", action="store_true",
                    help="merge into the existing logs/bench_<tag>.json: rerun only the selected "
                         "experiments/families and keep every other record")
    ap.add_argument("--reference", action="store_true",
                    help="also run reference/claude_solver.py on the same oracles")
    args = ap.parse_args()

    selected = [k for k in EXPERIMENTS_ALL if not k.startswith("claude_reference") or args.reference]
    if args.only:
        selected = [k for k in selected if k in args.only.split(",")]
    rerun = set(selected)

    fams = tuple(args.families.split(",")) if args.families else FAMILIES
    os.makedirs("logs", exist_ok=True)
    all_records, summaries = {}, {}
    if args.update:
        with open(f"logs/bench_{args.tag}.json") as fh:
            old = json.load(fh)
        all_records = old["records"]
        args.per_family = old["args"]["per_family"]
        args.seed = old["args"]["seed"]
    elif fams != FAMILIES:
        raise SystemExit("--families needs --update (it replaces part of an existing log)")
    experiments = {k: v for k, v in EXPERIMENTS_ALL.items() if k in rerun or k in all_records}
    with Pool(args.workers, initializer=_set_delta, initargs=(args.delta,)) as pool:
        for name, (strategy, noise, budget) in experiments.items():
            t0 = time.time()
            # same oracle seeds for every experiment -> paired comparison
            if name in rerun:
                jobs = [(strategy, fam, args.seed + 1000 * k + i, noise, budget)
                        for k, fam in enumerate(FAMILIES) if fam in fams
                        for i in range(args.per_family)]
                new = pool.map(run_task, jobs, chunksize=1)
                keep = [r for r in all_records.get(name, []) if r["family"] not in fams]
                order = {f: i for i, f in enumerate(FAMILIES)}
                recs = sorted(keep + new, key=lambda r: (order[r["family"]], r["seed"]))
            else:
                recs = all_records[name]
            all_records[name] = recs
            summaries[name] = summarize(recs, 60)
            s = summaries[name]
            print(f"{name:26s} acc {s['accuracy']:.3f}  worst {s['worst_family_accuracy']:.3f}  "
                  f"saving {s['query_saving']:.3f}  meanQ {s['mean_queries']:.1f}  "
                  f"maxT {s['max_seconds']:.1f}s  ({time.time() - t0:.0f}s)", flush=True)

    with open(f"logs/bench_{args.tag}.json", "w") as fh:
        json.dump({"args": vars(args), "summaries": summaries, "records": all_records}, fh, indent=1)

    lines = [f"# Benchmark {args.tag}", "",
             f"{args.per_family} random oracles per family per experiment; the same oracle seeds are "
             "used in every experiment. Query saving is over correct tasks, relative to 60.", "",
             "| experiment | noise (misfire, flip) | budget | accuracy | worst family | query saving | mean queries |",
             "|---|---|---|---|---|---|---|"]
    for name, (strategy, noise, budget) in experiments.items():
        s = summaries[name]
        lines.append(f"| {name} | {noise} | {budget} | {s['accuracy']:.3f} | {s['worst_family_accuracy']:.3f} | "
                     f"{s['query_saving']:.3f} | {s['mean_queries']:.1f} |")
    lines += ["", "## Per-family accuracy / mean queries", "",
              "| experiment | " + " | ".join(FAMILIES) + " |", "|---" * (len(FAMILIES) + 1) + "|"]
    for name in experiments:
        s = summaries[name]
        lines.append(f"| {name} | " + " | ".join(
            f"{s['per_family'][f]:.2f} / {s['per_family_queries'][f]:.0f}" for f in FAMILIES) + " |")
    for name in ("ours", "ours_stress"):
        if name in all_records:
            M = confusion(all_records[name])
            labels = list(FAMILIES) + ["none"]
            lines += ["", f"## Confusion matrix ({name}; rows = true family, columns = reported family; "
                          "secret errors are not shown here)", "",
                      "| true \\ reported | " + " | ".join(labels) + " |", "|---" * (len(labels) + 1) + "|"]
            for f in FAMILIES:
                lines.append(f"| {f} | " + " | ".join(str(M[f][g]) for g in labels) + " |")
            wrong = [x for x in all_records[name] if not x["correct"]]
            lines += ["", f"Failures in {name}: {len(wrong)}", ""]
            for x in wrong:
                lines.append(f"- {x['family']} secret={x['secret']} -> {x['answer_family']} "
                             f"{x['answer_secret']} (queries {x['queries']}, seed {x['seed']})")
    with open(f"logs/summary_{args.tag}.md", "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote logs/bench_{args.tag}.json and logs/summary_{args.tag}.md")


if __name__ == "__main__":
    main()
