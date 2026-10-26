"""Section 7.1 - small concurrent load test with multiprocessing.

Workloads: Q4 depth 10 and Q7 length-only bound 6, each cycling sets A-B-C.
Client counts 1, 4, 8, 16; three repetitions per engine/workload/client count.
One persistent connection per process, a Barrier to synchronise starts, a common start time
and a deadline 15 s later. A client keeps starting cycles until the deadline, finishes any cycle
it started, and submits the next request immediately after the previous one completes.

    python step12_load_test.py --engine pg            # uses the Section 6 SQL choice (Q7 v2 by default)
    python step12_load_test.py --engine neo
    python step12_load_test.py --summary              # table of the 16 combination summaries
Run with only the tested database service started.
"""
import argparse
import csv
import math
import multiprocessing as mp
import statistics
import time

import config
from mm_common import now_cat, normalize, case_params, save_json

WORKLOADS = ("Q4_d10", "Q7_b6")
CLIENTS = (1, 4, 8, 16)
REPS = 3
WINDOW_S = 15
TIMEOUT_S = 60
SETS = ("A", "B", "C")


def make_requests(workload, q7):
    from queries import Q4_SQL, q4_cypher, Q7_SQL_V1, Q7_SQL_V2, q7_cypher
    reqs = []
    for s in SETS:
        p = case_params(s)
        if workload == "Q4_d10":
            reqs.append((s, Q4_SQL, q4_cypher(10), dict(p, depth=10)))
        else:
            sql = Q7_SQL_V2 if q7 == "v2" else Q7_SQL_V1
            reqs.append((s, sql, q7_cypher(6), dict(p, bound=6, fwd_depth=3, bwd_depth=3)))
    return reqs


def classify(e):
    msg = f"{e.__class__.__name__}: {e}".lower()
    return "timeout" if ("timeout" in msg or "timed out" in msg or "cancel" in msg) else "error"


def client(cid, engine, workload, q7, conn):
    """One client process. Talks to the parent only through its own Pipe (no shared locks,
    which are unreliable on Windows with many processes)."""
    import mm_common
    mm_common._pg = mm_common._neo = None   # never reuse a connection inherited from the parent
    run = (lambda sql, cy, p: mm_common.run_pg(sql, p, timeout_s=TIMEOUT_S)) if engine == "pg" else \
          (lambda sql, cy, p: mm_common.run_neo(cy, p, timeout_s=TIMEOUT_S))
    log = []
    try:
        reqs = make_requests(workload, q7)
        try:
            for s, sql, cy, p in reqs:  # warm-up: A-B-C once (also opens the persistent connection)
                run(sql, cy, p)
            ready = True
        except Exception:
            ready = False
        conn.send(("ready", ready))
        start = conn.recv()             # common start time chosen by the parent (None = abort)
        if start is None or not ready:
            return
        deadline = start + WINDOW_S
        while time.time() < start:      # everyone begins at the same instant
            time.sleep(0.001)
        cycle = 0
        while time.time() < deadline:   # start a new cycle only before the deadline
            cycle += 1
            for s, sql, cy, p in reqs:  # finish the cycle even if the deadline passes meanwhile
                t0 = time.perf_counter()
                wall0 = time.time()
                status, answer = "ok", None
                try:
                    answer = repr(normalize(run(sql, cy, p)))
                except Exception as e:
                    status = classify(e)
                log.append(dict(client=cid, cycle=cycle, set=s, wall_start=wall0, wall_end=time.time(),
                                latency_ms=(time.perf_counter() - t0) * 1000, status=status, answer=answer))
    finally:
        try:
            conn.send(("log", log))     # always report, even after a failure
            conn.close()
        except Exception:
            pass
        mm_common.close_all()


