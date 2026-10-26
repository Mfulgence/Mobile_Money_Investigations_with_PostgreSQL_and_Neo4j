"""All SQL / Cypher query pairs for Q1-Q7 (Sections 4-6) and the 61 comparison cases.

SQL placeholders are psycopg %(name)s parameters; Cypher uses $name.
Depth/bound numbers inside variable-length Cypher patterns cannot be parameters,
so q4/q6/q7 builders insert the validated integer into the query text.
"""
import math
from mm_common import CASES, Q4_DEPTHS, Q7_BOUNDS, case_params, MONTH_START, MONTH_END

# --------------------------------------------------------------------------- Q1
Q1_SQL = """
SELECT COUNT(*) AS transfers, COALESCE(SUM(amount_rwf), 0) AS total_rwf
FROM transfers
WHERE sender_id = %(account)s
  AND occurred_at >= %(start)s AND occurred_at < %(end)s
"""
Q1_CYPHER = """
MATCH (a:Account {account_id: $account})
OPTIONAL MATCH (a)-[t:TRANSFER]->()
WHERE t.occurred_at >= $start AND t.occurred_at < $end
RETURN count(t) AS transfers, coalesce(sum(t.amount_rwf), 0) AS total_rwf
"""

# --------------------------------------------------------------------------- Q2
Q2_SQL = """
SELECT (to_timestamp(occurred_at) AT TIME ZONE 'Africa/Kigali')::date AS day,
       COUNT(*) AS transfers, SUM(amount_rwf) AS total_rwf
FROM transfers
GROUP BY 1
ORDER BY 1
"""
Q2_CYPHER = """
MATCH ()-[t:TRANSFER]->()
WITH date(datetime({epochSeconds: t.occurred_at, timezone: 'Africa/Kigali'})) AS day, t.amount_rwf AS amount
RETURN day, count(*) AS transfers, sum(amount) AS total_rwf
ORDER BY day
"""

# --------------------------------------------------------------------------- Q3
Q3_SQL = """
SELECT o.account_id, o.device_id, d.access_type,
       GREATEST(r.first_day, o.first_day) AS overlap_start,
       LEAST(r.last_day, o.last_day)       AS overlap_end
FROM account_devices r
JOIN account_devices o ON o.device_id = r.device_id AND o.account_id <> r.account_id
JOIN devices d         ON d.device_id = r.device_id
WHERE r.account_id = %(account)s
  AND GREATEST(r.first_day, o.first_day) <= LEAST(r.last_day, o.last_day)
ORDER BY o.account_id, o.device_id
"""
Q3_CYPHER = """
MATCH (a:Account {account_id: $account})-[r1:USED_DEVICE]->(d:Device)<-[r2:USED_DEVICE]-(o:Account)
WHERE o <> a
WITH o, d,
     CASE WHEN r1.first_day >= r2.first_day THEN r1.first_day ELSE r2.first_day END AS overlap_start,
     CASE WHEN r1.last_day  <= r2.last_day  THEN r1.last_day  ELSE r2.last_day  END AS overlap_end
WHERE overlap_start <= overlap_end
RETURN o.account_id AS account_id, d.device_id AS device_id, d.access_type AS access_type,
       overlap_start, overlap_end
ORDER BY account_id, device_id
"""

# --------------------------------------------------------------------------- Q4
Q4_SQL = """
WITH RECURSIVE edges(sk, si, dk, di) AS (
    SELECT 'Customer'::text, customer_id, 'Account'::text,  account_id  FROM accounts         -- OWNS forward
    UNION ALL
    SELECT 'Account'::text,  account_id,  'Customer'::text, customer_id FROM accounts         -- OWNS backward
    UNION ALL
    SELECT 'Account'::text,  account_id,  'Device'::text,   device_id   FROM account_devices  -- USED_DEVICE forward
    UNION ALL
    SELECT 'Device'::text,   device_id,   'Account'::text,  account_id  FROM account_devices  -- USED_DEVICE backward
), walk(kind, id, depth) AS (
    SELECT 'Account'::text, %(account)s::integer, 0
    UNION
    SELECT e.dk, e.di, w.depth + 1
    FROM walk w
    JOIN edges e ON e.sk = w.kind AND e.si = w.id
    WHERE w.depth < %(depth)s
)
SELECT c.region, COUNT(*) AS accounts
FROM (SELECT DISTINCT id FROM walk WHERE kind = 'Account' AND id <> %(account)s) reached
JOIN accounts a  ON a.account_id = reached.id
JOIN customers c ON c.customer_id = a.customer_id
GROUP BY c.region
ORDER BY c.region
"""


