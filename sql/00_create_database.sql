-- Section 1.1  Run once as a superuser in psql:  psql -U postgres -f sql/00_create_database.sql
CREATE DATABASE mobile_money;
ALTER DATABASE mobile_money SET timezone TO 'Africa/Kigali';

-- Memory settings used for every measurement (adjust to your RAM, then restart PostgreSQL).
-- Values below are for a 16 GB laptop; on 8 GB use shared_buffers=2GB, effective_cache_size=4GB.
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '8GB';
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET max_wal_size = '8GB';
ALTER SYSTEM SET timezone = 'Africa/Kigali';
-- restart the service now (Windows: services.msc -> postgresql-x64-16 -> Restart)
