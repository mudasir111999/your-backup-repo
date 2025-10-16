# Data Dictionary

| Column        | Type    | Nullable | Constraints         | Description                   | Example |
|---------------|---------|----------|---------------------|-------------------------------|---------|
| airline_id    | INT     | False    | PRIMARY KEY, Unique | Airline identifier            | 1845    |
| ticket_price  | FLOAT   | False    | >=50, <=1200        | Ticket price in USD           | 328.50  |