def active_clients(engine):
    """Sample how many sessions are busy, from a separate monitoring connection."""
    import mm_common
    try:
        if engine == "pg":
            return mm_common.run_pg("""SELECT count(*) FROM pg_stat_activity
                                       WHERE datname = current_database() AND state = 'active'
                                       AND pid <> pg_backend_pid()""")[0][0]
        return mm_common.run_neo("SHOW TRANSACTIONS YIELD currentQuery WHERE currentQuery <> '' "
                                 "AND NOT currentQuery STARTS WITH 'SHOW' RETURN count(*)")[0][0]
    except Exception as e:
        return f"n/a ({e.__class__.__name__})"


def expected_answers(engine, workload, q7):
    import mm_common
    exp = {}
    for s, sql, cy, p in make_requests(workload, q7):
        rows = mm_common.run_pg(sql, p) if engine == "pg" else mm_common.run_neo(cy, p)
        exp[s] = repr(normalize(rows))
    return exp


def one_test(engine, workload, n, rep, q7, expected):
    import psutil
    from multiprocessing.connection import wait as mp_wait
    ctx = mp.get_context("spawn")       # same behaviour on Windows, Linux and macOS
    pipes = [ctx.Pipe() for _ in range(n)]
    procs = [ctx.Process(target=client, args=(i, engine, workload, q7, pipes[i][1])) for i in range(n)]
    for p in procs:
        p.start()
    parents = [a for a, b in pipes]
    for a, b in pipes:
        b.close()                       # the parent keeps only its own end
    alive = []
    for c in parents:                   # wait until every client has warmed up and connected
        try:
            if c.poll(600) and c.recv() == ("ready", True):
                alive.append(c)
        except (EOFError, OSError):
            pass
    start = time.time() + 0.5           # common start time, slightly in the future
    for c in parents:
        try:
            c.send(start if c in alive else None)
        except (EOFError, OSError):
            pass
    time.sleep(max(0.0, start - time.time()))
    cpu, active, logs = [], None, []
    psutil.cpu_percent(None)
    last_cpu = time.time()
    waiting = list(alive)
    limit = start + WINDOW_S + 4 * TIMEOUT_S
    while waiting and time.time() < limit:      # clients report when their last cycle ends
        for c in mp_wait(waiting, timeout=1):
            try:
                kind, data = c.recv()
                if kind == "log":
                    logs.append(data)
            except (EOFError, OSError):
                pass
            waiting.remove(c)
        if time.time() - last_cpu >= 1:
            cpu.append(psutil.cpu_percent(None))
            last_cpu = time.time()
        if active is None and time.time() - start > 5:
            active = active_clients(engine)
    lost = n - len(logs)
    for c in parents:
        c.close()
    for p in procs:
        p.join(timeout=10)
        if p.is_alive():
            p.terminate()
            p.join()
    log = [r for l in logs for r in l]
    end = max([r["wall_end"] for r in log] or [time.time()])
    for r in log:                        # correctness checked after timing
        if r["status"] == "ok" and r["answer"] != expected[r["set"]]:
            r["status"] = "wrong"
    ok = sorted(r["latency_ms"] for r in log if r["status"] == "ok")
    p95 = ok[math.ceil(0.95 * len(ok)) - 1] if ok else None
    res = dict(engine=engine, workload=workload, clients=n, rep=rep, start_cat=now_cat(),
               elapsed_s=round(end - start, 3), requests=len(log), correct=len(ok),
               throughput_rps=round(len(ok) / (end - start), 3),
               median_ms=round(statistics.median(ok), 1) if ok else None, p95_ms=round(p95, 1) if p95 else None,
               errors=sum(r["status"] == "error" for r in log) + lost,
               timeouts=sum(r["status"] == "timeout" for r in log),
               wrong=sum(r["status"] == "wrong" for r in log), lost_clients=lost, active_clients_sampled=active,
               cpu_avg_pct=round(statistics.mean(cpu), 1) if cpu else None, cpu_max_pct=max(cpu) if cpu else None)
    print(f"  {engine} {workload} clients={n:>2} rep={rep}: {res['throughput_rps']:8.2f} req/s  "
          f"median {res['median_ms']} ms  p95 {res['p95_ms']} ms  err={res['errors']} to={res['timeouts']} "
          f"wrong={res['wrong']}  active={active}  cpu avg {res['cpu_avg_pct']}%"
          + (f"  LOST CLIENTS={lost}" if lost else ""), flush=True)
    for r in log:
        r.update(engine=engine, workload=workload, clients=n, rep=rep)
        r.pop("answer")
    return res, log


