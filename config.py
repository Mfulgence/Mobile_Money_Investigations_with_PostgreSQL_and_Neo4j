"""Project settings. Secrets are placeholders: put real values in config_local.py
(git-ignored, copy config_local.example.py) or in environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("MM_DATA_DIR", ROOT / "data"))           # source CSVs (kept local)
IMPORT_DIR = Path(os.environ.get("MM_IMPORT_DIR", ROOT / "neo4j_import"))  # temporary typed copies
RESULTS_DIR = ROOT / "results"
PLOTS_DIR = RESULTS_DIR / "plots"

PG = dict(
    host=os.environ.get("PGHOST", "localhost"),
    port=int(os.environ.get("PGPORT", "5432")),
    dbname=os.environ.get("PGDATABASE", "mobile_money"),
    user=os.environ.get("PGUSER", "postgres"),
    password=os.environ.get("PGPASSWORD", "CHANGE_ME"),
)
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "CHANGE_ME")
NEO4J_DATABASE = "neo4j"
# Folder where Neo4j is installed, e.g. C:/neo4j/neo4j-community-2025.09.0 (used to measure store size)
NEO4J_HOME = Path(os.environ.get("NEO4J_HOME", "C:/neo4j/neo4j-community"))

try:  # local overrides that never go to GitHub
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass

for _d in (RESULTS_DIR, PLOTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
