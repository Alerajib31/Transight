# Transight AI - 1-Day MVP Plan

## Goal

Ship the current Route 72 MVP in one continuous day of work. Keep the existing Flask + React + PostgreSQL stack, preserve the current endpoints, and focus on a stable runnable app rather than an architecture rewrite.

Status: this is the frozen handoff state for the current MVP, not a rewrite backlog.

## In Scope

- Route 72 only
- Flask backend, React frontend, PostgreSQL, YOLO crowd count, XGBoost ETA
- Stop-by-stop ETA display from the current backend responses
- Schedule-only fallback when no live bus is active
- Startup and environment documentation that matches the real code

## Day Plan

1. Start the backend cleanly with the local PostgreSQL URL and required API keys in shell env vars.
2. Verify the core endpoints:
   - `/`
   - `/api/routes`
   - `/api/status/1`
   - `/api/routes/1/predictions`
3. Start the frontend and confirm the Route 72 dashboard loads.
4. Verify the current UI shows:
   - current ETA
   - passenger count
   - stop-by-stop predicted arrivals
   - schedule fallback when no live bus is available
5. Keep the docs in sync with the working startup flow.

## Acceptance Criteria

- Backend boots without manual code changes.
- Frontend loads on `localhost:3000` and talks to the Flask API through the Vite proxy.
- Route 72 predictions render correctly with live or schedule-only data.
- README and env examples match the actual launch flow.
- No work is started on FastAPI, Celery, Redis, HERE Maps, WebSockets, PostGIS, or mobile packaging during this 1-day pass.

## Future Work

The following remain out of scope for the one-day MVP and should stay in a later roadmap:
- multi-bus / multi-route expansion
- HERE Maps migration
- FastAPI migration
- Celery + Redis orchestration
- WebSocket real-time push
- ONNX conversion
- PWA / Capacitor mobile app
