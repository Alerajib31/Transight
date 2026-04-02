# Testing Patterns

**Analysis Date:** 2026-04-02

## Test Framework

**Runner:**
- Backend: Flask's built-in test client via `app.test_client()`
- Frontend: None configured (no Jest, Vitest, or similar); manual browser testing only
- Config: None (no `pytest.ini`, `conftest.py`, or test configuration files)

**Assertion Library:**
- Backend: Native Python assertions and print-based debugging
- Frontend: N/A (no test framework)

**Run Commands:**
```bash
# Backend tests
cd server
python test_api.py      # Test stops and status endpoints
python test_status.py   # Test status API response structure
python test_route2.py   # Test inbound route status

# Frontend
cd client
npm run lint            # Run ESLint (code quality, not functional testing)
npm run build           # Verify build succeeds
npm run dev             # Manual browser testing
```

## Test File Organization

**Location:**
- Backend: Test files co-located in `server/` root directory next to application code
- Frontend: No test files present; all testing is manual

**Naming:**
- Pattern: `test_*.py` (e.g., `test_api.py`, `test_status.py`, `test_route2.py`)
- Corresponds to endpoints being tested

**Structure:**
```
server/
├── app.py                    (Main Flask application)
├── models.py                 (Database models)
├── test_api.py              (Tests for /api/routes/<id>/stops and /api/status/<id>)
├── test_status.py           (Tests for /api/status/<id> response)
└── test_route2.py           (Tests for inbound route /api/status/2)
```

## Test Structure

**Test pattern in Python:**

```python
# server/test_api.py
"""Test API endpoints"""
from app import app

with app.test_client() as client:
    # Test stops API
    print("Testing /api/routes/1/stops...")
    resp = client.get('/api/routes/1/stops')
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.get_json()
        stops = data.get('stops', [])
        print(f"Total stops: {len(stops)}")
        
        if stops:
            first = stops[0]
            print(f"First stop keys: {list(first.keys())}")
            print(f"First stop: {first}")
```

**Characteristics:**
- No test framework (no classes, no setup/teardown methods)
- Direct Flask test client usage: `app.test_client()`
- Print-based output for assertion validation (stdout inspection)
- Manual assertion via `if` statements on response status/data
- Inline comments describe test intent

## Mocking

**Framework:** None; tests use actual database and in-process Flask

**Patterns:**
- No mocking of external APIs (BODS, TomTom, GTFS)
- No fixtures for test data setup
- Database state is from `seed.py` or manual row insertion
- API responses tested against live BODS/TomTom/GTFS data when keys available

**What NOT to Mock:**
- Flask routes (tests run in-process)
- Database (tests use real PostgreSQL instance)
- External APIs are only avoided by setting API keys to empty/missing (graceful fallback testing)

## Fixtures and Factories

**Test Data:**
- None defined in codebase
- Tests rely on existing database rows from `seed.py` or data created by `generate_synthetic_data.py`
- Route IDs hardcoded: tests check route 1 (outbound) and route 2 (inbound)

**Location:**
- Not applicable; no factories or fixtures are used

**Pattern when creating test data:**
```bash
# From CLAUDE.md:
cd server
python setup_db.py           # Initialize schema
python seed.py               # Insert route definitions (destructive, drops tables)
python generate_synthetic_data.py  # Add synthetic BusLog rows
```

## Coverage

**Requirements:** None enforced; no CI validation

**View Coverage:**
- Not applicable; coverage tools not configured

**Current state:**
- Backend has 3 test scripts covering 5 endpoints; coverage ~25% of API surface
- Frontend has no test coverage
- Testing is integration-level (full stack, real DB)

## Test Types

**Unit Tests:**
- Not present; no isolated function testing
- Helpers like `parse_gtfs_time()`, `haversine()` not tested directly
- Would require extracting pure functions and adding unit test framework

**Integration Tests:**
- 3 scripts that test API endpoints end-to-end
- `test_api.py`: Tests `/api/routes/1/stops` and `/api/status/1`
- `test_status.py`: Tests `/api/status/1` response keys and bus data
- `test_route2.py`: Tests `/api/status/2` for inbound route
- All use live database state

