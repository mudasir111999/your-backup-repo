CREATE SCHEMA IF NOT EXISTS improve;


CREATE OR REPLACE TABLE improve.airline AS
SELECT * FROM read_csv_auto('./runs/outputs/run_20251009_173855/csv/airline.csv',
  SAMPLE_SIZE = -1,
  DATEFORMAT = 'YYYY-MM-DD',
  TIMESTAMPFORMAT = 'YYYY-MM-DD HH:MM:SS',
  HEADER = TRUE
);
