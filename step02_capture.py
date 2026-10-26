"""Section 1.2 - capture.py: preview each stream, then write all five CSVs progressively.

Usage:
    python step02_capture.py --preview     # dataset_info, FIELDS and 10 records per stream
    python step02_capture.py               # preview + full capture of the five streams
Never holds a full stream in memory: rows go straight from the generator to csv.DictWriter.
"""
import argparse
import csv
import json
import time
from itertools import islice
from pprint import pprint

import mobile_money_generator as g
import config
from mm_common import cat_time, save_json, now_cat

STREAMS = {
    "customers": g.iter_customers,
    "accounts": g.iter_accounts,
    "devices": g.iter_devices,
    "account_devices": g.iter_account_devices,
    "transfers": g.iter_transfers,
}


def preview():
    print("dataset_info():")
    pprint(g.dataset_info(), sort_dicts=False)
    print("\nFIELDS:")
    pprint(g.FIELDS, sort_dicts=False)
    for name, fn in STREAMS.items():
        print(f"\n--- first 10 records of iter_{name}() ---")
        for row in islice(fn(), 10):      # a fresh iterator call restarts the stream
            print(row)


def capture_stream(name, fn, expected):
    path = config.DATA_DIR / f"{name}.csv"
    consumed = written = 0
    audit = {}
    if name == "transfers":
        audit = dict(count=0, earliest=None, latest=None, sum_amount_rwf=0)
    t0 = time.perf_counter()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=g.FIELDS[name])
        writer.writeheader()
        for row in fn():
            consumed += 1
            writer.writerow(row)
            written += 1
            if name == "transfers":
                ts = row["occurred_at"]
                audit["count"] += 1
                audit["sum_amount_rwf"] += row["amount_rwf"]
                if audit["earliest"] is None or ts < audit["earliest"]:
                    audit["earliest"] = ts
                if audit["latest"] is None or ts > audit["latest"]:
                    audit["latest"] = ts
                if consumed % 1_000_000 == 0:
                    print(f"  [{now_cat()}] transfers: {consumed:,} written "
                          f"({time.perf_counter() - t0:,.0f} s)", flush=True)
    seconds = time.perf_counter() - t0
    size = path.stat().st_size
    status = "OK" if consumed == written == expected else "MISMATCH"
    print(f"{name:16s} consumed={consumed:>12,} written={written:>12,} expected={expected:>12,} "
          f"{status}  {seconds:8.1f} s  {size / 1e9:.3f} GB")
    return dict(stream=name, file=str(path), consumed=consumed, written=written, expected=expected,
                status=status, seconds=round(seconds, 2), bytes=size, gb=round(size / 1e9, 4), **audit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="only show the preview")
    args = ap.parse_args()
    preview()
    if args.preview:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    expected = g.dataset_info()["expected_counts"]
    print(f"\n=== Capture started {now_cat()} CAT into {config.DATA_DIR} ===")
    t0 = time.perf_counter()
    results = [capture_stream(n, fn, expected[n]) for n, fn in STREAMS.items()]
    total = time.perf_counter() - t0
    tr = results[-1]
    summary = dict(
        finished_cat=now_cat(),
        total_seconds=round(total, 1),
        total_records=sum(r["written"] for r in results),
        total_gb=round(sum(r["bytes"] for r in results) / 1e9, 4),
        transfer_audit=dict(count=tr["count"], earliest=tr["earliest"], earliest_cat=cat_time(tr["earliest"]),
                            latest=tr["latest"], latest_cat=cat_time(tr["latest"]),
                            sum_amount_rwf=tr["sum_amount_rwf"]),
        streams=results,
    )
    print("\n=== Five-stream totals ===")
    print(f"records written : {summary['total_records']:,} (expected 20,993,500)")
    print(f"CSV size        : {summary['total_gb']} GB   capture time: {summary['total_seconds']} s")
    print("transfer audit  :", json.dumps(summary["transfer_audit"], indent=2))
    print("saved", save_json("capture_audit.json", summary))


if __name__ == "__main__":
    main()
