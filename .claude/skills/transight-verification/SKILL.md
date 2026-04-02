---
name: transight-verification
description: Use before finishing work or when debugging regressions to choose the smallest relevant verification steps for Transight
---

# Transight Verification Skill

Use this skill to map changes to the right checks.

## Verification Matrix

- Backend logic in `server/`: run the smallest relevant `python test_*.py` helper or targeted Flask smoke test.
- Frontend code in `client/`: run `npm run build`; run `npm run lint` for code or style edits.
- Data-loading or route-shape changes: inspect `/api/routes`, `/api/routes/<route_id>/stops`, and `/api/status/<route_id>`.
- External API behavior: verify both the real-data path and fallback behavior when credentials or feeds are unavailable.

## High-Signal Checks

```bash
cd client
npm run build
npm run lint
```

```bash
cd server
python test_api.py
python test_status.py
python test_route2.py
```

## Gotchas

- A passing frontend build does not prove the backend data shape is still correct.
- A reachable Flask endpoint does not prove the Fusion Engine write loop is healthy.
- `seed.py` is not a verification command; it is a destructive reset.

## Final Report

Always report:

- what you ran
- what you could not run
- what still needs manual QA
