-- Generated from queries.py. psycopg placeholders %(name)s.
-- Parameters: account, destination, start, end (epoch s, 09:45-10:45 CAT), depth, bound, fwd_depth, bwd_depth

-- ===== Q1 account activity =====
SELECT COUNT(*) AS transfers, COALESCE(SUM(amount_rwf), 0) AS total_rwf
FROM transfers
WHERE sender_id = %(account)s
  AND occurred_at >= %(start)s AND occurred_at < %(end)s;

-- ===== Q2 daily activity =====
SELECT (to_timestamp(occurred_at) AT TIME ZONE 'Africa/Kigali')::date AS day,
       COUNT(*) AS transfers, SUM(amount_rwf) AS total_rwf
FROM transfers
GROUP BY 1
ORDER BY 1;

-- ===== Q3 shared devices =====
SELECT o.account_id, o.device_id, d.access_type,
       GREATEST(r.first_day, o.first_day) AS overlap_start,
       LEAST(r.last_day, o.last_day)       AS overlap_end
FROM account_devices r
JOIN account_devices o ON o.device_id = r.device_id AND o.account_id <> r.account_id
JOIN devices d         ON d.device_id = r.device_id
WHERE r.account_id = %(account)s
  AND GREATEST(r.first_day, o.first_day) <= LEAST(r.last_day, o.last_day)
ORDER BY o.account_id, o.device_id;

-- ===== Q4 ownership/device network (depth = 4, 6, 8, 10) =====
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
ORDER BY c.region;

-- ===== Q4 supporting path =====
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
ORDER BY depth, path LIMIT 1;

-- ===== Q5 rapid onward payments =====
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
ORDER BY 1, 2, 3, 4;

-- ===== Q6 circular payments =====
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
ORDER BY ids;

-- ===== Q7 shortest connection - version 1 (baseline) =====
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
SELECT MIN(depth) AS length FROM walk WHERE id = %(destination)s;

-- ===== Q7 shortest connection - version 2 (bidirectional, Section 6.3) =====
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
FROM fwd f JOIN bwd b ON b.id = f.id;

-- ===== Q7 one supporting path for a known length =====
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
SELECT accounts, transfer_ids, step AS length FROM path WHERE step = %(length)s;

-- ===== Path / chain verification =====
SELECT t.transfer_id, t.sender_id, t.receiver_id, t.occurred_at, t.amount_rwf, s.role, r.role
FROM transfers t
JOIN accounts s ON s.account_id = t.sender_id
JOIN accounts r ON r.account_id = t.receiver_id
WHERE t.transfer_id = ANY(%(ids)s);

-- ===== Chain details in CAT =====
SELECT t.transfer_id, t.sender_id, s.role AS sender_role, t.receiver_id, r.role AS receiver_role,
       t.occurred_at, to_char(to_timestamp(t.occurred_at) AT TIME ZONE 'Africa/Kigali',
                              'YYYY-MM-DD HH24:MI:SS') AS occurred_cat, t.amount_rwf
FROM transfers t
JOIN accounts s ON s.account_id = t.sender_id
JOIN accounts r ON r.account_id = t.receiver_id
WHERE t.transfer_id = ANY(%(ids)s)
ORDER BY t.occurred_at, t.transfer_id;

-- ===== 3.3 inspect one account =====
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
LIMIT 1;
