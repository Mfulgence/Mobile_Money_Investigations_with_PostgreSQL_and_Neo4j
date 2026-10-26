"""Section 2.2 step 3 - PostgreSQL checks: row counts, audit totals, roles,
validated constraints, indexes and data/index sizes (1 GB = 1,000,000,000 bytes)."""
import mobile_money_generator as g
from mm_common import run_pg, load_json, save_json, cat_time

audit = load_json("capture_audit.json")["transfer_audit"]
expected = g.dataset_info()["expected_counts"]
out = {}
ok_all = True


def check(label, got, want):
    global ok_all
    ok = got == want
    ok_all &= ok
    print(f"{'OK ' if ok else 'BAD'} {label:42s} got={got!s:>22}  expected={want!s:>22}")
    return dict(check=label, got=got, expected=want, ok=ok)


print("=== Row counts ===")
out["counts"] = [check(f"rows in {t}", run_pg(f"SELECT count(*) FROM {t}")[0][0], n) for t, n in expected.items()]

print("\n=== Transfer audit totals vs capture.py ===")
cnt, lo, hi, total = run_pg("SELECT count(*), min(occurred_at), max(occurred_at), sum(amount_rwf) FROM transfers")[0]
out["audit"] = [
    check("transfer count", cnt, audit["count"]),
    check("earliest occurred_at", lo, audit["earliest"]),
    check("latest occurred_at", hi, audit["latest"]),
    check("sum amount_rwf", int(total), audit["sum_amount_rwf"]),
]
print(f"    earliest {cat_time(lo)}  latest {cat_time(hi)}")
print("    in SQL:", run_pg("SELECT to_timestamp(min(occurred_at)), to_timestamp(max(occurred_at)) FROM transfers")[0])

print("\n=== Account roles ===")
roles = dict(run_pg("SELECT role, count(*) FROM accounts GROUP BY role ORDER BY role"))
out["roles"] = [check(f"{r} accounts", roles.get(r), n) for r, n in
                (("person", 240_000), ("merchant", 6_000), ("agent", 2_000))]

print("\n=== Constraints (convalidated must be true) ===")
cons = run_pg("""
    SELECT conrelid::regclass::text AS tbl, conname,
           CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'c' THEN 'CHECK' WHEN 'n' THEN 'NOT NULL' ELSE contype::text END,
           convalidated, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE connamespace = 'public'::regnamespace
    ORDER BY 1, 3, 2""")
for c in cons:
    print(f"  {c[0]:16s} {c[1]:26s} {c[2]:12s} validated={c[3]}  {c[4]}")
ok_all &= all(c[3] for c in cons)
out["constraints"] = cons
nn = run_pg("""SELECT count(*) FILTER (WHERE is_nullable='NO'), count(*) FROM information_schema.columns
               WHERE table_schema='public'""")[0]
out["not_null"] = check("NOT NULL columns / all columns", nn[0], nn[1])

print("\n=== Indexes ===")
idx = run_pg("""SELECT tablename, indexname, indexdef FROM pg_indexes
                WHERE schemaname='public' ORDER BY tablename, indexname""")
for i in idx:
    print(f"  {i[0]:16s} {i[1]:30s} {i[2].split(' USING ')[1]}")
out["indexes"] = idx

print("\n=== Sizes (GB = 1e9 bytes) ===")
sizes = run_pg("""
    SELECT c.relname, pg_table_size(c.oid), pg_indexes_size(c.oid), pg_total_relation_size(c.oid)
    FROM pg_class c WHERE c.relnamespace='public'::regnamespace AND c.relkind='r' ORDER BY 4 DESC""")
print(f"  {'table':16s} {'data GB':>9s} {'index GB':>9s} {'total GB':>9s}")
for name, d, i, t in sizes:
    print(f"  {name:16s} {d/1e9:9.3f} {i/1e9:9.3f} {t/1e9:9.3f}")
d, i = sum(s[1] for s in sizes), sum(s[2] for s in sizes)
db = run_pg("SELECT pg_database_size(current_database())")[0][0]
print(f"  {'ALL TABLES':16s} {d/1e9:9.3f} {i/1e9:9.3f} {(d+i)/1e9:9.3f}   database on disk {db/1e9:.3f} GB")
out["sizes"] = dict(tables=sizes, data_gb=round(d / 1e9, 3), index_gb=round(i / 1e9, 3), database_gb=round(db / 1e9, 3))

print("\nALL CHECKS PASSED" if ok_all else "\nSOME CHECKS FAILED")
save_json("pg_checks.json", out)