def q4_cypher(depth):
    depth = int(depth)
    return f"""
MATCH (a:Account {{account_id: $account}})
MATCH (a)-[:OWNS|USED_DEVICE*1..{depth}]-(b:Account)
WHERE b <> a
WITH DISTINCT b
MATCH (c:Customer)-[:OWNS]->(b)
RETURN c.region AS region, count(b) AS accounts
ORDER BY region
"""


# Supporting path for the report (one shortest ownership/device path to a reached account)
Q4_PATH_CYPHER = """
MATCH (a:Account {account_id: $account}), (b:Account {account_id: $target})
MATCH p = shortestPath((a)-[:OWNS|USED_DEVICE*..10]-(b))
RETURN [n IN nodes(p) | labels(n)[0] + ' ' +
        toString(coalesce(n.account_id, n.customer_id, n.device_id))] AS path, length(p) AS links
"""

Q4_PATH_SQL = """
WITH RECURSIVE edges(sk, si, dk, di) AS (
    SELECT 'Customer'::text, customer_id, 'Account'::text,  account_id  FROM accounts
    UNION ALL SELECT 'Account'::text, account_id, 'Customer'::text, customer_id FROM accounts
    UNION ALL SELECT 'Account'::text, account_id, 'Device'::text,   device_id   FROM account_devices
    UNION ALL SELECT 'Device'::text,  device_id,  'Account'::text,  account_id  FROM account_devices
), walk(kind, id, depth, path) AS (
    SELECT 'Account'::text, %(account)s::integer, 0, ARRAY['Account ' || %(account)s]
    UNION ALL
    SELECT e.dk, e.di, w.depth + 1, w.path || (e.dk || ' ' || e.di)
    FROM walk w JOIN edges e ON e.sk = w.kind AND e.si = w.id
    WHERE w.depth < %(depth)s AND NOT (e.dk || ' ' || e.di) = ANY (w.path)
)
SELECT path, depth FROM walk WHERE kind = 'Account' AND id = %(target)s
ORDER BY depth, path LIMIT 1
"""

# Chain/cycle details for the report: IDs, CAT times and amounts of given transfer ids
CHAIN_DETAILS_SQL = """
SELECT t.transfer_id, t.sender_id, s.role AS sender_role, t.receiver_id, r.role AS receiver_role,
       t.occurred_at, to_char(to_timestamp(t.occurred_at) AT TIME ZONE 'Africa/Kigali',
                              'YYYY-MM-DD HH24:MI:SS') AS occurred_cat, t.amount_rwf
FROM transfers t
JOIN accounts s ON s.account_id = t.sender_id
JOIN accounts r ON r.account_id = t.receiver_id
WHERE t.transfer_id = ANY(%(ids)s)
ORDER BY t.occurred_at, t.transfer_id
"""

