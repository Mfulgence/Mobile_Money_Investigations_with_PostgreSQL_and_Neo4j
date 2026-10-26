"""Section 6.1 - one comparison program for the 61 cases (Q1 6, Q2 1, Q3 6, Q4 24, Q5 6, Q6 6, Q7 12).
Both engines must be running. Rows are normalised (ints, tuples) and sorted before exact comparison.
Q7 lengths are compared exactly; supporting paths are compared separately by validity, because
equally short paths may differ.

    python step09_compare.py                 # Q7 SQL version 1 (baseline)
    python step09_compare.py --q7 v2         # Q7 SQL version 2 (Section 6.3 improvement)
"""
import argparse
import csv
import time

import config
from mm_common import run_pg, run_neo, normalize, save_json, now_cat, case_params
from queries import all_cases, Q7_SQL_V1, Q7_SQL_V2, Q7_PATH_SQL, q7_path_cypher
from step08_run_queries import verify_path


def timed(fn, *a):
    t0 = time.perf_counter()
    try:
        return normalize(fn(*a)), "ok", time.perf_counter() - t0
    except Exception as e:
        return None, f"error: {e.__class__.__name__}: {str(e)[:150]}", time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q7", choices=["v1", "v2"], default="v1")
    a = ap.parse_args()
    q7sql = Q7_SQL_V1 if a.q7 == "v1" else Q7_SQL_V2
    for name, fn in (("PostgreSQL", lambda: run_pg("SELECT 1")), ("Neo4j", lambda: run_neo("RETURN 1"))):
        try:
            fn()
        except Exception as e:
            raise SystemExit(f"{name} is not reachable ({e.__class__.__name__}). Start both services first.")
    started = now_cat()
    rows_out, full = [], {}
    print(f"61-case comparison started {started} CAT  (Q7 SQL {a.q7})")
    print(f"{'#':>3} {'case':12s} {'pg rows':>8} {'neo rows':>8} {'pg ms':>9} {'neo ms':>9}  status")
    for i, c in enumerate(all_cases(q7sql), 1):
        pg, s1, t1 = timed(run_pg, c["sql"], c["params"])
        neo, s2, t2 = timed(run_neo, c["cypher"], c["params"])
        if s1 != "ok" or s2 != "ok":
            status = f"ERROR pg={s1} neo={s2}"
        elif c["q"] == "Q7":
            status = "MATCH (length)" if pg == neo else "MISMATCH (length)"
        else:
            status = "MATCH" if pg == neo else "MISMATCH"
        print(f"{i:>3} {c['case']:12s} {len(pg or []):>8} {len(neo or []):>8} {t1*1000:9.1f} {t2*1000:9.1f}  {status}")
        if status.startswith("MISMATCH"):
            only_pg = [r for r in pg if r not in neo][:5]
            only_neo = [r for r in neo if r not in pg][:5]
            print(f"      only in PostgreSQL: {only_pg}\n      only in Neo4j:      {only_neo}")
        rows_out.append(dict(n=i, case=c["case"], question=c["q"], pg_rows=len(pg or []), neo_rows=len(neo or []),
                             pg_ms=round(t1 * 1000, 1), neo_ms=round(t2 * 1000, 1), status=status))
        full[c["case"]] = dict(params=c["params"], pg=pg, neo=neo, status=status)

    print("\nQ7 supporting paths (compared by validity, not equality)")
    path_rows = []
    for c in all_cases(q7sql):
        if c["q"] != "Q7":
            continue
        L = full[c["case"]]["pg"][0][0] if full[c["case"]]["pg"] else None
        if L is None:
            path_rows.append(dict(case=c["case"], length=None, pg_valid="n/a", neo_valid="n/a", same_path="n/a"))
            print(f"  {c['case']:10s} no route within bound - nothing to verify")
            continue
        p = c["params"]
        pp = run_pg(Q7_PATH_SQL, dict(p, length=L))[0]
        npth = run_neo(q7_path_cypher(p["bound"]), p)[0]
        v1, v2 = verify_path(pp[0], pp[1], L), verify_path(npth[0], npth[1], L)
        same = list(pp[1]) == list(npth[1])
        path_rows.append(dict(case=c["case"], length=L, pg_path=list(pp[1]), neo_path=list(npth[1]),
                              pg_valid=v1, neo_valid=v2, same_path=same))
        print(f"  {c['case']:10s} length {L}  pg valid={v1}  neo valid={v2}  identical={same}")

    by_q = {}
    for r in rows_out:
        by_q.setdefault(r["question"], [0, 0])
        by_q[r["question"]][0] += 1
        by_q[r["question"]][1] += r["status"].startswith("MATCH")
    print("\nSummary per question:", {q: f"{m}/{n} match" for q, (n, m) in by_q.items()})
    total = sum(m for n, m in by_q.values())
    paths_ok = all(r["pg_valid"] in (True, "n/a") and r["neo_valid"] in (True, "n/a") for r in path_rows)
    print(f"TOTAL {total}/61 cases match;  all supporting paths valid: {paths_ok};  finished {now_cat()} CAT")
    tag = a.q7
    with open(config.RESULTS_DIR / f"compare_61_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    save_json(f"compare_61_{tag}.json", dict(started=started, finished=now_cat(), total_match=total,
                                             table=rows_out, q7_paths=path_rows, full_outputs=full))


if __name__ == "__main__":
    main()
