// Generated from queries.py. Parameters $name.
// Parameters: account, destination, start, end (epoch s, 09:45-10:45 CAT), depth, bound, fwd_depth, bwd_depth

// ===== Q1 account activity =====
MATCH (a:Account {account_id: $account})
OPTIONAL MATCH (a)-[t:TRANSFER]->()
WHERE t.occurred_at >= $start AND t.occurred_at < $end
RETURN count(t) AS transfers, coalesce(sum(t.amount_rwf), 0) AS total_rwf;

// ===== Q2 daily activity =====
MATCH ()-[t:TRANSFER]->()
WITH date(datetime({epochSeconds: t.occurred_at, timezone: 'Africa/Kigali'})) AS day, t.amount_rwf AS amount
RETURN day, count(*) AS transfers, sum(amount) AS total_rwf
ORDER BY day;

// ===== Q3 shared devices =====
MATCH (a:Account {account_id: $account})-[r1:USED_DEVICE]->(d:Device)<-[r2:USED_DEVICE]-(o:Account)
WHERE o <> a
WITH o, d,
     CASE WHEN r1.first_day >= r2.first_day THEN r1.first_day ELSE r2.first_day END AS overlap_start,
     CASE WHEN r1.last_day  <= r2.last_day  THEN r1.last_day  ELSE r2.last_day  END AS overlap_end
WHERE overlap_start <= overlap_end
RETURN o.account_id AS account_id, d.device_id AS device_id, d.access_type AS access_type,
       overlap_start, overlap_end
ORDER BY account_id, device_id;

// ===== Q4 depth 4 =====
MATCH (a:Account {account_id: $account})
MATCH (a)-[:OWNS|USED_DEVICE*1..4]-(b:Account)
WHERE b <> a
WITH DISTINCT b
MATCH (c:Customer)-[:OWNS]->(b)
RETURN c.region AS region, count(b) AS accounts
ORDER BY region;

// ===== Q4 depth 6 =====
MATCH (a:Account {account_id: $account})
MATCH (a)-[:OWNS|USED_DEVICE*1..6]-(b:Account)
WHERE b <> a
WITH DISTINCT b
MATCH (c:Customer)-[:OWNS]->(b)
RETURN c.region AS region, count(b) AS accounts
ORDER BY region;

// ===== Q4 depth 8 =====
MATCH (a:Account {account_id: $account})
MATCH (a)-[:OWNS|USED_DEVICE*1..8]-(b:Account)
WHERE b <> a
WITH DISTINCT b
MATCH (c:Customer)-[:OWNS]->(b)
RETURN c.region AS region, count(b) AS accounts
ORDER BY region;

// ===== Q4 depth 10 =====
MATCH (a:Account {account_id: $account})
MATCH (a)-[:OWNS|USED_DEVICE*1..10]-(b:Account)
WHERE b <> a
WITH DISTINCT b
MATCH (c:Customer)-[:OWNS]->(b)
RETURN c.region AS region, count(b) AS accounts
ORDER BY region;

// ===== Q4 supporting path =====
MATCH (a:Account {account_id: $account}), (b:Account {account_id: $target})
MATCH p = shortestPath((a)-[:OWNS|USED_DEVICE*..10]-(b))
RETURN [n IN nodes(p) | labels(n)[0] + ' ' +
        toString(coalesce(n.account_id, n.customer_id, n.device_id))] AS path, length(p) AS links;

// ===== Q5 rapid onward payments =====
MATCH (a:Account {account_id: $account})-[t1:TRANSFER]->(b:Account)-[t2:TRANSFER]->(c:Account)-[t3:TRANSFER]->(d:Account)
WHERE t1.occurred_at >= $start AND t1.occurred_at < $end
  AND t2.occurred_at > t1.occurred_at AND t2.occurred_at <= t1.occurred_at + 600
  AND t3.occurred_at > t2.occurred_at AND t3.occurred_at <= t2.occurred_at + 600
  AND a <> b AND a <> c AND a <> d AND b <> c AND b <> d AND c <> d
  AND 90 * t1.amount_rwf <= 100 * t2.amount_rwf AND 100 * t2.amount_rwf <= 105 * t1.amount_rwf
  AND 90 * t2.amount_rwf <= 100 * t3.amount_rwf AND 100 * t3.amount_rwf <= 105 * t2.amount_rwf
RETURN t1.transfer_id AS first_id, t2.transfer_id AS second_id, t3.transfer_id AS third_id,
       d.account_id AS final_receiver
ORDER BY first_id, second_id, third_id, final_receiver;

// ===== Q6 circular payments =====
MATCH p = (a:Account {account_id: $account})-[:TRANSFER*3..8]->(a)
WHERE all(r IN relationships(p) WHERE r.occurred_at >= $start AND r.occurred_at < $end)
  AND all(i IN range(0, length(p) - 2) WHERE
          relationships(p)[i].occurred_at < relationships(p)[i + 1].occurred_at
      AND 90 * relationships(p)[i].amount_rwf <= 100 * relationships(p)[i + 1].amount_rwf
      AND 100 * relationships(p)[i + 1].amount_rwf <= 105 * relationships(p)[i].amount_rwf)
  AND last(relationships(p)).occurred_at - head(relationships(p)).occurred_at <= 1800
  AND none(n IN nodes(p)[1..-1] WHERE n = a)
RETURN [r IN relationships(p) | r.transfer_id] AS ids, length(p) AS length
ORDER BY ids;

// ===== Q7 bound 4 =====
MATCH (a:Account {account_id: $account, role: 'person'}), (b:Account {account_id: $destination})
OPTIONAL MATCH p = SHORTEST 1 (a)(()-[:TRANSFER]->(:Account {role: 'person'})){1,4}(b)
RETURN length(p) AS length;

// ===== Q7 bound 6 =====
MATCH (a:Account {account_id: $account, role: 'person'}), (b:Account {account_id: $destination})
OPTIONAL MATCH p = SHORTEST 1 (a)(()-[:TRANSFER]->(:Account {role: 'person'})){1,6}(b)
RETURN length(p) AS length;

// ===== Q7 supporting path, bound 6 =====
MATCH (a:Account {account_id: $account, role: 'person'}), (b:Account {account_id: $destination})
MATCH p = SHORTEST 1 (a)(()-[:TRANSFER]->(:Account {role: 'person'})){1,6}(b)
RETURN [n IN nodes(p) | n.account_id] AS accounts,
       [r IN relationships(p) | r.transfer_id] AS transfer_ids, length(p) AS length;

// ===== 3.3 inspect one account =====
MATCH (c:Customer)-[:OWNS]->(a:Account {account_id: $account})-[u:USED_DEVICE]->(d:Device)
MATCH (a)-[t:TRANSFER]->(r:Account)
RETURN a.account_id, a.role, c.customer_id, c.region,
       d.device_id, d.access_type, u.first_day, u.last_day, u.observations,
       t.transfer_id, r.account_id AS receiver_id, t.occurred_at,
       toString(datetime({epochSeconds: t.occurred_at, timezone: 'Africa/Kigali'})) AS occurred_cat,
       t.amount_rwf
ORDER BY d.device_id, t.transfer_id
LIMIT 1;
