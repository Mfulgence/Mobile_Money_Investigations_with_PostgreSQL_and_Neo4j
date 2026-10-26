#!/usr/bin/env bash
# Neo4j must be STOPPED: bin/neo4j stop
set -e
cd "C:\neo4j"
date
time bin/neo4j-admin database import full neo4j \
  --overwrite-destination=true \
  --id-type=integer \
  --nodes=Customer="C:\mobile_money_project\neo4j_import\customers.csv" \
  --nodes=Account="C:\mobile_money_project\neo4j_import\accounts.csv" \
  --nodes=Device="C:\mobile_money_project\neo4j_import\devices.csv" \
  --relationships=OWNS="C:\mobile_money_project\neo4j_import\owns.csv" \
  --relationships=USED_DEVICE="C:\mobile_money_project\neo4j_import\used_device.csv" \
  --relationships=TRANSFER="C:\mobile_money_project\neo4j_import\transfers.csv" \
  --report-file=import.report
date
