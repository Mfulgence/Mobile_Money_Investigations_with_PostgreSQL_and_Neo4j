# Copy this file to config_local.py and fill in YOUR values. config_local.py is git-ignored.
from pathlib import Path

PG = dict(host="localhost", port=5432, dbname="mobile_money", user="postgres", password="YOUR_PG_PASSWORD")
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "YOUR_NEO4J_PASSWORD"
NEO4J_HOME = Path(r"C:\neo4j\neo4j-community-2025.09.0")
# DATA_DIR = Path(r"D:\mm_data")   # optional: put the 1 GB of CSVs on another drive
