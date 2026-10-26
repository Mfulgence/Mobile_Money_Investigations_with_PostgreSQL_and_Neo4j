"""Section 3.3 - trace one loaded account to its owner, a device and an outgoing transfer
with SQL JOINs and with Cypher MATCH, and show both records side by side.
    python step07_inspect_account.py [account_id]     (default 998)
"""
import sys

from queries import INSPECT_SQL, INSPECT_CYPHER
from mm_common import run_pg, run_neo, save_json

FIELDS = ["account_id", "role", "customer_id", "region", "device_id", "access_type", "first_day",
          "last_day", "observations", "transfer_id", "receiver_id", "occurred_at", "occurred_cat", "amount_rwf"]

account = int(sys.argv[1]) if len(sys.argv) > 1 else 998
out = {"account": account}
print("SQL:\n" + INSPECT_SQL)
sql = run_pg(INSPECT_SQL, dict(account=account))[0]
out["sql"] = dict(zip(FIELDS, map(str, sql)))
try:
    print("Cypher:\n" + INSPECT_CYPHER)
    cy = run_neo(INSPECT_CYPHER, dict(account=account))[0]
    out["cypher"] = dict(zip(FIELDS, map(str, cy)))
except Exception as e:
    print("Neo4j not reachable:", e)
    cy = [None] * len(FIELDS)

print(f"{'field':14s} {'PostgreSQL':32s} {'Neo4j':32s} same")
for i, f in enumerate(FIELDS):
    a, b = sql[i], cy[i]
    same = "-" if f == "occurred_cat" else (str(a) == str(b))
    print(f"{f:14s} {str(a):32s} {str(b):32s} {same}")
save_json("inspect_account.json", out)
