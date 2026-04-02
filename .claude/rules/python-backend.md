# Glob: server/**/*.py

## Python Backend Rules

- Use `logger.info()` / `logger.error()` instead of `print()` in production code.
- Add type hints to new or significantly edited function signatures when practical.
- Keep constants at module top in UPPERCASE.
- `server/seed.py` drops and recreates tables; never run or suggest it casually.
- Preserve no-key and stale-data fallback paths when touching BODS, TomTom, GTFS, or ETA logic.
- When changing Flask responses, keep `/api/routes`, `/api/status/<route_id>`, `/api/routes/<route_id>/stops`, and `/api/routes/<route_id>/predictions` consistent.
