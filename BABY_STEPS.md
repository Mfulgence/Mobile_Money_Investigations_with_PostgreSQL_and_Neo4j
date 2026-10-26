# Baby Steps – Project 2 from an empty laptop to the submitted ZIP

This guide walks through every milestone of the handout in order, on **Windows 10/11**
(Linux/macOS differences are noted). For every step you get: **what to do**, **what you should
see**, and **📸 which screenshot to take**. Every screenshot must show the executed command, its
result, the Windows taskbar and the clock.

Expected total time on a normal laptop: about 3–4 hours of commands spread over the project
days (most of it is waiting for timings and the load test).

Reference numbers in this guide come from our own complete PostgreSQL run. **Query answers
are deterministic** – you must get exactly the same rows. **Timings and sizes are not** – yours
will differ and those are the ones you report.

---

## Step 0 – Install the software (once)

### 0.1 Python 3.12
1. Download Python 3.12 from python.org → *Windows installer (64-bit)*.
2. Tick **"Add python.exe to PATH"** → Install.
3. Open **Command Prompt** (Start → type `cmd`). Use *Command Prompt*, not PowerShell, for all
   commands in this guide.
4. Check: `py -3.12 --version` → `Python 3.12.x`.

### 0.2 PostgreSQL 16 (or 17)
1. Download the EDB installer from postgresql.org → Windows.
2. Keep the defaults (port **5432**, superuser **postgres**); write down the password you choose.
3. Add psql to PATH for this window:
   `set PATH=%PATH%;C:\Program Files\PostgreSQL\16\bin`
   (Add it permanently via *System → Environment variables → Path* to avoid repeating this.)
4. Check: `psql --version` → `psql (PostgreSQL) 16.x`.

### 0.3 Java 21 and Neo4j Community
1. Install **Java 21** (e.g. Eclipse Temurin 21 JDK from adoptium.net, tick "Set JAVA_HOME").
   Check: `java -version` → `21.x`.
2. Download **Neo4j Community Edition** (Windows ZIP) from the Neo4j Deployment Center
   (2025.x, or 5.26 LTS). Unzip to e.g. `C:\neo4j\neo4j-community-2025.09.0`.
   This folder is your **NEO4J_HOME**.
3. Set the initial password **before the first start**:
   ```bat
   cd /d C:\neo4j\neo4j-community-2025.09.0
   bin\neo4j-admin.bat dbms set-initial-password YourNeo4jPassword
   ```
4. Memory settings – open `conf\neo4j.conf` in Notepad and add/edit (16 GB laptop; on 8 GB use 2g/2g):
   ```
   server.memory.heap.initial_size=4g
   server.memory.heap.max_size=4g
   server.memory.pagecache.size=4g
   ```
5. Start Neo4j in its own Command Prompt window and leave it open:
   `bin\neo4j.bat console`  → wait for `Started.` Browser: http://localhost:7474 (user `neo4j`).
   Stop it later with **Ctrl+C** in that window.

### 0.4 Disk space
You need ~10 GB free: CSVs 0.8 GB, temporary Neo4j copies 0.8 GB, PostgreSQL ≈3.7 GB,
Neo4j store ≈3–4 GB.

---

## Step 1 – Set up the project folder

