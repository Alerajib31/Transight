---
description: Audit a Transight route end-to-end from route config to status and predictions
model: haiku
---

# Route Audit

Audit a route end-to-end before making changes.

## Instructions

1. Use the route the user mentioned. If none was mentioned, default to the currently most relevant route in context.
2. Inspect the route metadata, stops endpoint, predictions endpoint, and latest status response.
3. Call out:
   - whether the route exists
   - whether stops and schedules are loaded
   - whether live bus data is present
   - whether ETA and delay fields look plausible
4. If any check fails, identify the narrowest likely failure point: route seed data, GTFS loading, live data parsing, ETA logic, or frontend consumption.
5. Do not run destructive scripts while auditing.

## Output

Summarize:

- route health
- likely failure point if any
- files or systems to inspect next
