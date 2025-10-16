# Load Report

## Target Schema & Table
- Schema: improve
- Table: airline

## DDL/DML
- CREATE SCHEMA IF NOT EXISTS improve;
- CREATE OR REPLACE TABLE improve.airline AS SELECT * FROM read_csv_auto('./runs/outputs/run_20251009_173855/csv/airline.csv', ...);

## Row Counts (MotherDuck)
- airline: 50

## Validation Summary
- Row count matches: PASS
- Unique airline_id (PK): PASS
- ticket_price range: PASS (50.0 - 924.89)
- No nulls: PASS

## Mitigations
- None required.

## Load Time
- Table loaded by bulk operation via read_csv_auto.