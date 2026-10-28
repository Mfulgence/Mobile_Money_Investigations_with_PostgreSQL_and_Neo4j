# Mobile Money Investigations with PostgreSQL and Neo4j

Advanced Big Data Analytics – Project 2 (AUCA), Group 17.
Due 26 October 2026, 23:59 CAT.

This repository captures the fixed September 2026 mobile-money dataset from
`mobile_money_generator.py` (unchanged), loads it into **PostgreSQL** and **Neo4j Community**,
answers Q1–Q7 with parameterised SQL/Cypher pairs, checks that both engines agree on all
61 cases, times them, tries one SQL improvement, runs a concurrent load test and produces
the evidence used in the report.

> The final report is **[report/Mobile_Money_Report_Group17.pdf](report/Mobile_Money_Report_Group17.pdf)**.

## Repository layout

| Path | Purpose | Handout section |
|---|---|---|
| `mobile_money_generator.py` | Supplied generator – **unchanged** (check with `step00`) | 9.2 |
| `config.py`, `config_local.example.py` | Paths and connection settings (placeholder secrets) | – |
| `mm_common.py` | Case table A–F, CAT hour boundaries, `run_pg()` / `run_neo()`, normalisation | 4, 6.1 |
| `queries.py` | Every SQL / Cypher pair (Q1–Q7, Q7 v1 and v2, path checks) and the 61/21-case lists | 4–6 |
| `step00_verify_generator.py` | SHA-256 check that the generator is unchanged | 9.2 |
| `step01_environment.py` | Versions, CPU, RAM, OS, DB memory settings, connection test | 1.1 |
| `step02_capture.py` | capture.py: preview + streaming CSV capture with audit totals | 1.2 |
| `sql/00_create_database.sql` | Database, time zone, memory settings | 1.1 |
| `sql/01_tables.sql` | Five tables, NOT NULL columns | 2.1 |
| `sql/02_load.psql` | `\copy` bulk load with `\timing` | 2.2 |
| `sql/03_constraints_indexes.sql` | PK, FK, CHECK, required indexes, BRIN, ANALYZE | 2.1, 2.2 |
| `step04_pg_checks.py` | Row counts, audit totals, roles, validated constraints, indexes, sizes | 2.2 |
| `step05_neo4j_prepare_import.py` | prepare_import.py: typed temporary copies, owns.csv, import command | 3.2 |
| `neo4j/import_full.bat` / `.sh` | Generated `neo4j-admin database import full` command | 3.2 |
| `neo4j/setup.cypher` | Unique constraints + TRANSFER.occurred_at range index | 3.2 |
| `step06_neo4j_setup_checks.py` | Constraints/indexes, store sizes, all graph checks, cleanup | 3.2 |
| `step07_inspect_account.py` | One account traced in SQL and Cypher | 3.3 |
| `step08_run_queries.py` | Runs Q1–Q7 for all sets, Q4 prediction, Q7 path checks, charts | 4, 5 |
| `step09_compare.py` | 61-case correctness table | 6.1, 9.2 |
| `step09b_independent_check.py` | Plain-Python check of one overlap and one chain/cycle from CSVs | 6.1 |
| `step10_benchmark.py` | 21-case timing (3 warm-ups + 5 runs), summary and ratios | 6.2 |
| `step10b_plans.py` | EXPLAIN (ANALYZE, BUFFERS) and PROFILE | 6.2, 6.3 |
| `step11_sql_improvement.py` | Q7 bidirectional SQL: recheck 12 cases, retime 4 | 6.3 |
| `step12_load_test.py`, `step12b_plot_scaling.py` | Multiprocessing load test and scaling plots | 7 |
| `export_queries.py` | Writes all queries to `sql/queries_q1_q7.sql` and `neo4j/queries_q1_q7.cypher` | report |
| `report/` | Report draft, diagrams, screenshot checklist | 8, 9.1 |
| `expected_results/` | Reference outputs from our own complete run (for comparison) | – |
| `results/` | Everything your runs produce (JSON, CSV, plans, plots) – submitted | – |

`data/` (≈0.8 GB CSVs), `neo4j_import/` and the database stores stay local (`.gitignore`).

## Requirements

* Windows 10/11, Linux or macOS, ≥ 10 GB free disk, 8 GB RAM minimum (16 GB recommended)
* Python 3.12 (3.11–3.13 work), PostgreSQL 16 or 17, Neo4j Community 2025.x (or 5.26 LTS) with Java 21
* `pip install -r requirements.txt`

