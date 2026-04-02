# Glob: **

## Transight Workflow

- Start with the smallest reliable slice of the problem: backend pipeline, frontend dashboard, data loading, or verification.
- Prefer focused changes over broad rewrites; `server/app.py` and `client/src/App.jsx` already carry a lot of project logic.
- Before finishing, map touched files to the smallest relevant verification commands and run them when possible.
- If a task looks destructive, especially anything involving `seed.py`, stop and confirm intent first.
- If the user reports a live-data issue, keep fallback behavior in scope as well as the happy path.
