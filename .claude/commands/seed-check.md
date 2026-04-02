---
description: Inspect database and route table health without running the destructive seed script
model: haiku
---

# Seed Check

Inspect the current database state without reseeding.

## Instructions

1. Do not run `python seed.py` or `python server/seed.py`.
2. Use the smallest safe command set to check database reachability from the current repo.
3. Report row counts for `Route`, `BusLog`, `Stop`, and `RouteStop` if the database is reachable.
4. If the database is not reachable, explain the failure and stop rather than guessing.
5. If reseeding truly seems necessary, warn clearly that `seed.py` drops all data before suggesting it.

## Output

Return:

- whether the database is reachable
- table counts or the exact blocking error
- whether a reseed is actually necessary
- the safest next step
