-- Row count
SELECT COUNT(*) AS row_count FROM improve.airline;

-- Unique airline_id check
SELECT COUNT(DISTINCT airline_id) AS unique_airline_ids FROM improve.airline;

-- ticket_price min/max
SELECT MIN(ticket_price) AS min_price, MAX(ticket_price) AS max_price FROM improve.airline;

-- Null check
SELECT COUNT(*) AS airline_id_nulls FROM improve.airline WHERE airline_id IS NULL;
SELECT COUNT(*) AS ticket_price_nulls FROM improve.airline WHERE ticket_price IS NULL;