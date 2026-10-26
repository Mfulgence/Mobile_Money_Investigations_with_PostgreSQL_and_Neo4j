-- Section 2.1  Five tables, one per captured stream. Every column NOT NULL.
-- Keys, foreign keys, CHECKs and indexes are added AFTER bulk loading (03_constraints_indexes.sql)
-- so that load time and index/constraint setup time can be recorded separately.
\timing on
DROP TABLE IF EXISTS transfers, account_devices, accounts, devices, customers CASCADE;

CREATE TABLE customers (
    customer_id  INTEGER NOT NULL,      -- customer identifier 1..228,000
    region       TEXT    NOT NULL       -- Kigali | Northern | Southern | Eastern | Western
);

CREATE TABLE accounts (
    account_id   INTEGER NOT NULL,      -- wallet identifier 1..248,000
    customer_id  INTEGER NOT NULL,      -- owning customer
    role         TEXT    NOT NULL       -- person | merchant | agent
);

CREATE TABLE devices (
    device_id    INTEGER NOT NULL,      -- device identifier 1..228,600
    access_type  TEXT    NOT NULL       -- handset | public_terminal
);

CREATE TABLE account_devices (
    account_id   INTEGER  NOT NULL,     -- wallet observed on the device
    device_id    INTEGER  NOT NULL,
    first_day    SMALLINT NOT NULL,     -- inclusive day number, 0 = 1 Sep 2026 CAT
    last_day     SMALLINT NOT NULL,     -- inclusive day number, 29 = 30 Sep 2026 CAT
    observations INTEGER  NOT NULL      -- number of sightings within [first_day, last_day]
);

CREATE TABLE transfers (
    transfer_id  BIGINT  NOT NULL,      -- unique event id
    sender_id    INTEGER NOT NULL,      -- paying wallet
    receiver_id  INTEGER NOT NULL,      -- receiving wallet
    occurred_at  BIGINT  NOT NULL,      -- Unix seconds (UTC epoch); display in Africa/Kigali
    amount_rwf   INTEGER NOT NULL       -- whole Rwandan francs
);
