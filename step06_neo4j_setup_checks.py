"""Section 3.2 steps 3-4 - after the import: constraints + range index, wait until online,
store/transaction-log sizes, then all graph checks against capture.py.

    python step06_neo4j_setup_checks.py            # setup + checks
    python step06_neo4j_setup_checks.py --checks   # checks only
    python step06_neo4j_setup_checks.py --cleanup  # delete the temporary typed import copies
"""
import argparse
import shutil
import time
from pathlib import Path

import config
import mobile_money_generator as g
from mm_common import run_neo, load_json, save_json, cat_time

SETUP = [
    "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
    "CREATE CONSTRAINT account_id_unique  IF NOT EXISTS FOR (a:Account)  REQUIRE a.account_id  IS UNIQUE",
    "CREATE CONSTRAINT device_id_unique   IF NOT EXISTS FOR (d:Device)   REQUIRE d.device_id   IS UNIQUE",
    "CREATE RANGE INDEX transfer_occurred_at IF NOT EXISTS FOR ()-[t:TRANSFER]-() ON (t.occurred_at)",
]


def folder_bytes(p: Path):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else None


def setup():
    t0 = time.perf_counter()
    for q in SETUP:
        run_neo(q)
        print("  ran:", q)
    run_neo("CALL db.awaitIndexes(3600)")
    seconds = time.perf_counter() - t0
    print(f"Constraint/index setup (incl. waiting until ONLINE): {seconds:.1f} s")
    return seconds


def show_schema():
    print("\n=== Constraints ===")
    cons = run_neo("SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN name, type, labelsOrTypes, properties")
    for c in cons:
        print("  ", c)
    print("\n=== Indexes ===")
    idx = run_neo("SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, state, populationPercent "
                  "RETURN name, type, entityType, labelsOrTypes, properties, state, populationPercent")
    for i in idx:
        print("  ", i)
    return cons, idx


def sizes():
    home = config.NEO4J_HOME
    store = folder_bytes(home / "data" / "databases" / "neo4j")
    txlog = folder_bytes(home / "data" / "transactions" / "neo4j")
    print("\n=== Store sizes (GB = 1e9 bytes) ===")
    if store is None:
        print(f"  NEO4J_HOME not found ({home}); set it in config_local.py to measure folder sizes")
    else:
        print(f"  store (data/databases/neo4j)          {store / 1e9:.3f} GB")
        print(f"  transaction logs (data/transactions)  {txlog / 1e9:.3f} GB")
    return dict(store_gb=store and round(store / 1e9, 3), txlog_gb=txlog and round(txlog / 1e9, 3))


def checks():
    exp = g.dataset_info()["expected_counts"]
    audit = load_json("capture_audit.json")["transfer_audit"]
    rows, ok_all = [], True

    def check(label, got, want):
        nonlocal ok_all
        ok = got == want
        ok_all &= ok
        print(f"{'OK ' if ok else 'BAD'} {label:44s} got={got!s:>16}  expected={want!s:>16}")
        rows.append(dict(check=label, got=got, expected=want, ok=ok))

    print("\n=== Node and relationship counts ===")
    for label, key in (("Customer", "customers"), ("Account", "accounts"), ("Device", "devices")):
        check(f"(:{label}) nodes", run_neo(f"MATCH (n:{label}) RETURN count(n)")[0][0], exp[key])
    for rel, want in (("OWNS", 248_000), ("USED_DEVICE", 285_600), ("TRANSFER", 20_003_300)):
        check(f"[:{rel}] relationships", run_neo(f"MATCH ()-[r:{rel}]->() RETURN count(r)")[0][0], want)
    check("all nodes", run_neo("MATCH (n) RETURN count(n)")[0][0], 704_600)
    check("all relationships", run_neo("MATCH ()-[r]->() RETURN count(r)")[0][0], 20_536_900)

    print("\n=== Account roles and ownership ===")
    roles = dict(run_neo("MATCH (a:Account) RETURN a.role, count(*)"))
    for r, n in (("person", 240_000), ("merchant", 6_000), ("agent", 2_000)):
        check(f"{r} accounts", roles.get(r), n)
    bad = run_neo("""MATCH (a:Account) WITH a, COUNT { (:Customer)-[:OWNS]->(a) } AS owners
                     WHERE owners <> 1 RETURN count(a)""")[0][0]
    check("accounts without exactly one owner", bad, 0)

    print("\n=== TRANSFER properties vs capture audit ===")
    n, distinct = run_neo("MATCH ()-[t:TRANSFER]->() RETURN count(t), count(DISTINCT t.transfer_id)")[0]
    check("distinct transfer_id = transfer count", distinct, n)
    c, lo, hi, s = run_neo("""MATCH ()-[t:TRANSFER]->()
                              RETURN count(t), min(t.occurred_at), max(t.occurred_at), sum(t.amount_rwf)""")[0]
    check("transfer count", c, audit["count"])
    check("earliest occurred_at", lo, audit["earliest"])
    check("latest occurred_at", hi, audit["latest"])
    check("sum amount_rwf", s, audit["sum_amount_rwf"])
    print(f"    earliest {cat_time(lo)}   latest {cat_time(hi)}")
    types = run_neo("""MATCH (a:Account {account_id: 998})-[t:TRANSFER]->() WITH a, t LIMIT 1
                       RETURN valueType(a.account_id), valueType(t.occurred_at), valueType(t.amount_rwf)""")
    print("    property types sample:", types)
    print("\nALL CHECKS PASSED" if ok_all else "\nSOME CHECKS FAILED")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks", action="store_true")
    ap.add_argument("--cleanup", action="store_true")
    a = ap.parse_args()
    if a.cleanup:
        shutil.rmtree(config.IMPORT_DIR, ignore_errors=True)
        print("Removed temporary import copies:", config.IMPORT_DIR, "exists now?", config.IMPORT_DIR.exists())
        return
    comp = run_neo("CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition")
    print("Neo4j:", comp)
    out = dict(components=comp)
    if not a.checks:
        out["setup_seconds"] = round(setup(), 1)
    out["constraints"], out["indexes"] = show_schema()
    out["sizes"] = sizes()
    out["checks"] = checks()
    save_json("neo4j_checks.json", out)


if __name__ == "__main__":
    main()