# --------------------------------------------------------------------------- Q5
Q5_SQL = """
SELECT t1.transfer_id, t2.transfer_id, t3.transfer_id, t3.receiver_id AS final_receiver
FROM transfers t1
JOIN transfers t2 ON t2.sender_id = t1.receiver_id
                 AND t2.occurred_at >  t1.occurred_at
                 AND t2.occurred_at <= t1.occurred_at + 600
JOIN transfers t3 ON t3.sender_id = t2.receiver_id
                 AND t3.occurred_at >  t2.occurred_at
                 AND t3.occurred_at <= t2.occurred_at + 600
WHERE t1.sender_id = %(account)s
  AND t1.occurred_at >= %(start)s AND t1.occurred_at < %(end)s
  -- four distinct accounts: sender, t1 receiver, t2 receiver, t3 receiver
  AND t1.receiver_id <> t1.sender_id
  AND t2.receiver_id NOT IN (t1.sender_id, t1.receiver_id)
  AND t3.receiver_id NOT IN (t1.sender_id, t1.receiver_id, t2.receiver_id)
  -- 90*previous <= 100*next <= 105*previous, in BIGINT arithmetic
  AND 90::bigint  * t1.amount_rwf <= 100::bigint * t2.amount_rwf
  AND 100::bigint * t2.amount_rwf <= 105::bigint * t1.amount_rwf
  AND 90::bigint  * t2.amount_rwf <= 100::bigint * t3.amount_rwf
  AND 100::bigint * t3.amount_rwf <= 105::bigint * t2.amount_rwf
ORDER BY 1, 2, 3, 4
"""
Q5_CYPHER = """
MATCH (a:Account {account_id: $account})-[t1:TRANSFER]->(b:Account)-[t2:TRANSFER]->(c:Account)-[t3:TRANSFER]->(d:Account)
WHERE t1.occurred_at >= $start AND t1.occurred_at < $end
  AND t2.occurred_at > t1.occurred_at AND t2.occurred_at <= t1.occurred_at + 600
  AND t3.occurred_at > t2.occurred_at AND t3.occurred_at <= t2.occurred_at + 600
  AND a <> b AND a <> c AND a <> d AND b <> c AND b <> d AND c <> d
  AND 90 * t1.amount_rwf <= 100 * t2.amount_rwf AND 100 * t2.amount_rwf <= 105 * t1.amount_rwf
  AND 90 * t2.amount_rwf <= 100 * t3.amount_rwf AND 100 * t3.amount_rwf <= 105 * t2.amount_rwf
RETURN t1.transfer_id AS first_id, t2.transfer_id AS second_id, t3.transfer_id AS third_id,
       d.account_id AS final_receiver
ORDER BY first_id, second_id, third_id, final_receiver
"""

# --------------------------------------------------------------------------- Q6
Q6_SQL = """
WITH RECURSIVE chain(cur, ids, first_t, last_t, last_amt, closed) AS (
    SELECT t.receiver_id, ARRAY[t.transfer_id], t.occurred_at, t.occurred_at, t.amount_rwf,
           t.receiver_id = %(account)s
    FROM transfers t
    WHERE t.sender_id = %(account)s
      AND t.occurred_at >= %(start)s AND t.occurred_at < %(end)s
    UNION ALL
    SELECT t.receiver_id, c.ids || t.transfer_id, c.first_t, t.occurred_at, t.amount_rwf,
           t.receiver_id = %(account)s
    FROM chain c
    JOIN transfers t ON t.sender_id = c.cur
                    AND t.occurred_at >  c.last_t              -- strictly increasing time
                    AND t.occurred_at <  %(end)s               -- inside the hour
                    AND t.occurred_at <= c.first_t + 1800      -- span at most 1,800 s
    WHERE NOT c.closed                                          -- stop at the first return
      AND cardinality(c.ids) < 8
      AND 90::bigint  * c.last_amt   <= 100::bigint * t.amount_rwf
      AND 100::bigint * t.amount_rwf <= 105::bigint * c.last_amt
)
SELECT ids, cardinality(ids) AS length
FROM chain
WHERE closed AND cardinality(ids) BETWEEN 3 AND 8
ORDER BY ids
"""


def q6_cypher(max_len=8):
    return f"""
MATCH p = (a:Account {{account_id: $account}})-[:TRANSFER*3..{int(max_len)}]->(a)
WHERE all(r IN relationships(p) WHERE r.occurred_at >= $start AND r.occurred_at < $end)
  AND all(i IN range(0, length(p) - 2) WHERE
          relationships(p)[i].occurred_at < relationships(p)[i + 1].occurred_at
      AND 90 * relationships(p)[i].amount_rwf <= 100 * relationships(p)[i + 1].amount_rwf
      AND 100 * relationships(p)[i + 1].amount_rwf <= 105 * relationships(p)[i].amount_rwf)
  AND last(relationships(p)).occurred_at - head(relationships(p)).occurred_at <= 1800
  AND none(n IN nodes(p)[1..-1] WHERE n = a)
RETURN [r IN relationships(p) | r.transfer_id] AS ids, length(p) AS length
ORDER BY ids
"""


# --------------------------------------------------------------------------- Q7
# Version 1 (baseline): breadth-first walk over directed person-to-person transfers.
# UNION removes duplicate (account, depth) rows inside each iteration's result.
Q7_SQL_V1 = """
WITH RECURSIVE walk(id, depth) AS (
    SELECT a.account_id, 0 FROM accounts a
    WHERE a.account_id = %(account)s AND a.role = 'person'
    UNION
    SELECT t.receiver_id, w.depth + 1
    FROM walk w
    JOIN transfers t ON t.sender_id = w.id
    JOIN accounts r  ON r.account_id = t.receiver_id AND r.role = 'person'
    WHERE w.depth < %(bound)s
)
SELECT MIN(depth) AS length FROM walk WHERE id = %(destination)s
"""

