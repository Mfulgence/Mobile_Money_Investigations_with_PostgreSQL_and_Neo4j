@echo off
REM Neo4j must be STOPPED:  bin\neo4j.bat stop   (or stop the Windows service)
cd /d "C:\neo4j"
echo Import started %date% %time%
bin\neo4j-admin.bat database import full neo4j ^
  --overwrite-destination=true ^
  --id-type=integer ^
  --nodes=Customer="C:\mobile_money_project\neo4j_import\customers.csv" ^
  --nodes=Account="C:\mobile_money_project\neo4j_import\accounts.csv" ^
  --nodes=Device="C:\mobile_money_project\neo4j_import\devices.csv" ^
  --relationships=OWNS="C:\mobile_money_project\neo4j_import\owns.csv" ^
  --relationships=USED_DEVICE="C:\mobile_money_project\neo4j_import\used_device.csv" ^
  --relationships=TRANSFER="C:\mobile_money_project\neo4j_import\transfers.csv" ^
  --report-file="C:\neo4j\import.report"
echo Import finished %date% %time%
