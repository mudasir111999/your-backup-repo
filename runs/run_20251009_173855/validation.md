# Pre-DB Validation

- Row count: 50 (expected 50)
- Unique airline_id values: 50 (expected 50)
- All ticket_prices are floats: True
- All ticket_prices between 50 and 1200: True
- No null values: True

PASS: True
# MotherDuck Post-load Validation

```sql
-- Row count
SELECT COUNT(*) AS row_count FROM improve.airline;

-- Unique airline_id check
SELECT COUNT(DISTINCT airline_id) AS unique_airline_ids FROM improve.airline;

-- ticket_price min/max
SELECT MIN(ticket_price) AS min_price, MAX(ticket_price) AS max_price FROM improve.airline;

-- Null check
SELECT COUNT(*) AS airline_id_nulls FROM improve.airline WHERE airline_id IS NULL;
SELECT COUNT(*) AS ticket_price_nulls FROM improve.airline WHERE ticket_price IS NULL;
```

Results:

- Row count: +-----------+
| row_count |
|  NUMBER   |
+-----------+
|    50     |
+-----------+
- Unique airline_id: +--------------------+
| unique_airline_ids |
|       NUMBER       |
+--------------------+
|         50         |
+--------------------+
- ticket_price min/max: +-----------+-----------+
| min_price | max_price |
|  NUMBER   |  NUMBER   |
+-----------+-----------+
|   50.0    |  924.89   |
+-----------+-----------+
- Airline_id NULLs: +------------------+
| airline_id_nulls |
|      NUMBER      |
+------------------+
|        0         |
+------------------+
- Ticket_price NULLs: +--------------------+
| ticket_price_nulls |
|       NUMBER       |
+--------------------+
|         0          |
+--------------------+