# Version 2 (Section 6.3 improvement): search from both ends and meet in the middle.
# Forward depth <= ceil(bound/2), backward depth <= floor(bound/2). Any route of length
# L <= bound splits at node min(L, ceil(bound/2)), so min(f.depth + b.depth) is exact.
Q7_SQL_V2 = """
WITH RECURSIVE fwd(id, depth) AS (
    SELECT a.account_id, 0 FROM accounts a
    WHERE a.account_id = %(account)s AND a.role = 'person'
    UNION
    SELECT t.receiver_id, f.depth + 1
    FROM fwd f
    JOIN transfers t ON t.sender_id = f.id
    JOIN accounts r  ON r.account_id = t.receiver_id AND r.role = 'person'
    WHERE f.depth < %(fwd_depth)s
), bwd(id, depth) AS (
    SELECT a.account_id, 0 FROM accounts a
    WHERE a.account_id = %(destination)s AND a.role = 'person'
    UNION
    SELECT t.sender_id, b.depth + 1
    FROM bwd b
    JOIN transfers t ON t.receiver_id = b.id
    JOIN accounts s  ON s.account_id = t.sender_id AND s.role = 'person'
    WHERE b.depth < %(bwd_depth)s
)
SELECT MIN(f.depth + b.depth) AS length
FROM fwd f JOIN bwd b ON b.id = f.id
"""


def q7_cypher(bound):
    # Quantified path pattern: the person test is inside the pattern, so it is applied
    # DURING the shortest-path search (pre-filter), not after a shortest path was chosen.
    return f"""
MATCH (a:Account {{account_id: $account, role: 'person'}}), (b:Account {{account_id: $destination}})
OPTIONAL MATCH p = SHORTEST 1 (a)(()-[:TRANSFER]->(:Account {{role: 'person'}})){{1,{int(bound)}}}(b)
RETURN length(p) AS length
"""


def q7_path_cypher(bound):
    return f"""
MATCH (a:Account {{account_id: $account, role: 'person'}}), (b:Account {{account_id: $destination}})
MATCH p = SHORTEST 1 (a)(()-[:TRANSFER]->(:Account {{role: 'person'}})){{1,{int(bound)}}}(b)
RETURN [n IN nodes(p) | n.account_id] AS accounts,
       [r IN relationships(p) | r.transfer_id] AS transfer_ids, length(p) AS length
"""


# One supporting path in SQL for a known length L: backward distances from the destination,
# then a deterministic greedy walk that always steps to a person whose distance is one less.
Q7_PATH_SQL = """
WITH RECURSIVE back(id, depth) AS (
    SELECT %(destination)s::integer, 0
    UNION
    SELECT t.sender_id, b.depth + 1
    FROM back b
    JOIN transfers t ON t.receiver_id = b.id
    JOIN accounts s  ON s.account_id = t.sender_id AND s.role = 'person'
    WHERE b.depth < %(length)s - 1
), dist AS (
    SELECT id, MIN(depth) AS d FROM back GROUP BY id
), path(node, step, accounts, transfer_ids) AS (
    SELECT %(account)s::integer, 0, ARRAY[%(account)s::integer], ARRAY[]::bigint[]
    UNION ALL
    SELECT x.receiver_id, p.step + 1, p.accounts || x.receiver_id, p.transfer_ids || x.transfer_id
    FROM path p
    CROSS JOIN LATERAL (
        SELECT t.receiver_id, t.transfer_id
        FROM transfers t
        JOIN dist ON dist.id = t.receiver_id AND dist.d = %(length)s - p.step - 1
        WHERE t.sender_id = p.node
        ORDER BY t.receiver_id, t.transfer_id
        LIMIT 1
    ) x
    WHERE p.step < %(length)s
)
SELECT accounts, transfer_ids, step AS length FROM path WHERE step = %(length)s
"""