## Execution order (all commands from the project folder)

```bat
REM 0. environment
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
REM then edit passwords and NEO4J_HOME
copy config_local.example.py config_local.py
python step00_verify_generator.py

REM 1. capture (Section 1)
REM then restart PostgreSQL
psql -U postgres -f sql\00_create_database.sql
python step01_environment.py --pg
python step02_capture.py --preview
python step02_capture.py

REM 2. PostgreSQL (Section 2)
psql -U postgres -d mobile_money -f sql\01_tables.sql
psql -U postgres -d mobile_money -v csvdir="%CD:\=/%/data" -f sql\02_load.psql
psql -U postgres -d mobile_money -f sql\03_constraints_indexes.sql
python step04_pg_checks.py

REM 3. Neo4j (Section 3)  - Neo4j stopped for the import
python step05_neo4j_prepare_import.py
neo4j\import_full.bat
REM start Neo4j, then
python step06_neo4j_setup_checks.py
python step06_neo4j_setup_checks.py --cleanup
python step01_environment.py
python step07_inspect_account.py 998

REM 4-5. questions (Sections 4 and 5)
python step08_run_queries.py --engine both

REM 6. correctness and performance (Section 6)
python step09_compare.py --q7 v1
python step09b_independent_check.py
REM Neo4j stopped
python step10_benchmark.py --engine pg
python step10b_plans.py --engine pg
REM PostgreSQL stopped
python step10_benchmark.py --engine neo
python step10b_plans.py --engine neo
REM needs both for the length recheck; --no-neo otherwise
python step11_sql_improvement.py
REM before/after Q7 plans
python step10b_plans.py --engine pg
python step10_benchmark.py --summary

REM 7. load test (Section 7) - one engine running at a time
python step12_load_test.py --engine pg
python step12_load_test.py --engine neo
python step12_load_test.py --summary
python step12b_plot_scaling.py

REM 9. final verification
python step09_compare.py --q7 v2
python step00_verify_generator.py
```

On Linux/macOS use `python3`, `source .venv/bin/activate`, `-v csvdir="$PWD/data"` and `neo4j/import_full.sh`.

## Key results (deterministic – identical on every machine)

| Set | Review → destination | Q1 hour | Q3 rows | Q4 reached d4/6/8/10 | Q5 chains | Q6 cycles | Q7 len (b4 / b6) |
|---|---|---|---|---|---|---|---|
| A | 998 → 24755 (6 Sep) | 1 transfer, 200,000 RWF | 4 | 10 / 43 / 175 / 187 | 1 | 1 (len 4) | 3 / 3 |
| B | 147228 → 186823 (13 Sep) | 1, 1,050,000 | 9 | 46 / 178 / 188 / 228 | 1 | 0 | none / 5 |
| C | 206978 → 6573 (8 Sep) | 1, 300,000 | 9 | 146 / 483 / 832 / 1433 | 1 | 1 (len 6) | none / 5 |
| D | 237998 → 21755 (6 Sep) | 1, 45,000 | 4 | 10 / 44 / 180 / 192 | 0 | 0 | 3 / 3 |
| E | 144228 → 183823 (13 Sep) | 1, 40,000 | 9 | 47 / 183 / 193 / 230 | 0 | 0 | none / 5 |
| F | 203978 → 3573 (8 Sep) | 1, 30,000 | 9 | 147 / 488 / 837 / 1426 | 0 | 0 | none / 5 |

Month: 20,003,300 transfers, 231,482,327,870 RWF, 06:00:00 on 1 Sep to 21:59:59 on 30 Sep CAT.
Timings, sizes and load-test numbers depend on the machine and must come from your own runs.

## Notes

* SQL parameters use psycopg `%(name)s`; Cypher uses `$name`. Depth/bound integers inside
  variable-length Cypher patterns cannot be parameters, so `q4_cypher(d)`, `q6_cypher()` and
  `q7_cypher(b)` insert validated integers.
* Q7 in Neo4j uses `SHORTEST 1` with the person test **inside** the quantified path pattern,
  so it is applied during the search (Neo4j 5.21+ / 2025.x).
* Secrets: only placeholders are committed. Real passwords live in `config_local.py`
  (git-ignored) or environment variables `PGPASSWORD`, `NEO4J_PASSWORD`.
