"""Sections 4 and 5 - run every Q1-Q7 query pair for all case sets, save full outputs,
print case summaries, draw the Q2 and Q4 charts and print the requested examples.

    python step08_run_queries.py --engine pg      # PostgreSQL only
    python step08_run_queries.py --engine neo     # Neo4j only
    python step08_run_queries.py --engine both    # both (default)
    python step08_run_queries.py --only Q4        # one question
    python step08_run_queries.py --q7 v2          # use the improved Q7 SQL (much faster)
Full outputs: results/outputs_pg.json / results/outputs_neo.json; examples: results/examples_<engine>.txt
"""
import argparse
import math
import time

import config
from mm_common import (CASES, Q4_DEPTHS, run_pg, run_neo, normalize, save_json, load_json, cat_time,
                       case_params, now_cat)
from queries import (all_cases, Q7_SQL_V1, Q7_SQL_V2, Q4_PATH_SQL, Q4_PATH_CYPHER, Q7_PATH_SQL, q7_path_cypher,
                     CHAIN_DETAILS_SQL, PATH_CHECK_SQL)

RUN = {"pg": lambda c: run_pg(c["sql"], c["params"]), "neo": lambda c: run_neo(c["cypher"], c["params"])}
LOG = []


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    LOG.append(line)


def run_cases(engine, cases):
    out = {}
    for c in cases:
        t0 = time.perf_counter()
        try:
            rows = normalize(RUN[engine](c))
            status = "ok"
        except Exception as e:
            rows, status = [], f"error: {e.__class__.__name__}: {str(e)[:200]}"
        out[c["case"]] = dict(params=c["params"], rows=rows, status=status,
                              seconds=round(time.perf_counter() - t0, 3))
    return out


def summarise(engine, out):
    say(f"\n================ {engine.upper()} results  ({now_cat()} CAT) ================")
    say("\nQ1 outgoing activity in the hour 09:45-10:45 CAT")
    for s in CASES:
        r = out.get(f"Q1-{s}")
        if r:
            p = r["params"]
            say(f"  {s} account {p['account']:>6}  {cat_time(p['start'])[:10]}  transfers={r['rows'][0][0]}  "
                f"total={r['rows'][0][1]:,} RWF")
    if "Q2-month" in out:
        rows = sorted(out["Q2-month"]["rows"])
        say(f"\nQ2 daily activity: {len(rows)} days, total transfers {sum(r[1] for r in rows):,}, "
            f"total value {sum(r[2] for r in rows):,} RWF")
        for r in rows:
            say(f"  {r[0]}  {r[1]:>9,} transfers  {r[2]:>15,} RWF")
    say("\nQ3 shared devices with overlapping periods")
    for s in CASES:
        r = out.get(f"Q3-{s}")
        if r:
            say(f"  {s} account {r['params']['account']}: {len(r['rows'])} rows")
            for row in r["rows"]:
                say(f"      other={row[0]:>6} device={row[1]:>6} {row[2]:15s} overlap days [{row[3]},{row[4]}]")
    say("\nQ4 distinct accounts reached through OWNS/USED_DEVICE, by owner region")
    for s in CASES:
        parts = []
        for d in Q4_DEPTHS:
            r = out.get(f"Q4-{s}-d{d}")
            if r:
                parts.append(f"d{d}={sum(x[1] for x in r['rows'])}")
        if parts:
            say(f"  {s}: " + "  ".join(parts))
    for s in CASES:
        for d in Q4_DEPTHS:
            r = out.get(f"Q4-{s}-d{d}")
            if r:
                say(f"    {s} depth {d:>2}: " + ", ".join(f"{reg} {n}" for reg, n in r["rows"]))
    for q, title in (("Q5", "rapid onward chains (3 transfers, 4 accounts)"), ("Q6", "circular sequences")):
        say(f"\n{q} {title}")
        for s in CASES:
            r = out.get(f"{q}-{s}")
            if r:
                say(f"  {s} account {r['params']['account']}: {len(r['rows'])} rows  {r['rows']}")
    say("\nQ7 fewest directed person-to-person transfers to the destination")
    for s in CASES:
        vals = []
        for b in (4, 6):
            r = out.get(f"Q7-{s}-b{b}")
            if r and r["status"] != "ok":
                vals.append(f"bound {b}: ERROR (see status)")
            elif r:
                v = r["rows"][0][0] if r["rows"] else None
                vals.append(f"bound {b}: {v if v is not None else 'no route within bound'}")
        if vals:
            p = case_params(s)
            say(f"  {s} {p['account']} -> {p['destination']}:  " + " | ".join(vals))
    bad = {k: v["status"] for k, v in out.items() if v["status"] != "ok"}
    say(f"\nCases run: {len(out)}   errors: {len(bad)} {bad if bad else ''}")