Example from `server/test_status.py`:
```python
"""Test status API response"""
from app import app
import json

with app.test_client() as client:
    resp = client.get('/api/status/1')
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.get_json()
        print(f"\nKeys: {list(data.keys())}")
        print(f"Bus available: {data.get('bus_available')}")
        print(f"Bus count: {data.get('bus_count')}")
        print(f"Buses: {len(data.get('buses', []))}")
        
        if data.get('buses'):
            for i, bus in enumerate(data['buses']):
                print(f"\nBus #{i+1}:")
                print(f"  vehicle_id: {bus.get('vehicle_id')}")
                print(f"  eta: {bus.get('eta')}")
                print(f"  position: {bus.get('position')}")
                print(f"  delay_minutes: {bus.get('delay_minutes')}")
```

**E2E Tests:**
- Not automated; manual browser testing via `npm run dev` in `client/`
- User journey: Select route → Observe live bus markers on map → Check ETA dashboard
- Covers: Route selection, API polling, map rendering, theme toggle

**E2E Testing Procedure (Manual):**
```bash
# Terminal 1: Backend
cd server
python setup_db.py
python seed.py
python generate_synthetic_data.py
python app.py

# Terminal 2: Frontend
cd client
npm run dev
```

1. Browser opens http://localhost:5173
2. Verify routes load in dropdown
3. Select route 1 (outbound)
4. Confirm map centers on bus position
5. Check ETA updates every 10 seconds (POLL_INTERVAL)
6. Toggle theme dark/light
7. Switch routes and repeat
8. Select different buses in multi-bus scenarios
9. Verify historical trends graph loads

## Common Patterns

**Async Testing:**
- Not used; tests are synchronous Flask test client calls
- Would require async test framework (e.g., pytest-asyncio) for async function testing

**Error Testing:**
- No dedicated error test scenarios
- 404 responses tested implicitly (routes not seeded would return errors)
- Would test: missing route, invalid bus position, API key failures, database disconnection

Example structure if error testing were added:
```python
# Not currently in codebase, example of how it could look:
with app.test_client() as client:
    # Test missing route
    resp = client.get('/api/status/99999')
    assert resp.status_code == 404
    assert resp.get_json().get('error') == 'Route not found'
```

## Manual Verification Commands

From `CLAUDE.md` "Verification Expectations":

**Frontend change:**
```bash
cd client
npm run build   # Verify TypeScript/JSX compiles
npm run lint    # Run ESLint checks
```

**Backend/API change:**
```bash
cd server
python test_api.py        # Quick smoke test
python test_status.py     # Endpoint data structure
python test_route2.py     # Inbound route test
```

**Data pipeline change:**
```bash
cd server
python generate_synthetic_data.py  # Populate test data
python test_status.py              # Verify ETA calculation
```

**Route or ETA changes:**
```bash
cd server
curl http://localhost:5000/api/status/1                      # Manual HTTP test
curl http://localhost:5000/api/routes/1/predictions          # Stop predictions
```

## Frontend Testing Strategy (Recommended Pattern)

While not yet implemented, tests should follow this pattern when added:

**Test structure:**
```javascript
// client/src/App.test.jsx (recommended if Jest/Vitest added)
import { render, screen, waitFor } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('fetches and displays routes', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Route/)).toBeInTheDocument();
    });
  });
});
```

**Key areas to test:**
- Route selection triggers status/stops/history fetches
- Polling interval (10 seconds) for status updates
- Error state displays when API fails
- Theme toggle persists to localStorage
- Bus marker colors reflect delay_minutes correctly
- Stop predictions calculate properly with live data

## Database Testing Notes

**Setup:**
```bash
cd server
python setup_db.py     # Create schema
python seed.py         # Insert Route definitions (destructive)
```

**Teardown:**
- Not automated; `seed.py` is idempotent (drops and recreates)
- To reset: `python seed.py` again
- ⚠️ **WARNING:** `seed.py` is destructive; never run without explicit approval

**Test isolation:**
- Tests share single database instance
- No transaction rollback between tests
- BusLog data accumulates across test runs (not a problem; tests query latest rows)

## Performance Testing

**Not present; no load/stress tests**

**Manual checks:**
- Fusion Engine polling interval: `FUSION_INTERVAL = 10` seconds
- Frontend polling intervals: `POLL_INTERVAL = 10_000` ms, `HISTORY_POLL_INTERVAL = 30_000` ms
- Database queries: All use indexes on `route_id` and `timestamp`

---

*Testing analysis: 2026-04-02*
