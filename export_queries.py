"""Write every SQL / Cypher query from queries.py into two readable files for the report:
sql/queries_q1_q7.sql and neo4j/queries_q1_q7.cypher.   python export_queries.py"""
import config
import queries as q

SQL = [("Q1 account activity", q.Q1_SQL), ("Q2 daily activity", q.Q2_SQL), ("Q3 shared devices", q.Q3_SQL),
       ("Q4 ownership/device network (depth = 4, 6, 8, 10)", q.Q4_SQL), ("Q4 supporting path", q.Q4_PATH_SQL),
       ("Q5 rapid onward payments", q.Q5_SQL), ("Q6 circular payments", q.Q6_SQL),
       ("Q7 shortest connection - version 1 (baseline)", q.Q7_SQL_V1),
       ("Q7 shortest connection - version 2 (bidirectional, Section 6.3)", q.Q7_SQL_V2),
       ("Q7 one supporting path for a known length", q.Q7_PATH_SQL),
       ("Path / chain verification", q.PATH_CHECK_SQL), ("Chain details in CAT", q.CHAIN_DETAILS_SQL),
       ("3.3 inspect one account", q.INSPECT_SQL)]
CY = [("Q1 account activity", q.Q1_CYPHER), ("Q2 daily activity", q.Q2_CYPHER), ("Q3 shared devices", q.Q3_CYPHER)]
CY += [(f"Q4 depth {d}", q.q4_cypher(d)) for d in (4, 6, 8, 10)]
CY += [("Q4 supporting path", q.Q4_PATH_CYPHER), ("Q5 rapid onward payments", q.Q5_CYPHER),
       ("Q6 circular payments", q.q6_cypher())]
CY += [(f"Q7 bound {b}", q.q7_cypher(b)) for b in (4, 6)] + [("Q7 supporting path, bound 6", q.q7_path_cypher(6)),
       ("3.3 inspect one account", q.INSPECT_CYPHER)]

header = "Parameters: account, destination, start, end (epoch s, 09:45-10:45 CAT), depth, bound, fwd_depth, bwd_depth"
with open(config.ROOT / "sql" / "queries_q1_q7.sql", "w") as f:
    f.write(f"-- Generated from queries.py. psycopg placeholders %(name)s.\n-- {header}\n")
    for t, s in SQL:
        f.write(f"\n-- ===== {t} =====\n{s.strip()};\n")
with open(config.ROOT / "neo4j" / "queries_q1_q7.cypher", "w") as f:
    f.write(f"// Generated from queries.py. Parameters $name.\n// {header}\n")
    for t, s in CY:
        f.write(f"\n// ===== {t} =====\n{s.strip()};\n")
print("Wrote sql/queries_q1_q7.sql and neo4j/queries_q1_q7.cypher")
