"""Section 6.1 step 2 - independent checks against the captured CSV rows in plain Python
(no database involved): one device overlap from Q3 and one chain (Q5) / cycle (Q6).

    python step09b_independent_check.py
Streams the CSVs (never loads transfers.csv into memory).
"""
import csv

import config
from mm_common import case_params, cat_time, save_json, load_json

out = {}

# ---------- 1. Device overlap: set A account 998 and every account sharing its devices
acct = case_params("A")["account"]
rows = list(csv.DictReader(open(config.DATA_DIR / "account_devices.csv", newline="")))
mine = [r for r in rows if int(r["account_id"]) == acct]
dev_type = {}
mine_devices = {int(r["device_id"]) for r in mine}
for r in csv.DictReader(open(config.DATA_DIR / "devices.csv", newline="")):
    if int(r["device_id"]) in mine_devices:
        dev_type[int(r["device_id"])] = r["access_type"]
overlaps = []
for m in mine:
    for o in rows:
        if o["device_id"] == m["device_id"] and o["account_id"] != m["account_id"]:
            s = max(int(m["first_day"]), int(o["first_day"]))
            e = min(int(m["last_day"]), int(o["last_day"]))
            if s <= e:
                overlaps.append((int(o["account_id"]), int(o["device_id"]), dev_type[int(o["device_id"])], s, e))
overlaps.sort()
print(f"CSV rows for account {acct} in account_devices.csv:")
for m in mine:
    print("   ", dict(m))
print(f"Overlaps computed from CSV ({len(overlaps)}):")
for o in overlaps:
    print("   ", o)
out["device_overlap"] = overlaps

# ---------- 2. Chain and cycle from transfers.csv (stream; keep only the review account's hour)
p = case_params("A")
wanted_hour = {}
for r in csv.DictReader(open(config.DATA_DIR / "transfers.csv", newline="")):
    ts = int(r["occurred_at"])
    if p["start"] <= ts < p["end"] + 1800:
        wanted_hour[int(r["transfer_id"])] = (int(r["sender_id"]), int(r["receiver_id"]), ts, int(r["amount_rwf"]))
print(f"\nTransfers between {cat_time(p['start'])} and the hour end + 30 min: {len(wanted_hour):,}")
by_sender = {}
for tid, (s, rcv, ts, amt) in wanted_hour.items():
    by_sender.setdefault(s, []).append((tid, rcv, ts, amt))


def ok_amount(prev, nxt):
    return 90 * prev <= 100 * nxt <= 105 * prev


chains = []
for t1, b, ts1, a1 in by_sender.get(acct, []):
    if not ts1 < p["end"]:
        continue
    for t2, c, ts2, a2 in by_sender.get(b, []):
        if ts1 < ts2 <= ts1 + 600 and ok_amount(a1, a2):
            for t3, d, ts3, a3 in by_sender.get(c, []):
                if ts2 < ts3 <= ts2 + 600 and ok_amount(a2, a3) and len({acct, b, c, d}) == 4:
                    chains.append((t1, t2, t3, d))
print("Q5 chains found in CSV:", sorted(chains))

cycles = []


def extend(path, cur, first, last, amt):
    if len(path) >= 8:
        return
    for tid, nxt, ts, a in by_sender.get(cur, []):
        if last < ts < p["end"] and ts - first <= 1800 and ok_amount(amt, a):
            if nxt == acct:
                if len(path) + 1 >= 3:
                    cycles.append(tuple(path + [tid]))
            else:
                extend(path + [tid], nxt, first, ts, a)


for tid, nxt, ts, a in by_sender.get(acct, []):
    if ts < p["end"] and nxt != acct:
        extend([tid], nxt, ts, ts, a)
print("Q6 cycles found in CSV:", sorted(cycles))
for tid in (sorted(cycles)[0] if cycles else []):
    s, rcv, ts, amt = wanted_hour[tid]
    print(f"    t{tid}: {s} -> {rcv}  {cat_time(ts)}  {amt:,} RWF")
out["q5_chains"] = sorted(chains)
out["q6_cycles"] = sorted(cycles)

# ---------- 3. Compare with the stored database answers (if step08 has been run)
for engine in ("pg", "neo"):
    try:
        res = load_json(f"outputs_{engine}.json")["cases"]
    except FileNotFoundError:
        continue
    db_q3 = [tuple(x) for x in res["Q3-A"]["rows"]]
    db_q5 = [tuple(x) for x in res["Q5-A"]["rows"]]
    db_q6 = [tuple(x[0]) for x in res["Q6-A"]["rows"]]
    print(f"\n{engine}: Q3-A equal to CSV check: {sorted(db_q3) == overlaps};  "
          f"Q5-A equal: {sorted(db_q5) == sorted(chains)};  Q6-A equal: {sorted(db_q6) == sorted(cycles)}")
    out[f"agrees_with_{engine}"] = dict(q3=sorted(db_q3) == overlaps, q5=sorted(db_q5) == sorted(chains),
                                        q6=sorted(db_q6) == sorted(cycles))
save_json("independent_check.json", out)