def _append(path, rows):
    if not rows:
        return
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        if new:
            w.writeheader()
        w.writerows(rows)


def run_all(engine, q7, workloads, clients, fresh=False):
    """Results are appended after EVERY repetition, so an interrupted run can be resumed:
    rerunning the same command skips the repetitions already saved. --fresh starts over."""
    import mm_common
    reps_path = config.RESULTS_DIR / f"load_reps_{engine}.csv"
    raw_path = config.RESULTS_DIR / f"load_raw_{engine}.csv"
    if fresh:
        for pth in (reps_path, raw_path):
            pth.unlink(missing_ok=True)
    done = set()
    if reps_path.exists():
        done = {(r["workload"], int(r["clients"]), int(r["rep"])) for r in csv.DictReader(open(reps_path, newline=""))}
    print(f"Load test {engine} started {now_cat()} CAT (Q7 SQL {q7}); already saved: {len(done)} repetitions")
    for w in workloads:
        expected = expected_answers(engine, w, q7)
        mm_common.close_all()
        for n in clients:
            for rep in range(1, REPS + 1):
                if (w, n, rep) in done:
                    print(f"  {engine} {w} clients={n:>2} rep={rep}: already saved - skipped")
                    continue
                s, log = one_test(engine, w, n, rep, q7, expected)
                _append(reps_path, [s])
                _append(raw_path, log)
    print(f"Saved results/load_raw_{engine}.csv and results/load_reps_{engine}.csv")


def summary():
    reps = []
    for p in sorted(config.RESULTS_DIR.glob("load_reps_*.csv")):
        reps += list(csv.DictReader(open(p, newline="")))
    groups = {}
    for r in reps:
        groups.setdefault((r["engine"], r["workload"], int(r["clients"])), []).append(r)
    med = lambda rs, k: statistics.median(float(x[k]) for x in rs if x[k] not in ("", "None"))
    table = []
    print(f"{'engine':6s} {'workload':8s} {'clients':>7} {'thr req/s':>10} {'median ms':>10} {'p95 ms':>9} "
          f"{'errors':>6} {'timeouts':>8} {'cpu avg%':>8}")
    for (e, w, n), rs in sorted(groups.items()):
        row = dict(engine=e, workload=w, clients=n, reps=len(rs), throughput_rps=round(med(rs, "throughput_rps"), 2),
                   median_ms=round(med(rs, "median_ms"), 1), p95_ms=round(med(rs, "p95_ms"), 1),
                   errors=med(rs, "errors"), timeouts=med(rs, "timeouts"), cpu_avg_pct=round(med(rs, "cpu_avg_pct"), 1))
        table.append(row)
        print(f"{e:6s} {w:8s} {n:>7} {row['throughput_rps']:>10} {row['median_ms']:>10} {row['p95_ms']:>9} "
              f"{row['errors']:>6} {row['timeouts']:>8} {row['cpu_avg_pct']:>8}")
    save_json("load_summary.json", table)
    with open(config.RESULTS_DIR / "load_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print("Saved results/load_summary.csv (median of the 3 repetitions)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["pg", "neo"])
    ap.add_argument("--q7", choices=["v1", "v2"], default="v2", help="SQL version selected in Section 6")
    ap.add_argument("--workload", choices=WORKLOADS)
    ap.add_argument("--clients", type=int, nargs="*")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="delete this engine's saved load results first")
    a = ap.parse_args()
    if a.summary:
        return summary()
    if not a.engine:
        ap.error("--engine pg|neo required")
    run_all(a.engine, a.q7, [a.workload] if a.workload else WORKLOADS, a.clients or CLIENTS, a.fresh)


if __name__ == "__main__":
    mp.freeze_support()
    main()