def verify_path(accounts, tids, length):
    """Check IDs, direction, person roles, event existence and length against stored rows."""
    rows = {r[0]: r for r in run_pg(PATH_CHECK_SQL, dict(ids=list(tids)))}
    ok = len(tids) == length == len(accounts) - 1 and len(rows) == length
    for i, tid in enumerate(tids):
        r = rows.get(tid)
        ok &= bool(r) and r[1] == accounts[i] and r[2] == accounts[i + 1] and r[5] == r[6] == "person"
    return ok


def q7_paths(engine, out):
    say(f"\nQ7 supporting paths ({engine}) - verified for IDs, direction, roles, events and length")
    res = {}
    for s in CASES:
        for b in (4, 6):
            r = out.get(f"Q7-{s}-b{b}")
            if not r or not r["rows"] or r["rows"][0][0] is None:
                continue
            L, p = r["rows"][0][0], case_params(s)
            if engine == "pg":
                rows = run_pg(Q7_PATH_SQL, dict(p, length=L))
            else:
                rows = run_neo(q7_path_cypher(b), p)
            acc, tids, plen = rows[0][0], rows[0][1], rows[0][2]
            ok = verify_path(acc, tids, L)
            res[f"Q7-{s}-b{b}"] = dict(accounts=list(acc), transfer_ids=list(tids), length=plen, valid=ok)
            say(f"  {s} bound {b}: length {plen}  accounts {list(acc)}  transfers {list(tids)}  valid={ok}")
    return res


def examples(engine, out):
    """Requested examples: Q4 supporting path, Q5 chain and Q6 cycle with CAT times and amounts."""
    say(f"\n---------------- examples ({engine}) ----------------")
    r = out.get("Q4-A-d4")
    if r:
        p = case_params("A")
        target = 24755
        if engine == "pg":
            path = run_pg(Q4_PATH_SQL, dict(account=p["account"], depth=4, target=target))
        else:
            path = run_neo(Q4_PATH_CYPHER, dict(account=p["account"], target=target))
        say(f"Q4 supporting path A (998 -> {target}): {path}")
    for q in ("Q5", "Q6"):
        for s in CASES:
            r = out.get(f"{q}-{s}")
            if r and r["rows"]:
                ids = list(r["rows"][0][:3]) if q == "Q5" else list(r["rows"][0][0])
                say(f"{q} example from set {s} (account {r['params']['account']}), transfer ids {ids}:")
                for d in run_pg(CHAIN_DETAILS_SQL, dict(ids=ids)):
                    say(f"    t{d[0]}  {d[1]} ({d[2]}) -> {d[3]} ({d[4]})  {d[6]} CAT  {d[7]:,} RWF")
                break


