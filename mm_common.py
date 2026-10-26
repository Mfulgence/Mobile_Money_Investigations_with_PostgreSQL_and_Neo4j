"""Shared helpers: case sets, CAT hour boundaries, persistent connections,
run_pg / run_neo wrappers and result normalisation."""
import datetime as dt
import decimal
import json
import time
from zoneinfo import ZoneInfo   # on Windows: pip install tzdata

import config

CAT = ZoneInfo("Africa/Kigali")

# Section 4 case table: set -> (review account, destination, September day)
CASES = {
    "A": (998, 24755, 6),
    "B": (147228, 186823, 13),
    "C": (206978, 6573, 8),
    "D": (237998, 21755, 6),
    "E": (144228, 183823, 13),
    "F": (203978, 3573, 8),
}
Q4_DEPTHS = (4, 6, 8, 10)
Q7_BOUNDS = (4, 6)
MONTH_START = int(dt.datetime(2026, 9, 1, tzinfo=CAT).timestamp())   # 1788213600
MONTH_END = int(dt.datetime(2026, 10, 1, tzinfo=CAT).timestamp())


def hour_bounds(day):
    """09:45:00 inclusive to 10:45:00 exclusive, CAT, on September <day>, as epoch seconds."""
    start = dt.datetime(2026, 9, day, 9, 45, 0, tzinfo=CAT)
    end = dt.datetime(2026, 9, day, 10, 45, 0, tzinfo=CAT)
    return int(start.timestamp()), int(end.timestamp())


def case_params(s):
    account, destination, day = CASES[s]
    start, end = hour_bounds(day)
    return dict(account=account, destination=destination, start=start, end=end)


def cat_time(epoch):
    return dt.datetime.fromtimestamp(epoch, CAT).strftime("%Y-%m-%d %H:%M:%S CAT")


def now_cat():
    return dt.datetime.now(CAT).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- connections
_pg = None
_neo = None


def pg_conn():
    global _pg
    if _pg is None or _pg.closed:
        import psycopg
        _pg = psycopg.connect(**config.PG, autocommit=True)
        _pg.execute("SET TIME ZONE 'Africa/Kigali'")
        _pg.execute("SET statement_timeout = '180s'")
    return _pg


def neo_driver():
    global _neo
    if _neo is None:
        from neo4j import GraphDatabase
        _neo = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        _neo.verify_connectivity()
    return _neo


def run_pg(query, params=None, timeout_s=None):
    """Execute SQL with psycopg %(name)s parameters and return every row."""
    conn = pg_conn()
    if timeout_s is not None:
        conn.execute(f"SET statement_timeout = '{int(timeout_s)}s'")
    with conn.cursor() as cur:
        cur.execute(query, params or {})
        return cur.fetchall() if cur.description else []


def run_neo(query, params=None, timeout_s=None):
    """Execute Cypher with $name parameters and return every row (list of value lists)."""
    from neo4j import Query
    q = Query(query, timeout=timeout_s) if timeout_s else query
    with neo_driver().session(database=config.NEO4J_DATABASE) as s:
        result = s.run(q, params or {})
        return [list(r.values()) for r in result]


def close_all():
    global _pg, _neo
    if _pg is not None:
        _pg.close(); _pg = None
    if _neo is not None:
        _neo.close(); _neo = None


# ---------------------------------------------------------------- normalisation
def _norm(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, decimal.Decimal)):
        return int(v)
    if isinstance(v, float):
        return int(v) if v.is_integer() else round(v, 6)
    if isinstance(v, (list, tuple)):
        return tuple(_norm(x) for x in v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if hasattr(v, "iso_format"):          # neo4j.time.Date / DateTime
        return v.iso_format()
    return v


def normalize(rows):
    """Integers as int, sequences as tuples, dates as ISO text; rows sorted for exact comparison."""
    out = [tuple(_norm(x) for x in r) for r in rows]
    try:
        return sorted(out)            # natural order: numbers numerically, text alphabetically
    except TypeError:                 # e.g. a None length mixed with numbers
        return sorted(out, key=repr)


def save_json(name, obj):
    path = config.RESULTS_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return path


def load_json(name):
    return json.loads((config.RESULTS_DIR / name).read_text(encoding="utf-8"))


class Stopwatch:
    def __enter__(self):
        self.t0 = time.perf_counter(); return self

    def __exit__(self, *a):
        self.seconds = time.perf_counter() - self.t0
