"""Section 6.2 (and 6.3 retiming) - time the fixed selection of 21 cases on ONE engine.

Stop the other database service first, so only one engine uses the machine.
    python step10_benchmark.py --engine pg              # 21 PostgreSQL cases, Q7 SQL v1
    python step10_benchmark.py --engine neo             # 21 Neo4j cases
    python step10_benchmark.py --engine pg --q7 v2 --only Q7   # Section 6.3: 4 revised SQL cases
    python step10_benchmark.py --summary                # median/min/max table + PG/Neo4j ratio

Per case: 3 untimed warm-ups (180 s limit each), then 5 measured runs (60 s limit each),
timed with perf_counter from submission until the final row has been received.
Errors and timeouts are recorded separately, never as completed timings.
"""
import argparse
import csv
import statistics
import time

import config
from mm_common import run_pg, run_neo, normalize, now_cat, save_json
from queries import timed_cases, Q7_SQL_V1, Q7_SQL_V2

WARMUPS, RUNS, WARM_TIMEOUT, RUN_TIMEOUT = 3, 5, 180, 60
FIELDS = ["case", "question", "params", "engine", "variant", "phase", "run", "start_cat", "duration_ms", "rows", "status"]


def classify(e):
    msg = f"{e.__class__.__name__}: {e}".lower()
    return "timeout" if ("timeout" in msg or "timed out" in msg or "cancel" in msg or "terminated" in msg) else "error"


def call(engine, case, timeout_s):
    if engine == "pg":
        return run_pg(case["sql"], case["params"], timeout_s=timeout_s)
    return run_neo(case["cypher"], case["params"], timeout_s=timeout_s)


def bench(engine, variant, only):
    cases = [c for c in timed_cases(Q7_SQL_V1 if variant != "v2" else Q7_SQL_V2) if not only or c["q"] == only]
    log, answers = [], {}
    print(f"Benchmark {engine} ({variant}) - {len(cases)} cases - started {now_cat()} CAT")
    for c in cases:
        params = {k: v for k, v in c["params"].items() if k in ("account", "start", "end", "depth", "bound", "destination")}
        for phase, n, limit in (("warmup", WARMUPS, WARM_TIMEOUT), ("measured", RUNS, RUN_TIMEOUT)):
            for i in range(1, n + 1):
                start_cat = now_cat()
                status, rows = "ok", None
                t0 = time.perf_counter()
                try:
                    rows = call(engine, c, limit)      # wrapper fetches every row
                except Exception as e:
                    status = classify(e)
                dur = (time.perf_counter() - t0) * 1000
                log.append(dict(case=c["case"], question=c["q"], params=params, engine=engine, variant=variant,
                                phase=phase, run=i, start_cat=start_cat, duration_ms=round(dur, 2),
                                rows=len(rows) if rows is not None else None, status=status))
                if rows is not None:   # answer checked OUTSIDE the timed region
                    answers.setdefault(c["case"], set()).add(repr(normalize(rows)))
        ms = [r["duration_ms"] for r in log if r["case"] == c["case"] and r["phase"] == "measured" and r["status"] == "ok"]
        bad = [r["status"] for r in log if r["case"] == c["case"] and r["phase"] == "measured" and r["status"] != "ok"]
        med = f"{statistics.median(ms):10.1f} ms" if ms else "      n/a   "
        print(f"  {c['case']:12s} median {med}  ok={len(ms)}  failed={bad}")
    stable = {k: len(v) == 1 for k, v in answers.items()}
    print("Every run returned the same answer:", all(stable.values()))
    tag = f"{engine}_{variant}" + (f"_{only}" if only else "")
    with open(config.RESULTS_DIR / f"bench_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in log:
            w.writerow(dict(r, params=str(r["params"])))
    print(f"Raw runs saved to results/bench_{tag}.csv")


def summary():
    rows = []
    for p in sorted(config.RESULTS_DIR.glob("bench_*.csv")):
        rows += list(csv.DictReader(open(p, newline="")))
    groups = {}
    for r in rows:
        if r["phase"] != "measured":
            continue
        key = (r["case"], r["engine"], r["variant"])
        groups.setdefault(key, dict(ok=[], fail=0))
        if r["status"] == "ok":
            groups[key]["ok"].append(float(r["duration_ms"]))
        else:
            groups[key]["fail"] += 1
    table = []
    for (case, engine, variant), g in sorted(groups.items()):
        ok = g["ok"]
        table.append(dict(case=case, engine=engine, variant=variant, runs_ok=len(ok), failed=g["fail"],
                          median_ms=round(statistics.median(ok), 2) if ok else None,
                          min_ms=round(min(ok), 2) if ok else None, max_ms=round(max(ok), 2) if ok else None))
    print(f"{'case':12s} {'engine':6s} {'var':4s} {'ok':>3} {'fail':>4} {'median ms':>11} {'min ms':>10} {'max ms':>10}")
    for t in table:
        f = lambda v: f"{v:>11.1f}" if v is not None else f"{'-':>11}"
        print(f"{t['case']:12s} {t['engine']:6s} {t['variant']:4s} {t['runs_ok']:>3} {t['failed']:>4} "
              f"{f(t['median_ms'])} {f(t['min_ms'])[1:]} {f(t['max_ms'])[1:]}")
    # PostgreSQL / Neo4j median ratio (Neo4j has no Q7 variants; it is compared with each SQL version)
    print("\nPostgreSQL / Neo4j median ratio (>1 means Neo4j faster)")
    neo = {t["case"]: t["median_ms"] for t in table if t["engine"] == "neo"}
    ratios = []
    for t in table:
        if t["engine"] == "pg" and t["case"] in neo:
            r = (t["median_ms"] / neo[t["case"]]) if t["median_ms"] and neo[t["case"]] else None
            ratios.append(dict(case=t["case"], sql_variant=t["variant"], pg_median_ms=t["median_ms"],
                               neo_median_ms=neo[t["case"]], ratio=round(r, 3) if r else None))
            print(f"  {t['case']:12s} SQL {t['variant']}: {t['median_ms']} / {neo[t['case']]} = "
                  f"{(f'{r:.2f}' if r else 'n/a (timeout/error)')}")
    save_json("bench_summary.json", dict(table=table, ratios=ratios))
    with open(config.RESULTS_DIR / "bench_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print("Saved results/bench_summary.csv and bench_summary.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["pg", "neo"])
    ap.add_argument("--q7", choices=["v1", "v2"], default="v1", help="SQL Q7 version (ignored for neo)")
    ap.add_argument("--only", help="e.g. Q7")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if a.summary:
        return summary()
    if not a.engine:
        ap.error("--engine pg|neo required")
    bench(a.engine, a.q7 if a.engine == "pg" else "cypher", a.only)


if __name__ == "__main__":
    main()