# Path check used for both engines' supporting paths
PATH_CHECK_SQL = """
SELECT t.transfer_id, t.sender_id, t.receiver_id, t.occurred_at, t.amount_rwf, s.role, r.role
FROM transfers t
JOIN accounts s ON s.account_id = t.sender_id
JOIN accounts r ON r.account_id = t.receiver_id
WHERE t.transfer_id = ANY(%(ids)s)
"""

# --------------------------------------------------------------------------- 3.3 inspect one account
INSPECT_SQL = """
SELECT a.account_id, a.role, c.customer_id, c.region,
       d.device_id, d.access_type, ad.first_day, ad.last_day, ad.observations,
       t.transfer_id, t.receiver_id, t.occurred_at,
       to_timestamp(t.occurred_at) AT TIME ZONE 'Africa/Kigali' AS occurred_cat, t.amount_rwf
FROM accounts a
JOIN customers c        ON c.customer_id = a.customer_id
JOIN account_devices ad ON ad.account_id = a.account_id
JOIN devices d          ON d.device_id = ad.device_id
JOIN transfers t        ON t.sender_id = a.account_id
WHERE a.account_id = %(account)s
ORDER BY ad.device_id, t.transfer_id
LIMIT 1
"""
INSPECT_CYPHER = """
MATCH (c:Customer)-[:OWNS]->(a:Account {account_id: $account})-[u:USED_DEVICE]->(d:Device)
MATCH (a)-[t:TRANSFER]->(r:Account)
RETURN a.account_id, a.role, c.customer_id, c.region,
       d.device_id, d.access_type, u.first_day, u.last_day, u.observations,
       t.transfer_id, r.account_id AS receiver_id, t.occurred_at,
       toString(datetime({epochSeconds: t.occurred_at, timezone: 'Africa/Kigali'})) AS occurred_cat,
       t.amount_rwf
ORDER BY d.device_id, t.transfer_id
LIMIT 1
"""


# --------------------------------------------------------------------------- case list
def all_cases(q7_sql=Q7_SQL_V1):
    """The 61 comparison cases: Q1 6, Q2 1, Q3 6, Q4 24, Q5 6, Q6 6, Q7 12."""
    cases = []
    for s in CASES:
        cases.append(dict(case=f"Q1-{s}", q="Q1", set=s, sql=Q1_SQL, cypher=Q1_CYPHER, params=case_params(s)))
    cases.append(dict(case="Q2-month", q="Q2", set="month", sql=Q2_SQL, cypher=Q2_CYPHER,
                      params=dict(start=MONTH_START, end=MONTH_END)))
    for s in CASES:
        cases.append(dict(case=f"Q3-{s}", q="Q3", set=s, sql=Q3_SQL, cypher=Q3_CYPHER, params=case_params(s)))
    for s in CASES:
        for d in Q4_DEPTHS:
            p = dict(case_params(s), depth=d)
            cases.append(dict(case=f"Q4-{s}-d{d}", q="Q4", set=s, sql=Q4_SQL, cypher=q4_cypher(d), params=p))
    for s in CASES:
        cases.append(dict(case=f"Q5-{s}", q="Q5", set=s, sql=Q5_SQL, cypher=Q5_CYPHER, params=case_params(s)))
    for s in CASES:
        cases.append(dict(case=f"Q6-{s}", q="Q6", set=s, sql=Q6_SQL, cypher=q6_cypher(), params=case_params(s)))
    for s in CASES:
        for b in Q7_BOUNDS:
            p = dict(case_params(s), bound=b, fwd_depth=math.ceil(b / 2), bwd_depth=b // 2)
            cases.append(dict(case=f"Q7-{s}-b{b}", q="Q7", set=s, sql=q7_sql, cypher=q7_cypher(b), params=p))
    assert len(cases) == 61, len(cases)
    return cases


def timed_cases(q7_sql=Q7_SQL_V1):
    """Section 6.2 fixed selection: 21 cases per engine."""
    keep = set()
    for s in ("B", "E"):
        keep |= {f"Q1-{s}", f"Q3-{s}", f"Q5-{s}", f"Q6-{s}"}
        keep |= {f"Q4-{s}-d{d}" for d in Q4_DEPTHS}
        keep |= {f"Q7-{s}-b{b}" for b in Q7_BOUNDS}
    keep.add("Q2-month")
    sel = [c for c in all_cases(q7_sql) if c["case"] in keep]
    assert len(sel) == 21, len(sel)
    return sel