1. Unzip the project to e.g. `C:\Users\<you>\Documents\mobile_money_project` and open cmd there:
   ```bat
   cd /d C:\Users\<you>\Documents\mobile_money_project
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   The prompt now starts with `(.venv)`. Run `.venv\Scripts\activate` again in every new window.
2. Create your private settings file:
   ```bat
   copy config_local.example.py config_local.py
   notepad config_local.py
   ```
   Fill in your PostgreSQL password, Neo4j password and NEO4J_HOME path. Save.
   (`config_local.py` is git-ignored – your passwords never reach GitHub.)
3. Prove the generator is unchanged:
   `python step00_verify_generator.py` → `UNCHANGED - matches the supplied generator`.

---

## Milestone 1 – Capture the data

### 1.1 Prepare your workspace [2 marks]

1. Create the database and memory settings:
   ```bat
   psql -U postgres -f sql\00_create_database.sql
   ```
   Enter the postgres password. You should see `CREATE DATABASE`, `ALTER DATABASE` and
   `ALTER SYSTEM` lines. Open the file first if you have 8 GB RAM and change the values as the
   comment says.
2. Restart PostgreSQL so memory settings apply: Start → `services.msc` → **postgresql-x64-16**
   → Restart.
3. Record versions, hardware and settings for both databases (Neo4j must be running):
   ```bat
   python step01_environment.py
   ```
   You see JSON with OS, CPU, RAM, Python/driver versions, PostgreSQL `version()`,
   `shared_buffers`, `work_mem`, `TimeZone = Africa/Kigali`, Neo4j version/edition and
   `server.memory.*` settings, then `Connections OK`. Saved to `results/environment.json`.

📸 **1.1** – the step01 output showing both successful connections, TimeZone Africa/Kigali and the
memory settings. Optionally also `psql -U postgres -d mobile_money -c "SHOW timezone"`.

### 1.2 Build capture.py [5 marks]

1. Preview the streams:
   ```bat
   python step02_capture.py --preview
   ```
   You see `dataset_info()`, `FIELDS` and ten records from each of the five `iter_<stream>()`
   functions (taken with `itertools.islice`; each call starts the stream again).
   📸 **1.2a** – the preview.
2. Full capture (about 1–3 minutes):
   ```bat
   python step02_capture.py
   ```
   It writes `data\customers.csv` … `data\transfers.csv` row by row with `csv.DictWriter`
   (never holding a stream in memory), prints a log line every million transfers, then:
   ```
   records written : 20,993,500 (expected 20,993,500)
   transfer audit  : count 20003300, earliest 1788235200 (2026-09-01 06:00:00 CAT),
                     latest 1790798399 (2026-09-30 21:59:59 CAT), sum_amount_rwf 231482327870
   ```
   Every stream line must say `OK`. Seconds and CSV sizes are saved in `results\capture_audit.json`.
   📸 **1.2b** – the five stream lines + totals + audit.

*How the starter TODO was completed:* inside the loop we `writer.writerow(row)`, increment
consumed/written counters, and for transfers add `amount_rwf` to the sum and update min/max
`occurred_at` (the file is not time-sorted, so min/max must be tracked, not taken from the first and
last rows).

---

## Milestone 2 – Build PostgreSQL

### 2.1 Define the five tables [4 marks]
```bat
psql -U postgres -d mobile_money -f sql\01_tables.sql
```
→ five `CREATE TABLE`. Types follow the handout: INTEGER for IDs, amounts and observations,
BIGINT for `transfer_id` and `occurred_at`, SMALLINT for days, TEXT for categories, all NOT NULL.
Keys, foreign keys and CHECK rules are in `sql\03_constraints_indexes.sql` and are added
**after** loading (faster, and lets you time loading and constraint/index setup separately).
The schema drawing is `report\diagrams\postgres_schema.png`; field meanings and units are in
the comments of `01_tables.sql` and in the report.

📸 **2.1** – after step 2.2 has added the constraints, run in psql:
`\d+ accounts`, `\d+ account_devices`, `\d+ transfers` (definitions + constraints).

### 2.2 Bulk-load and check [5 marks]
1. Load (Command Prompt, from the project folder):
   ```bat
   psql -U postgres -d mobile_money -v csvdir="%CD:\=/%/data" -f sql\02_load.psql
   ```
   `%CD:\=/%` is the current folder with forward slashes. Each `\copy` prints `COPY n` and
   `Time: … ms`. Our run: transfers ≈14 s, all files ≈15 s. **Write down the times (load seconds).**
2. Constraints and indexes:
   ```bat
   psql -U postgres -d mobile_money -f sql\03_constraints_indexes.sql
   ```
   Every statement prints `Time:`. Add them up = **index/constraint setup seconds** (ours ≈58 s).
   This adds the 5 PKs, 5 FKs, CHECKs (`amount_rwf > 0`, `observations > 0`,
   `0 <= first_day <= last_day <= 29`), the four required B-tree indexes (two with INCLUDE),
   the BRIN index on `occurred_at`, then `VACUUM ANALYZE`.
3. Checks:
   ```bat
   python step04_pg_checks.py
   ```
   Every line must start with `OK`, roles 240,000 / 6,000 / 2,000, every constraint
   `validated=True`, ten indexes listed, sizes table (ours: data 1.25 GB, indexes 2.47 GB,
   database 3.73 GB, GB = 10⁹ bytes), ending in `ALL CHECKS PASSED`.

📸 **2.2a** – the load timings. 📸 **2.2b** – step04 output (counts, audit, roles, validated
constraints, indexes, sizes).

---

## Milestone 3 – Build Neo4j

### 3.1 Map the same facts [4 marks]
Nothing to run. The mapping (drawn in `report\diagrams\graph_schema.png`, table in the report):

| Source field | Graph element |
|---|---|
| customers.customer_id, region | `(:Customer {customer_id, region})` |
| accounts.account_id, role | `(:Account {account_id, role})` |
| accounts.customer_id | `(:Customer)-[:OWNS]->(:Account)` |
| devices.device_id, access_type | `(:Device {device_id, access_type})` |
| account_devices.* | `(:Account)-[:USED_DEVICE {first_day, last_day, observations}]->(:Device)` |
| transfers.sender_id / receiver_id | start / end node of `[:TRANSFER]` |
| transfers.transfer_id, occurred_at, amount_rwf | properties of **one** TRANSFER relationship per row |

### 3.2 Prepare and import CSVs [5 marks]
1. Make the typed temporary copies and the import command:
   ```bat
   python step05_neo4j_prepare_import.py
   ```
   You see each header change, e.g. `account_id,customer_id,role => account_id:ID(Account),:IGNORE,role:string`,
   `owns.csv 248,000 rows`, `Source CSVs unchanged (MD5 before == after): True`, and the full
   command. It writes `neo4j\import_full.bat`.
2. **Stop Neo4j** (Ctrl+C in its console window). Then:
   ```bat
   neo4j\import_full.bat
   ```
   The command is `neo4j-admin database import full neo4j --overwrite-destination=true
   --id-type=integer --nodes=Customer=… --nodes=Account=… --nodes=Device=…
   --relationships=OWNS=… --relationships=USED_DEVICE=… --relationships=TRANSFER=…`.
   At the end Neo4j prints `IMPORT DONE in …` with **704600 nodes** and **20536900
   relationships**. Note the import time.
   📸 **3.2a** – IMPORT DONE with the counts and time.
3. Start Neo4j again (`bin\neo4j.bat console`), wait for `Started.`, then:
   ```bat
   python step06_neo4j_setup_checks.py
   ```
   It creates the three unique constraints and the TRANSFER `occurred_at` range index,
   waits until they are ONLINE (prints setup seconds), lists constraints and indexes, measures the
   store and transaction-log GB from NEO4J_HOME, and runs all checks: node counts 228,000 /
   248,000 / 228,600, OWNS 248,000, USED_DEVICE 285,600, TRANSFER 20,003,300, totals 704,600 and
   20,536,900, roles, one owner per account, unique transfer_id, and the audit totals. Must end in
   `ALL CHECKS PASSED`.
   📸 **3.2b** – constraints/indexes ONLINE + sizes. 📸 **3.2c** – the checks.
4. Remove the temporary copies:
   `python step06_neo4j_setup_checks.py --cleanup` 📸 (shows they are gone).

*If the import fails with "already contains data"*: the command already has
`--overwrite-destination=true`; make sure Neo4j is really stopped. *If counts look doubled*:
you imported twice without overwrite – rerun the .bat.

### 3.3 Inspect one account in both models [3 marks]
```bat
python step07_inspect_account.py 998
```
Shows the SQL JOIN query and the Cypher MATCH, then a side-by-side table: account 998 (person),
owner customer 998 (Kigali), device 998 (handset, days 0–29, 39 observations) and its first outgoing
transfer 113540 to merchant 240004 on 2026-09-01 08:43:29 CAT for 2,100 RWF – every field `True`.
📸 **3.3**. Explanation for the report is in `report\REPORT.md` §3.3.

---

## Milestone 4 – Routine business questions (Q1–Q3)

All query text is in `queries.py`. Run all questions for both engines (≈5–10 min; the SQL Q7
baseline is the slow part):
```bat
python step08_run_queries.py --engine both
```
Results: `results\outputs_pg.json`, `results\outputs_neo.json`, readable summaries
`results\examples_pg.txt` / `examples_neo.txt`, charts in `results\plots\`.
(To run only one engine or one question: `--engine pg` or `--only Q3`. The SQL Q7 baseline needs
≈25–60 s per bound-6 case; add `--q7 v2` to use the improved version when you only need the answers.)
Readable copies of every query for the report: `python export_queries.py` →
`sql\queries_q1_q7.sql` and `neo4j\queries_q1_q7.cypher`.

**Q1** – the starters completed: `AND occurred_at < %(end)s` / `AND t.occurred_at < $end`,
total `coalesce(sum(t.amount_rwf), 0)`. Hour = 09:45:00 ≤ t < 10:45:00 CAT converted in
Python (`mm_common.hour_bounds`). Expected: A 1 / 200,000; B 1 / 1,050,000; C 1 / 300,000;
D 1 / 45,000; E 1 / 40,000; F 1 / 30,000. 📸 **4.1** (six pairs).

**Q2** – 30 days, sums reconcile to 20,003,300 / 231,482,327,870 RWF.
Chart: `results\plots\q2_daily_pg.png`. 📸 **4.2** (results, totals check, chart).

**Q3** – row counts A 4, B 9, C 9, D 4, E 9, F 9. 📸 **4.3** (all six sets).

## Milestone 5 – Connected accounts (Q4–Q7)

**Q4** – the script first runs depths 4 and 6, prints a *prediction* for 8 and 10, then runs 8
and 10 and prints prediction vs actual. Totals: A 10/43/175/187, B 46/178/188/228,
C 146/483/832/1433, D 10/44/180/192, E 47/183/193/230, F 147/488/837/1426.
Chart `results\plots\q4_depth_pg.png`; supporting path `Account 998 – Device 228001 –
Account 24755`. 📸 **5.1** (24 comparisons from step09, plot, path, prediction lines).

**Q5** – one chain each for A, B, C; none for D, E, F. Example A: 998 → 8917 → 16836 → 24755,
10:00:00 / 10:00:40 / 10:01:20 CAT, 200,000 / 196,000 / 192,080 RWF. 📸 **5.2**.

**Q6** – A: one cycle of 4 (20000001–20000004), C: one cycle of 6; others none. 📸 **5.3**.

**Q7** – lengths: A 3/3, B none/5, C none/5, D 3/3, E none/5, F none/5 (bound 4 / bound 6),
each successful case with a verified path (`valid=True`). 📸 **5.4**.

---

## Milestone 6 – Correctness and performance

### 6.1 Comparison program [4 marks]
Both engines running:
```bat
python step09_compare.py --q7 v1
python step09b_independent_check.py
```
The first prints a 61-row status table (`MATCH` / `MATCH (length)`), the per-question summary
and `TOTAL 61/61 cases match; all supporting paths valid: True`. Saved to
`results\compare_61_v1.csv/.json`. The second recomputes the set-A device overlaps, the Q5
chain and the Q6 cycle from the CSV files in plain Python and prints `equal: True` against both
engines. 📸 **6.1a** status table, 📸 **6.1b** independent check.

*If something says MISMATCH*: the script prints rows only in PostgreSQL / only in Neo4j. The usual
causes are a wrong hour boundary or an import done without `--id-type=integer` (IDs become
strings). Fix, rerun, and describe the fix in the report.

### 6.2 Time a fixed selection [5 marks]
One database at a time:
1. Stop Neo4j (Ctrl+C). Close other heavy programs. Then
   ```bat
   python step10_benchmark.py --engine pg
   python step10b_plans.py --engine pg
   ```
2. Start Neo4j, stop PostgreSQL (`services.msc` → postgresql → Stop). Then
   ```bat
   python step10_benchmark.py --engine neo
   python step10b_plans.py --engine neo
   ```
3. `python step10_benchmark.py --summary` → median/min/max per case and the PostgreSQL/Neo4j
   median ratio. Raw runs: `results\bench_pg_v1.csv`, `bench_neo_cypher.csv`; plans in
   `results\plans\`.
📸 **6.2** summary table + one SQL plan + one PROFILE.

### 6.3 One SQL improvement [5 marks]
The Q7 v1 plan shows the recursive walk producing hundreds of thousands of (account, depth)
rows and millions of index probes at bound 6. The improvement (`Q7_SQL_V2`) searches 3 steps
forward from the review account and 3 steps backward from the destination and joins in the middle.
Start PostgreSQL (and Neo4j if you want the length recheck against Cypher too), then
```bat
python step11_sql_improvement.py
python step10b_plans.py --engine pg
python step10_benchmark.py --summary
```
Expected: all 12 lengths equal (`All 12 Q7 cases correct with version 2: True`); in our run bound 6
went from ≈25–33 s to ≈60–100 ms. 📸 **6.3** correctness, timing summary, before/after plans
(`results\plans\pg_Q7_B_b6_v1_before.txt` / `..._v2_after.txt`).

---

## Milestone 7 – Concurrent requests

Only one database running at a time. Each command runs 2 workloads × 4 client counts × 3
repetitions × ~15–20 s ≈ 8–10 minutes.
```bat
python step12_load_test.py --engine pg
python step12_load_test.py --engine neo
python step12_load_test.py --summary
python step12b_plot_scaling.py
```
While a 16-client test runs, open Task Manager → Performance (CPU at 100% is your saturation
evidence) 📸 **7.1a**. Every test line prints `active=<n>` (sessions busy, sampled from a
separate connection) 📸. The summary table has the 16 combinations (engine × workload ×
clients) 📸 **7.1b**. `results\plots\load_scaling.png` 📸 **7.2**.

---

## Milestone 8 – Decisions (report writing)

Open `report\REPORT.md`. Sections 8.1–8.3 are drafted from the deterministic results;
replace every **[YOUR …]** placeholder with your own timing/size numbers and screenshots.
Each member writes their own 150–200-word note (8.3) – the draft gives three topics that do not
overlap.

## Milestone 9 – Submit

1. Create a GitHub repository (e.g. `Mfulgence/mobile-money-project2`):
   ```bat
   git init
   git add .
   git commit -m "Project 2 mobile money PostgreSQL vs Neo4j"
   git branch -M main
   git remote add origin https://github.com/<you>/mobile-money-project2.git
   git push -u origin main
   ```
   `.gitignore` keeps `data\`, `neo4j_import\` and `config_local.py` out.
2. ZIP the same folder **without** `data\`, `neo4j_import\`, `.venv\`, `config_local.py`.
3. Final rerun with both services started:
   ```bat
   python step09_compare.py --q7 v2
   python step00_verify_generator.py
   ```
   📸 **9.2a** `TOTAL 61/61` + `UNCHANGED`.
4. Stop both services: Ctrl+C in the Neo4j window (or `bin\neo4j.bat stop`), and in an
   administrator cmd `net stop postgresql-x64-16`; check with `sc query postgresql-x64-16`
   (STATE: STOPPED) 📸 **9.2b**. Keep the database stores.
5. Export `report\REPORT.md` (with screenshots inserted) to one PDF in milestone order.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `psql` not recognised | `set PATH=%PATH%;C:\Program Files\PostgreSQL\16\bin` |
| `password authentication failed` | wrong password in `config_local.py`; for psql use `set PGPASSWORD=...` |
| `ZoneInfoNotFoundError: Africa/Kigali` | `pip install tzdata` |
| `\copy: could not open file` | run psql from the project folder; check `-v csvdir=` uses forward slashes |
| Neo4j import: Java errors / wrong Java | Neo4j 2025.x needs Java 21: `java -version`, set `JAVA_HOME` |
| Neo4j `SHORTEST` syntax error | Neo4j older than 5.21 – install 2025.x or 5.26 |
| Neo4j out of memory on Q2 / transfer_id check | raise `server.memory.heap.max_size` in `conf\neo4j.conf`, restart |
| Benchmark shows `timeout` | that is a result: it is recorded separately; mention it in the report |
| Neo4j Q2 or Q4 d10 very slow | run `python step10b_plans.py --engine neo`: Q4 should show a pruning/BFS var-length expand; Q2 builds 20 M datetimes – give Neo4j more heap and page cache |
| Load test hangs on Windows | run from cmd (not an IDE console); the script uses `freeze_support()` |
