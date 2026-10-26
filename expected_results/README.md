# Reference run (for comparison only)

Produced on 19 Oct 2026 by a complete **PostgreSQL** run of this code on a 2-vCPU / 8 GB Linux VM
(PostgreSQL 16.15, shared_buffers 2 GB). Neo4j was not available on that machine, so there are no
Neo4j files here.

* **Query answers** (`outputs_pg.json`, `examples_pg.txt`, `independent_check.json`,
  `q7_improvement_check.json`) are deterministic: your PostgreSQL *and* Neo4j answers must be
  identical.
* **Times, sizes and load-test numbers** (`bench_*.csv`, `bench_summary.*`, `load_*`,
  `capture_audit.json` seconds, `pg_checks.json` sizes, `plans/`) belong to that machine only.
  Report your own numbers, never these.

Your own runs write to `../results/`.
