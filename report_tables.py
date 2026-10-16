"""Print the markdown tables used in REPORT.md sections 3-5
from a benchmark log, so the report can be refreshed after every rerun:

    python report_tables.py logs/bench_final.json
"""
import json
import sys
from collections import Counter

FAMILIES = ("constant", "balanced", "linear", "grover", "randfun", "simon", "simon2", "perm")


def main(path):
    d = json.load(open(path))
    S, R = d["summaries"], d["records"]
    per = d["args"]["per_family"]

    print(f"## Budget split (mean queries, nominal noise, {per} oracles per family)\n")
    print("| family | mean queries | accuracy |")
    print("|---|---|---|")
    for f in FAMILIES:
        print(f"| {f} | {S['ours']['per_family_queries'][f]:.1f} | {S['ours']['per_family'][f]:.2f} |")

    print("\n## Results\n")
    print("| experiment | accuracy | worst family | query saving | mean queries |")
    print("|---|---|---|---|---|")
    for name, s in S.items():
        print(f"| {name} | {s['accuracy']:.3f} | {s['worst_family_accuracy']:.3f} | "
              f"{s['query_saving']:.3f} | {s['mean_queries']:.1f} |")

    print("\n## Per-family accuracy\n")
    print("| experiment | " + " | ".join(FAMILIES) + " |")
    print("|---" * (len(FAMILIES) + 1) + "|")
    for name, s in S.items():
        print(f"| {name} | " + " | ".join(f"{s['per_family'][f]:.2f}" for f in FAMILIES) + " |")

    for name in ("ours", "ours_stress", "claude_reference", "claude_reference_stress"):
        if name not in R:
            continue
        wrong = [r for r in R[name] if not r["correct"]]
        kinds = Counter((r["family"], r["answer_family"] or "none") for r in wrong)
        print(f"\n## Failures in {name}: {len(wrong)} of {len(R[name])}\n")
        for (t, a), c in sorted(kinds.items()):
            same = " (wrong secret)" if t == a else ""
            print(f"- {t} -> {a}{same}: {c}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "logs/bench_final.json")
