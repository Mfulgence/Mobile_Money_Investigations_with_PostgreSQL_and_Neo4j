"""Section 3.2 steps 1-2 - prepare_import.py

Makes TEMPORARY import copies of the captured CSVs with Neo4j typed headers (the source
CSVs in data/ are never modified), derives owns.csv in (customer_id, account_id) order,
and writes the exact neo4j-admin command for Windows (.bat) and Linux/macOS (.sh).

    python step05_neo4j_prepare_import.py
Then stop Neo4j and run neo4j/import_full.bat (Windows) or neo4j/import_full.sh.
"""
import csv
import hashlib
import shutil
import time

import config
from mm_common import save_json

SRC, DST = config.DATA_DIR, config.IMPORT_DIR

# source file -> (import file, typed header). Customer, Account and Device are separate ID groups.
HEADERS = {
    "customers.csv":       ("customers.csv",       "customer_id:ID(Customer),region:string"),
    "accounts.csv":        ("accounts.csv",        "account_id:ID(Account),:IGNORE,role:string"),
    "devices.csv":         ("devices.csv",         "device_id:ID(Device),access_type:string"),
    "account_devices.csv": ("used_device.csv",     ":START_ID(Account),:END_ID(Device),first_day:int,last_day:int,observations:int"),
    "transfers.csv":       ("transfers.csv",       "transfer_id:long,:START_ID(Account),:END_ID(Account),occurred_at:long,amount_rwf:int"),
}
OWNS_HEADER = ":START_ID(Customer),:END_ID(Account)"


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def typed_copy(src_name, dst_name, header):
    """Replace only the first (header) line; stream the remaining bytes unchanged."""
    src, dst = SRC / src_name, DST / dst_name
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        old = fin.readline().decode().strip()
        fout.write((header + "\n").encode())
        shutil.copyfileobj(fin, fout, 1 << 24)
    print(f"  {src_name:20s} -> {dst_name:16s}  '{old}'  =>  '{header}'")


def derive_owns():
    """Ownership fact from accounts.csv, sorted by customer_id then account_id."""
    with open(SRC / "accounts.csv", newline="") as f:
        pairs = sorted((int(r["customer_id"]), int(r["account_id"])) for r in csv.DictReader(f))
    with open(DST / "owns.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(OWNS_HEADER.split(","))
        w.writerows(pairs)
    print(f"  accounts.csv          -> owns.csv          {len(pairs):,} rows, header '{OWNS_HEADER}'")
    return len(pairs)


def write_commands():
    files = dict(c=DST / "customers.csv", a=DST / "accounts.csv", d=DST / "devices.csv",
                 o=DST / "owns.csv", u=DST / "used_device.csv", t=DST / "transfers.csv")
    opts = [
        "--overwrite-destination=true",
        "--id-type=integer",
        f'--nodes=Customer="{files["c"]}"',
        f'--nodes=Account="{files["a"]}"',
        f'--nodes=Device="{files["d"]}"',
        f'--relationships=OWNS="{files["o"]}"',
        f'--relationships=USED_DEVICE="{files["u"]}"',
        f'--relationships=TRANSFER="{files["t"]}"',
        "--report-file=import.report",
    ]
    home = config.NEO4J_HOME
    bat = ["@echo off", "REM Neo4j must be STOPPED:  bin\\neo4j.bat stop   (or stop the Windows service)",
           f'cd /d "{home}"', "echo Import started %date% %time%",
           "bin\\neo4j-admin.bat database import full neo4j ^"]
    bat += [f"  {o} ^" for o in opts[:-1]] + [f"  {opts[-1]}", "echo Import finished %date% %time%"]
    sh = ["#!/usr/bin/env bash", "# Neo4j must be STOPPED: bin/neo4j stop", "set -e", f'cd "{home}"', "date",
          "time bin/neo4j-admin database import full neo4j \\"]
    sh += [f"  {o} \\" for o in opts[:-1]] + [f"  {opts[-1]}", "date"]
    (config.ROOT / "neo4j" / "import_full.bat").write_text("\r\n".join(bat) + "\r\n")
    (config.ROOT / "neo4j" / "import_full.sh").write_text("\n".join(sh) + "\n")
    print("\nImport command written to neo4j/import_full.bat and neo4j/import_full.sh:\n")
    print("\n".join(sh[5:]))


def main():
    DST.mkdir(parents=True, exist_ok=True)
    before = {n: md5(SRC / n) for n in HEADERS}
    t0 = time.perf_counter()
    print(f"Typed import copies in {DST}:")
    for src_name, (dst_name, header) in HEADERS.items():
        typed_copy(src_name, dst_name, header)
    owns = derive_owns()
    seconds = time.perf_counter() - t0
    after = {n: md5(SRC / n) for n in HEADERS}
    unchanged = before == after
    print(f"\nSource CSVs unchanged (MD5 before == after): {unchanged}")
    print(f"Preparation took {seconds:.1f} s")
    write_commands()
    save_json("neo4j_prepare_import.json", dict(seconds=round(seconds, 1), owns_rows=owns,
                                                source_unchanged=unchanged, source_md5=after))


if __name__ == "__main__":
    main()
