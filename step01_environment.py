"""Section 1.1 - record software/driver versions, CPU, RAM, OS and database memory settings,
and prove both connections work. Run with both database services started.
    python step01_environment.py            (both)      --pg / --neo  (only one)
"""
import argparse
import os
import platform
import sys

import config
from mm_common import save_json, now_cat


def machine():
    info = dict(os=platform.platform(), machine=platform.machine(),
                cpu=platform.processor() or platform.machine(), logical_cpus=os.cpu_count(),
                python=sys.version.split()[0])
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 2)
        info["physical_cores"] = psutil.cpu_count(logical=False)
    except ImportError:
        info["ram_gb"] = "install psutil to record RAM"
    if platform.system() == "Windows":
        try:
            import subprocess
            name = subprocess.run(["powershell", "-NoProfile", "-Command",
                                   "(Get-CimInstance Win32_Processor).Name"],
                                  capture_output=True, text=True, timeout=20).stdout.strip()
            if name:
                info["cpu"] = name
        except Exception:
            pass
    for mod in ("numpy", "psycopg", "neo4j", "matplotlib", "pandas"):
        try:
            info[f"{mod}_version"] = __import__(mod).__version__
        except Exception as e:
            info[f"{mod}_version"] = f"not installed ({e.__class__.__name__})"
    return info


def postgres():
    from mm_common import run_pg
    out = dict(version=run_pg("SELECT version()")[0][0],
               database=run_pg("SELECT current_database(), current_user")[0],
               connected_at=str(run_pg("SELECT now()")[0][0]))
    names = ("shared_buffers", "effective_cache_size", "work_mem", "maintenance_work_mem",
             "max_wal_size", "max_parallel_workers_per_gather", "jit", "TimeZone", "statement_timeout")
    out["settings"] = {n: run_pg(f"SHOW {n}")[0][0] for n in names}
    out["db_timezone_setting"] = run_pg("""SELECT setconfig FROM pg_db_role_setting s
                                           JOIN pg_database d ON d.oid = s.setdatabase
                                           WHERE d.datname = current_database()""")
    return out


def neo4j():
    from mm_common import run_neo
    out = dict(components=run_neo("CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition"),
               databases=run_neo("SHOW DATABASES YIELD name, currentStatus, default RETURN name, currentStatus, default"))
    try:
        rows = run_neo("""SHOW SETTINGS YIELD name, value
                          WHERE name STARTS WITH 'server.memory' OR name = 'db.transaction.timeout'
                          RETURN name, value ORDER BY name""")
    except Exception:
        rows = run_neo("""CALL dbms.listConfig() YIELD name, value
                          WHERE name STARTS WITH 'server.memory' RETURN name, value ORDER BY name""")
    out["memory_settings"] = {r[0]: r[1] for r in rows}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pg", action="store_true")
    ap.add_argument("--neo", action="store_true")
    a = ap.parse_args()
    both = not (a.pg or a.neo)
    env = dict(recorded_at_cat=now_cat(), machine=machine())
    if both or a.pg:
        env["postgresql"] = postgres()
    if both or a.neo:
        env["neo4j"] = neo4j()
    import json
    print(json.dumps(env, indent=2, default=str))
    print("\nConnections OK. Saved", save_json("environment.json", env))


if __name__ == "__main__":
    main()