def plots(out, engine):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if "Q2-month" in out:
        rows = sorted(out["Q2-month"]["rows"])
        days = [r[0][5:] for r in rows]
        counts = [r[1] for r in rows]
        values = [r[2] / 1e9 for r in rows]
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        ax1.bar(days, counts, color="#4C72B0")
        ax1.set_ylim(min(counts) - 100, max(counts) + 60)
        ax1.set_ylabel("Transfers per day (count)")
        ax1.set_title(f"Q2 Daily transfers, September 2026 CAT ({engine}) - y-axes zoomed, not starting at zero")
        ax1.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax2.plot(days, values, color="#DD8452", marker="o")
        ax2.set_ylabel("Value per day (billion RWF)")
        ax2.set_xlabel("Date in September 2026 (CAT)")
        ax2.tick_params(axis="x", rotation=60)
        for ax in (ax1, ax2):
            ax.grid(axis="y", alpha=.3)
        fig.tight_layout()
        fig.savefig(config.PLOTS_DIR / f"q2_daily_{engine}.png", dpi=150)
        plt.close(fig)
    if any(k.startswith("Q4") for k in out):
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for s in CASES:
            ys = [sum(x[1] for x in out[f"Q4-{s}-d{d}"]["rows"]) for d in Q4_DEPTHS if f"Q4-{s}-d{d}" in out]
            if ys:
                ax.plot(Q4_DEPTHS[:len(ys)], ys, marker="o", label=f"{s} ({CASES[s][0]})")
        ax.set_xlabel("Maximum links (OWNS / USED_DEVICE, either direction)")
        ax.set_ylabel("Distinct other accounts reached")
        ax.set_xticks(Q4_DEPTHS)
        ax.set_title(f"Q4 Accounts reached versus depth ({engine})")
        ax.legend()
        ax.grid(alpha=.3)
        fig.tight_layout()
        fig.savefig(config.PLOTS_DIR / f"q4_depth_{engine}.png", dpi=150)
        plt.close(fig)
    say(f"Charts saved in {config.PLOTS_DIR}")


def q4_with_prediction(engine, cases, out):
    """Run depths 4 and 6, record a geometric prediction for 8 and 10, then run 8 and 10."""
    q4 = [c for c in cases if c["q"] == "Q4"]
    out.update(run_cases(engine, [c for c in q4 if c["params"]["depth"] in (4, 6)]))
    pred = {}
    say("\nQ4 prediction made BEFORE running depths 8 and 10 (growth factor d4->d6 applied again):")
    for s in CASES:
        n4 = sum(x[1] for x in out[f"Q4-{s}-d4"]["rows"])
        n6 = sum(x[1] for x in out[f"Q4-{s}-d6"]["rows"])
        g = n6 / n4 if n4 else 1
        pred[s] = dict(d8=round(n6 * g), d10=round(n6 * g * g))
        say(f"  {s}: d4={n4} d6={n6} growth x{g:.2f} -> predicted d8~{pred[s]['d8']} d10~{pred[s]['d10']}")
    out.update(run_cases(engine, [c for c in q4 if c["params"]["depth"] in (8, 10)]))
    for s in CASES:
        a8 = sum(x[1] for x in out[f"Q4-{s}-d8"]["rows"])
        a10 = sum(x[1] for x in out[f"Q4-{s}-d10"]["rows"])
        say(f"  {s}: actual d8={a8} (predicted {pred[s]['d8']})  d10={a10} (predicted {pred[s]['d10']})")
    return pred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["pg", "neo", "both"], default="both")
    ap.add_argument("--only", help="e.g. Q4")
    ap.add_argument("--q7", choices=["v1", "v2"], default="v1", help="SQL version for Q7 (v2 = Section 6.3)")
    a = ap.parse_args()
    engines = ["pg", "neo"] if a.engine == "both" else [a.engine]
    cases = [c for c in all_cases(Q7_SQL_V1 if a.q7 == "v1" else Q7_SQL_V2) if not a.only or c["q"] == a.only]
    for engine in engines:
        LOG.clear()
        say(f"Running {len(cases)} cases on {engine} at {now_cat()} CAT")
        out = run_cases(engine, [c for c in cases if c["q"] != "Q4"])
        pred = q4_with_prediction(engine, cases, out) if any(c["q"] == "Q4" for c in cases) else {}
        summarise(engine, out)
        paths = q7_paths(engine, out)
        examples(engine, out)
        plots(out, engine)
        save_json(f"outputs_{engine}.json", dict(run_at_cat=now_cat(), cases=out, q4_prediction=pred,
                                                 q7_paths=paths))
        (config.RESULTS_DIR / f"examples_{engine}.txt").write_text("\n".join(LOG), encoding="utf-8")
        say(f"Saved results/outputs_{engine}.json and results/examples_{engine}.txt")


if __name__ == "__main__":
    main()
