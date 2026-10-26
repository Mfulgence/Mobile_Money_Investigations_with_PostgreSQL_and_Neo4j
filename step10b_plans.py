"""Section 6.2 step 3 and 6.3 - collect plans OUTSIDE the timing runs.
PostgreSQL: EXPLAIN (ANALYZE, BUFFERS). Neo4j: PROFILE.
Cases: Q2 (month), Q4 B depth 10, Q7 B bound 6 (SQL v1 = before, SQL v2 = after).

    python step10b_plans.py --engine pg
    python step10b_plans.py --engine neo
Plans are written to results/plans/<engine>_<case>.txt
"""
import argparse

import config
from mm_common import run_pg, neo_driver, case_params
from queries import Q2_SQL, Q2_CYPHER, Q4_SQL, q4_cypher, Q7_SQL_V1, Q7_SQL_V2, q7_cypher

PLAN_DIR = config.RESULTS_DIR / "plans"
PLAN_DIR.mkdir(parents=True, exist_ok=True)
B4 = dict(case_params("B"), depth=10)
B7 = dict(case_params("B"), bound=6, fwd_depth=3, bwd_depth=3)

PG_CASES = [("Q2_month", Q2_SQL, {}), ("Q4_B_d10", Q4_SQL, B4),
            ("Q7_B_b6_v1_before", Q7_SQL_V1, B7), ("Q7_B_b6_v2_after", Q7_SQL_V2, B7)]
NEO_CASES = [("Q2_month", Q2_CYPHER, {}), ("Q4_B_d10", q4_cypher(10), B4), ("Q7_B_b6", q7_cypher(6), B7)]


def fmt_profile(p, depth=0):
    """Render the Neo4j profile tree: operator, rows, db hits, details."""
    args = p.get("args", {})
    line = (f"{'  ' * depth}+{p.get('operatorType')}  rows={p.get('rows')}  dbHits={p.get('dbHits')}"
            f"  pageCacheHits={p.get('pageCacheHits', '-')}  time_ms={round(p.get('time', 0) / 1e6, 1) if p.get('time') else '-'}"
            f"  | {args.get('Details', '')}")
    lines = [line]
    for child in p.get("children", []):
        lines += fmt_profile(child, depth + 1)
    return lines


def totals(p):
    hits = p.get("dbHits", 0) or 0
    for c in p.get("children", []):
        hits += totals(c)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["pg", "neo"], required=True)
    a = ap.parse_args()
    if a.engine == "pg":
        for name, sql, params in PG_CASES:
            plan = run_pg("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
            text = "\n".join(r[0] for r in plan)
            (PLAN_DIR / f"pg_{name}.txt").write_text(f"-- {name}\n-- params {params}\n{sql}\n\n{text}\n")
            print(f"===== PostgreSQL {name} =====\n{text}\n")
    else:
        for name, cypher, params in NEO_CASES:
            with neo_driver().session(database=config.NEO4J_DATABASE) as s:
                summary = s.run("PROFILE " + cypher, params).consume()
            prof = summary.profile
            lines = fmt_profile(prof)
            head = (f"planner={summary.plan.get('args', {}).get('planner', '') if summary.plan else ''} "
                    f"runtime={prof.get('args', {}).get('runtime', '')} "
                    f"total dbHits={totals(prof)}  result_available_after={summary.result_available_after} ms "
                    f"consumed_after={summary.result_consumed_after} ms")
            text = head + "\n" + "\n".join(lines)
            (PLAN_DIR / f"neo_{name}.txt").write_text(f"// {name}\n// params {params}\n{cypher}\n\n{text}\n")
            print(f"===== Neo4j {name} =====\n{text}\n")
    print("Plans saved in", PLAN_DIR)


if __name__ == "__main__":
    main()
