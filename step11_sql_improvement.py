"""Section 6.3 - one SQL improvement for Q7: search from both ends (meet in the middle).

Prediction (write it in the report BEFORE running): version 1 expands every (account, depth)
state up to 6 transfers from the review account - roughly 16 distinct contacts per person,
so ~16^5 (about 1 million) states and tens of millions of index probes at bound 6. Version 2
expands only 3 levels forward and 3 backward (~16^3 = 4,096 states each side), so it should be
two to three orders of magnitude faster, with identical lengths.

    python step11_sql_improvement.py              # recheck all 12 cases (v1 vs v2 [vs Neo4j]) + retime 4 cases
    python step11_sql_improvement.py --no-time    # correctness only
"""
import argparse
import time

from mm_common import run_pg, run_neo, save_json, now_cat
from queries import all_cases, Q7_SQL_V1, Q7_SQL_V2, Q7_PATH_SQL
from step08_run_queries import verify_path
import step10_benchmark


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-time", action="store_true")
    ap.add_argument("--no-neo", action="store_true", help="skip the Neo4j length comparison")
    a = ap.parse_args()
    v1 = {c["case"]: c for c in all_cases(Q7_SQL_V1) if c["q"] == "Q7"}
    v2 = {c["case"]: c for c in all_cases(Q7_SQL_V2) if c["q"] == "Q7"}
    print(f"Q7 correctness recheck, {now_cat()} CAT")
    print(f"{'case':10s} {'v1 len':>7} {'v1 ms':>9} {'v2 len':>7} {'v2 ms':>8} {'neo len':>8}  path ok  status")
    rows, all_ok = [], True
    for k in v1:
        t = time.perf_counter(); l1 = run_pg(v1[k]["sql"], v1[k]["params"])[0][0]; t1 = time.perf_counter() - t
        t = time.perf_counter(); l2 = run_pg(v2[k]["sql"], v2[k]["params"])[0][0]; t2 = time.perf_counter() - t
        ln = "-"
        if not a.no_neo:
            try:
                ln = run_neo(v1[k]["cypher"], v1[k]["params"])[0][0]
            except Exception as e:
                ln = f"n/a ({e.__class__.__name__})"
        path_ok = "n/a"
        if l2 is not None:
            p = run_pg(Q7_PATH_SQL, dict(v2[k]["params"], length=l2))[0]
            path_ok = verify_path(p[0], p[1], l2)
        ok = l1 == l2 and (ln in ("-",) or str(ln).startswith("n/a") or ln == l2) and path_ok in (True, "n/a")
        all_ok &= ok
        print(f"{k:10s} {str(l1):>7} {t1*1000:9.1f} {str(l2):>7} {t2*1000:8.1f} {str(ln):>8}  {str(path_ok):7s}  "
              f"{'MATCH' if ok else 'MISMATCH'}")
        rows.append(dict(case=k, v1_length=l1, v1_ms=round(t1 * 1000, 1), v2_length=l2,
                         v2_ms=round(t2 * 1000, 1), neo_length=ln, path_valid=path_ok, ok=ok))
    print("All 12 Q7 cases correct with version 2:", all_ok)
    save_json("q7_improvement_check.json", dict(checked_at=now_cat(), all_ok=all_ok, rows=rows))
    if not a.no_time:
        print("\nRetiming the 4 revised SQL cases (B/E, bounds 4 and 6) with 3 warm-ups + 5 runs ...")
        step10_benchmark.bench("pg", "v2", "Q7")


if __name__ == "__main__":
    main()
