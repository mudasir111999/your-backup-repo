# Generation Specification

## Task
Generate a synthetic dataset about airplane/airline ticket data.
- Table name: airline
- Number of rows: 50

## Columns
- airline_id: Identifier for airline (integer, unique per airline)
- ticket_price: Ticket price for an unspecified flight (decimal, simulating realistic prices between $50 and $1200)

## Requirements
- No provided schema; inferred from prompt.
- 50 rows exactly.
- Deterministic (random seed: 42).
- airline_id values randomly sampled unique integers in [1000,9999].
- ticket_price drawn from a normal distribution (mu=400, sigma=200), clipped [50,1200] and rounded to 2 decimals.

## Assumptions
- airline_id: int, unique, between 1000 and 9999.
- ticket_price: float, simulating possible ticket prices for economy–premium tickets.

## Random seed
- All random generation uses numpy/pandas with seed=42 for repeatability.