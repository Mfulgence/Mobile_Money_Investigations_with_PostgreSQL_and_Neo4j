"""Section 7.2 - plots of throughput and p95 latency against client count,
for both workloads and both engines (median of the three repetitions).
    python step12b_plot_scaling.py
"""
import csv
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from step12_load_test import CLIENTS

reps = []
for p in sorted(config.RESULTS_DIR.glob("load_reps_*.csv")):
    reps += list(csv.DictReader(open(p, newline="")))
series = {}
for r in reps:
    series.setdefault((r["engine"], r["workload"]), {}).setdefault(int(r["clients"]), []).append(r)

NAMES = {"pg": "PostgreSQL", "neo": "Neo4j"}
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
for col, workload in enumerate(("Q4_d10", "Q7_b6")):
    for engine, style in (("pg", "o-"), ("neo", "s--")):
        data = series.get((engine, workload))
        if not data:
            continue
        xs = sorted(data)
        thr = [statistics.median(float(x["throughput_rps"]) for x in data[n]) for n in xs]
        p95 = [statistics.median(float(x["p95_ms"]) for x in data[n] if x["p95_ms"] not in ("", "None")) for n in xs]
        axes[0][col].plot(xs, thr, style, label=NAMES[engine])
        axes[1][col].plot(xs, p95, style, label=NAMES[engine])
    axes[0][col].set_title(f"{workload.replace('_', ' ')} - throughput")
    axes[0][col].set_ylabel("Correct requests per second")
    axes[1][col].set_title(f"{workload.replace('_', ' ')} - p95 latency")
    axes[1][col].set_ylabel("p95 latency (ms)")
    for row in (0, 1):
        ax = axes[row][col]
        ax.set_xlabel("Concurrent clients")
        ax.set_xticks(CLIENTS)
        ax.grid(alpha=.3)
        ax.legend()
fig.suptitle("Section 7 load test (median of 3 repetitions, 15 s window)")
fig.tight_layout()
out = config.PLOTS_DIR / "load_scaling.png"
fig.savefig(out, dpi=150)
print("Saved", out)
