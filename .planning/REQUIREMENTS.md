# Requirements: Transight AI — Multi-Route Expansion

**Defined:** 2026-04-02
**Core Value:** Accurate, real-time bus arrival predictions with delay indicators at every stop — proving the system scales beyond a single route.

## v1 Requirements

Requirements for the A1 Airport Flyer multi-route update. Each maps to roadmap phases.

### Data Pipeline

- [ ] **DATA-01**: A1 Airport Flyer route extracted from GTFS with agency filtering to avoid operator collisions
- [ ] **DATA-02**: A1 route and stops seeded in database for both directions (Bristol → Airport, Airport → Bristol)
- [ ] **DATA-03**: GTFS loader safely adds new routes without wiping existing Route 72 data
- [ ] **DATA-04**: BODS fetch refactored for multi-route efficiency (bulk or batched requests)

### Live Tracking

- [ ] **LIVE-01**: Fusion Engine tracks A1 vehicles via BODS with correct operator/line filtering
- [ ] **LIVE-02**: `is_near_major_stop()` refactored to be route-aware (not hardcoded to Route 72 stops)
- [ ] **LIVE-03**: Per-stop arrival time and delay indicator (on time / late / early) computed for all active routes

### Frontend

- [ ] **UI-01**: Route selector dropdown to switch between Route 72 and A1
- [ ] **UI-02**: Stop popup on map tap showing next arrival time and delay status for that stop
- [ ] **UI-03**: Mobile-first responsive layout — full-screen map with bottom sheet for route info and stop details
- [ ] **UI-04**: Desktop responsive layout — map with side panel for route info
- [ ] **UI-05**: Map viewport auto-adjusts (flyTo) when switching routes
- [ ] **UI-06**: Polished, modern UI evolving the current Transight theme with improved typography and spacing

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### ML & Analytics

- **ML-01**: Per-route XGBoost model training (A1 has different geometry than Route 72)
- **ML-02**: Crowd occupancy indicator via route-aware YOLO detection
- **ML-03**: Historical reliability scoring per stop

### Enhanced UX

- **UX-01**: Animated bus markers with direction indicators
- **UX-02**: PWA manifest for installable mobile experience
- **UX-03**: Multiple upcoming bus arrivals per stop (next 2-3)
- **UX-04**: Full stop detail page with history and trends

### Scale

- **SCALE-01**: Additional Bristol routes beyond 72 and A1

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dark/light theme toggle | Keep current theme, focus on polish not redesign |
| User accounts or authentication | Public dashboard, no login needed |
| Native mobile app | Web-first, responsive design covers mobile |
| Real-time chat or notifications | Not a communication tool |
| Additional routes beyond A1 | Prove multi-route pattern first, then scale |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | — | Pending |
| DATA-02 | — | Pending |
| DATA-03 | — | Pending |
| DATA-04 | — | Pending |
| LIVE-01 | — | Pending |
| LIVE-02 | — | Pending |
| LIVE-03 | — | Pending |
| UI-01 | — | Pending |
| UI-02 | — | Pending |
| UI-03 | — | Pending |
| UI-04 | — | Pending |
| UI-05 | — | Pending |
| UI-06 | — | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 0
- Unmapped: 13

---
*Requirements defined: 2026-04-02*
*Last updated: 2026-04-02 after initial definition*
