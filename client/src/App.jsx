/**
 * Transight AI — Phase 2 MVP Frontend
 *
 * Features:
 *   • Route Selector with origin/destination display
 *   • Live dashboard: ETA to destination, passenger count
 *   • React-Leaflet map with bus, route visualization
 */

import { useState, useEffect, useCallback } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import HistoricalTrends from "./HistoricalTrends.jsx";

/* ── Fix Leaflet's default icon paths (Vite bundling workaround) ────── */
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

/* ── Bus marker helpers ────────────────────────────────────────────── */
function getBusMarkerColors(delayMinutes) {
  if (delayMinutes == null) return { bg: '#2563eb,#1d4ed8', glow: 'rgba(37,99,235,.7)' };
  if (delayMinutes <= 1) return { bg: '#10b981,#059669', glow: 'rgba(16,185,129,.7)' };
  if (delayMinutes <= 5) return { bg: '#f59e0b,#d97706', glow: 'rgba(245,158,11,.7)' };
  return { bg: '#ef4444,#dc2626', glow: 'rgba(239,68,68,.7)' };
}

function createBusIcon(delayMinutes) {
  const { bg, glow } = getBusMarkerColors(delayMinutes);
  return new L.DivIcon({
    className: "bus-marker",
    html: `<div style="
      width:32px;height:32px;border-radius:50%;
      background:linear-gradient(135deg,${bg});
      border:3px solid #fff;box-shadow:0 0 16px ${glow};
      display:flex;align-items:center;justify-content:center;
      font-size:16px;animation:pulse 2s infinite;
    ">🚌</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

const originIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width:28px;height:28px;border-radius:50%;
    background:linear-gradient(135deg,#10b981,#059669);
    border:3px solid #fff;box-shadow:0 0 12px rgba(16,185,129,.6);
    display:flex;align-items:center;justify-content:center;
    font-size:14px;font-weight:bold;color:white;
  ">A</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

const destIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width:28px;height:28px;border-radius:50%;
    background:linear-gradient(135deg,#ef4444,#dc2626);
    border:3px solid #fff;box-shadow:0 0 12px rgba(239,68,68,.6);
    display:flex;align-items:center;justify-content:center;
    font-size:14px;font-weight:bold;color:white;
  ">B</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

const stopIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width:10px;height:10px;border-radius:50%;
    background:#3b82f6;
    border:2px solid #fff;box-shadow:0 0 4px rgba(59,130,246,.8);
  "></div>`,
  iconSize: [10, 10],
  iconAnchor: [5, 5],
});

const API_BASE = "/api";
const POLL_INTERVAL = 10_000; // 10 seconds
const HISTORY_POLL_INTERVAL = 30_000;
const A1_BRISTOL_TERMINALS = new Set([
  "Bristol Bus Station",
  "Bristol City Centre (Marlborough St)",
]);

function getBusKey(bus, index = 0) {
  return `${bus.operator || "unknown"}:${bus.vehicle_id || `bus-${index}`}`;
}

function getBusLabel(bus, index = 0) {
  const operator = bus.operator && bus.operator !== "unknown" ? bus.operator : "Unknown operator";
  const vehicle = bus.vehicle_id && bus.vehicle_id !== "unknown" ? bus.vehicle_id : `Bus ${index + 1}`;
  return `${operator} • ${vehicle}`;
}

function getDisplayTerminalName(routeName, terminalName) {
  if (routeName === "A1" && A1_BRISTOL_TERMINALS.has(terminalName)) {
    return "Bristol";
  }
  return terminalName;
}

function formatScheduleTime(value) {
  if (!value) {
    return null;
  }

  const parts = String(value).split(":");
  if (parts.length < 2) {
    return value;
  }

  const hour = Number.parseInt(parts[0], 10);
  const minute = Number.parseInt(parts[1], 10);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
    return value;
  }

  const normalizedHour = ((hour % 24) + 24) % 24;
  return `${String(normalizedHour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function buildBoundsPoints(routePath, originPos, destPos) {
  const points = [];

  for (const point of routePath || []) {
    if (
      Array.isArray(point)
      && point.length === 2
      && Number.isFinite(point[0])
      && Number.isFinite(point[1])
    ) {
      points.push(point);
    }
  }

  for (const point of [originPos, destPos]) {
    if (
      Array.isArray(point)
      && point.length === 2
      && Number.isFinite(point[0])
      && Number.isFinite(point[1])
    ) {
      points.push(point);
    }
  }

  return points;
}

function MapViewportController({ fitKey, fitPoints, resizeKey }) {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    if (!container || typeof ResizeObserver === "undefined") {
      return undefined;
    }

    const observer = new ResizeObserver(() => {
      map.invalidateSize({ pan: false });
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [map]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      map.invalidateSize({ pan: false });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [map, resizeKey]);

  useEffect(() => {
    if (!fitPoints.length) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      const bounds = L.latLngBounds(fitPoints);
      if (!bounds.isValid()) {
        return;
      }

      map.invalidateSize({ pan: false });
      if (fitPoints.length === 1) {
        map.setView(fitPoints[0], 14, { animate: false });
        return;
      }

      map.fitBounds(bounds, {
        padding: [36, 36],
        maxZoom: 13,
        animate: false,
      });
    }, 0);

    return () => window.clearTimeout(timer);
  }, [map, fitKey]);

  return null;
}

function getStoredTheme() {
  try {
    const saved = localStorage.getItem("transight-theme");
    return saved === "light" || saved === "dark" ? saved : null;
  } catch {
    return null;
  }
}

function saveTheme(theme) {
  try {
    localStorage.setItem("transight-theme", theme);
  } catch {
    // Ignore storage failures and keep the in-memory theme state.
    return;
  }
}

// =====================================================================
// Component: App
// =====================================================================
export default function App() {
  const [theme, setTheme] = useState(() => {
    const saved = getStoredTheme();
    if (saved) return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e) => {
      if (getStoredTheme()) return;
      setTheme(e.matches ? "dark" : "light");
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const toggleTheme = () => setTheme((t) => t === "dark" ? "light" : "dark");

  const [routes, setRoutes] = useState([]);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [buses, setBuses] = useState([]); // Array of all buses
  const [routePredictions, setRoutePredictions] = useState({
    stops: [],
    service_time: null,
    current_delay: null,
    is_live: false,
  });
  const [route, setRoute] = useState(null);
  const [stops, setStops] = useState([]);
  const [routeHistory, setRouteHistory] = useState({
    points: [],
    stats: {},
    sample_count: 0,
    vehicle_id: null,
    hours: 6,
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedBusKey, setSelectedBusKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /* ── Fetch routes on mount ─────────────────────────────────────── */
  useEffect(() => {
    fetch(`${API_BASE}/routes`)
      .then((r) => r.json())
      .then((data) => {
        setRoutes(data);
        if (data.length > 0) setSelectedRouteId(data[0].id);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  /* ── Poll status for selected route ────────────────────────────── */
  const fetchStatus = useCallback(() => {
    if (!selectedRouteId) return;
    // Add cache-busting timestamp
    fetch(`${API_BASE}/status/${selectedRouteId}?_t=${Date.now()}`)
      .then((r) => {
        if (!r.ok) throw new Error("No data yet");
        return r.json();
      })
      .then((data) => {
        let nextBuses = [];
        if (data.buses && Array.isArray(data.buses)) {
          nextBuses = data.buses;
        } else {
          if (data.bus_available === false) {
            nextBuses = [];
          } else if (data.status) {
            nextBuses = [{
              vehicle_id: "unknown",
              position: { lat: data.status.bus_lat, lng: data.status.bus_lng },
              eta: data.status.predicted_eta,
              passenger_count: data.status.passenger_count,
              traffic_delay: data.status.traffic_delay,
              scheduled_service_time: data.status.scheduled_service_time,
              delay_minutes: data.status.delay_minutes,
              eta_method: data.eta_method,
            }];
          } else {
            nextBuses = [];
          }
        }
        setBuses(nextBuses);
        setSelectedBusKey((prev) => {
          if (nextBuses.length === 0) {
            return "";
          }

          const stillExists = nextBuses.some((bus, index) => getBusKey(bus, index) === prev);
          return stillExists ? prev : getBusKey(nextBuses[0], 0);
        });
        setRoute(data.route);
        setError(null);
      })
      .catch((e) => {
        setBuses([]);
        setError(e.message);
      });
  }, [selectedRouteId]);

  /* ── Fetch stops for selected route ────────────────────────────── */
  const fetchStops = useCallback(() => {
    if (!selectedRouteId) return;
    fetch(`${API_BASE}/routes/${selectedRouteId}/stops`)
      .then((r) => r.json())
      .then((data) => {
        setStops(data.stops || []);
      })
      .catch(() => {
        setStops([]);
      });
  }, [selectedRouteId]);

  const fetchHistory = useCallback(() => {
    if (!selectedRouteId) return;

    const selected =
      buses.find((bus, index) => getBusKey(bus, index) === selectedBusKey) ||
      buses[0] ||
      null;

    const params = new URLSearchParams({
      hours: "6",
      limit: "36",
    });

    if (selected?.vehicle_id && selected.vehicle_id !== "unknown") {
      params.set("vehicle_id", selected.vehicle_id);
    }

    setHistoryLoading(true);
    fetch(`${API_BASE}/routes/${selectedRouteId}/history?${params.toString()}&_t=${Date.now()}`)
      .then((r) => {
        if (!r.ok) throw new Error("No historical data yet");
        return r.json();
      })
      .then((data) => {
        setRouteHistory({
          points: data.points || [],
          stats: data.stats || {},
          sample_count: data.sample_count ?? 0,
          vehicle_id: data.vehicle_id ?? null,
          hours: data.hours ?? 6,
        });
      })
      .catch(() => {
        setRouteHistory({
          points: [],
          stats: {},
          sample_count: 0,
          vehicle_id: selected?.vehicle_id ?? null,
          hours: 6,
        });
      })
      .finally(() => setHistoryLoading(false));
  }, [selectedRouteId, buses, selectedBusKey]);

  const fetchPredictions = useCallback(() => {
    if (!selectedRouteId) return;
    fetch(`${API_BASE}/routes/${selectedRouteId}/predictions?_t=${Date.now()}`)
      .then((r) => {
        if (!r.ok) throw new Error("No stop predictions yet");
        return r.json();
      })
      .then((data) => {
        setRoutePredictions({
          stops: data.stops || [],
          service_time: data.service_time ?? null,
          current_delay: data.current_delay ?? null,
          is_live: Boolean(data.is_live),
        });
      })
      .catch(() => {
        setRoutePredictions({
          stops: [],
          service_time: null,
          current_delay: null,
          is_live: false,
        });
      });
  }, [selectedRouteId]);

  useEffect(() => {
    fetchStops();
  }, [fetchStops]);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [fetchStatus]);

  useEffect(() => {
    fetchPredictions();
    const id = setInterval(fetchPredictions, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [fetchPredictions]);

  useEffect(() => {
    const initialLoad = setTimeout(fetchHistory, 0);
    const id = setInterval(fetchHistory, HISTORY_POLL_INTERVAL);
    return () => {
      clearTimeout(initialLoad);
      clearInterval(id);
    };
  }, [fetchHistory]);


  /* ── Derived values ────────────────────────────────────────────── */
  const displayOriginName = route ? getDisplayTerminalName(route.route_name, route.origin_name) : "--";
  const displayDestName = route ? getDisplayTerminalName(route.route_name, route.destination_name) : "--";
  const selectedBusIndex = buses.findIndex((bus, index) => getBusKey(bus, index) === selectedBusKey);
  const selectedBus =
    (selectedBusIndex >= 0 ? buses[selectedBusIndex] : null) ||
    buses[0] ||
    null;
  const activeBus = selectedBus;
  const eta = activeBus?.eta ?? "--";
  const passengers = activeBus?.passenger_count ?? 0;
  const highDemand = passengers > 15;
  const activeServiceTime = activeBus?.scheduled_service_time ?? routePredictions.service_time;
  const displayStopPredictions =
    activeBus?.stop_predictions?.length > 0
      ? activeBus.stop_predictions
      : routePredictions.stops;
  const getStopPrediction = (routeStop) =>
    displayStopPredictions.find((prediction) => {
      if (prediction.stop_id && routeStop.stop?.stop_id) {
        return prediction.stop_id === routeStop.stop.stop_id;
      }

      return (
        prediction.stop_sequence === routeStop.sequence ||
        prediction.stop_sequence === routeStop.sequence + 1
      );
    }) || null;
  const getStopStatusLabel = (status) => {
    if (status === "current") return "Current location";
    if (status === "departed") return "Departed";
    if (status === "scheduled") return "Scheduled service";
    return "Upcoming";
  };
  
  // All bus positions for map
  const allBusPositions = buses.map((b, index) => ({
    key: getBusKey(b, index),
    vehicle_id: b.vehicle_id,
    operator: b.operator,
    position: [b.position.lat, b.position.lng],
    eta: b.eta,
    passengers: b.passenger_count,
    delay_minutes: b.delay_minutes,
  }));
  
  const originPos = route?.origin_lat && route?.origin_lng
    ? [route.origin_lat, route.origin_lng]
    : null;
  const destPos = route?.dest_lat && route?.dest_lng
    ? [route.dest_lat, route.dest_lng]
    : null;
  
  // Route path for polyline
  const routePath = route?.route_path || [];
  const routeBoundsPoints = buildBoundsPoints(routePath, originPos, destPos);
  const mapFitKey = `${selectedRouteId ?? "none"}:${routeBoundsPoints.length}`;
  const mapResizeKey = `${theme}:${selectedRouteId ?? "none"}`;
  
  // Map center - prioritize: bus > origin > default
  const mapCenter = activeBus?.position ? [activeBus.position.lat, activeBus.position.lng] : originPos ?? [51.4545, -2.5879];
  const historyTitle = activeBus ? getBusLabel(activeBus, selectedBusIndex >= 0 ? selectedBusIndex : 0) : `${route?.route_name ?? "--"} ${route?.direction ?? ""}`.trim();
  const historySubtitle = activeBus
    ? `Last ${routeHistory.hours} hours of ETA, delay, passenger, and traffic samples for the selected live bus.`
    : `Last ${routeHistory.hours} hours of route history. Live bus selection will focus the charts automatically.`;

  // ===================================================================
  // Render
  // ===================================================================
  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ────────────────────────────────────────────────── */}
      <header className={`flex items-center justify-between px-6 py-4 border-b border-border backdrop-blur-lg sticky top-0 z-50 ${theme === "light" ? "bg-white/80 shadow-sm" : "bg-bg-card/60"}`}>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-blue-400 flex items-center justify-center text-xl shadow-lg shadow-accent/20">
            🚍
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              Transight <span className="text-accent font-extrabold">AI</span>
            </h1>
            <p className="text-xs text-text-secondary -mt-0.5">
              Real-Time Bus Tracking • Bristol
            </p>
          </div>
        </div>

        {/* Route Selector + Theme Toggle */}
        <div className="flex items-center gap-2">
          <label htmlFor="route-select" className="text-sm text-text-secondary hidden sm:inline">
            Route:
          </label>
          <select
            id="route-select"
            value={selectedRouteId ?? ""}
            onChange={(e) => setSelectedRouteId(Number(e.target.value))}
            className="bg-bg-card border border-border text-text-primary rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent cursor-pointer"
          >
            {routes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.route_name} — {r.direction} → {getDisplayTerminalName(r.route_name, r.destination_name)}
              </option>
            ))}
          </select>
          <button
            onClick={toggleTheme}
            className="w-9 h-9 flex items-center justify-center rounded-lg border border-border bg-bg-card hover:bg-bg-card-hover transition-colors cursor-pointer text-text-primary"
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? "\u2600\uFE0F" : "\uD83C\uDF19"}
          </button>
        </div>
      </header>

      {/* ── Main Grid ─────────────────────────────────────────────── */}
      <main className="flex-1 space-y-4 p-4 lg:p-6">
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* LEFT COLUMN: Info Cards */}
        <div className="flex flex-col gap-4 lg:col-span-1">

          {/* JOURNEY Route Card */}
          <div className="bg-bg-card rounded-2xl p-5 border border-border">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-3">
              Journey Route
            </p>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 rounded-full bg-success/20 text-success flex items-center justify-center text-xs font-bold">A</span>
              <span className="font-medium">{displayOriginName}</span>
            </div>
            <div className="ml-3 w-0.5 h-6 bg-border"></div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-danger/20 text-danger flex items-center justify-center text-xs font-bold">B</span>
              <span className="font-medium">{displayDestName}</span>
            </div>
          </div>

          {/* ETA TO DESTINATION Card */}
          <div className="bg-bg-card rounded-2xl p-6 border border-border card-glow text-center">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-1">
              {buses.length > 1 ? `${buses.length} Buses En Route` : 'Bus Arrives At'}
            </p>
            <p className="text-lg font-semibold text-text-primary mb-2">
              {displayDestName}
            </p>
            {activeBus && (
              <p className="text-xs text-text-secondary mb-3">
                Showing live data for {getBusLabel(activeBus, selectedBusIndex >= 0 ? selectedBusIndex : 0)}
              </p>
            )}
            
            {/* Show all buses' ETAs */}
            {buses.length > 0 ? (
              <div className="space-y-3">
                {buses.map((bus, idx) => (
                  <button
                    key={getBusKey(bus, idx)}
                    type="button"
                    onClick={() => setSelectedBusKey(getBusKey(bus, idx))}
                    className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                      getBusKey(bus, idx) === selectedBusKey
                        ? "border-accent bg-accent/10"
                        : "border-border/60 bg-transparent hover:bg-bg-card-hover"
                    }`}
                  >
                    <p className="text-sm text-text-secondary">
                      {bus.operator && bus.operator !== "unknown" ? `${bus.operator} ` : ""}
                      {bus.vehicle_id && bus.vehicle_id !== "unknown" ? `(${bus.vehicle_id})` : `Bus #${idx + 1}`}
                    </p>
                    <p className="text-4xl font-black text-danger tabular-nums leading-none">
                      {typeof bus.eta === "number" ? bus.eta : "--"}
                    </p>
                    <p className="text-xs text-text-secondary">minutes to destination</p>
                    {bus.scheduled_service_time && (
                      <p className="text-xs text-text-secondary">Service {bus.scheduled_service_time}</p>
                    )}
                    {bus.delay_minutes > 0 && (
                      <p className="text-xs text-danger">{Math.round(bus.delay_minutes)} min late</p>
                    )}
                    {bus.eta_method && (
                      <span className={`inline-block mt-1 text-xs px-2 py-0.5 rounded-full font-medium ${
                        bus.eta_method === "xgboost"
                          ? "bg-accent/15 text-accent"
                          : "bg-text-secondary/10 text-text-secondary"
                      }`}>
                        {bus.eta_method === "xgboost" ? "XGBoost" : bus.eta_method === "routing" ? "Routing" : "Formula"}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            ) : (
              <>
                <p className="text-6xl font-black text-text-secondary tabular-nums leading-none">--</p>
                <p className="text-sm text-text-secondary mt-2 font-medium">No buses currently tracked</p>
                <p className="text-xs text-text-secondary mt-1">Check back in a moment</p>
              </>
            )}
            
            <div className="mt-3 flex items-center justify-center gap-2">
              <span className={`w-2 h-2 rounded-full ${buses.length > 0 ? 'bg-success animate-pulse' : 'bg-warning'}`}></span>
              <span className="text-xs text-text-secondary">
                {buses.length > 0 ? `${buses.length} Bus${buses.length > 1 ? 'es' : ''} Tracked` : 'No Live Buses'}
              </span>
            </div>
          </div>

          {/* Passengers Card */}
          <div className="bg-bg-card rounded-2xl p-5 border border-border">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-1">
              Passenger Count (YOLO)
            </p>
            <p className="text-3xl font-bold">{passengers}</p>
            <p className="text-xs text-text-secondary mt-1">
              {activeBus ? "Detected for the selected live bus context" : "Detected from video feed when a live bus is active"}
            </p>
            {highDemand && (
              <div className="mt-3 flex items-center gap-2 bg-warning/10 text-warning rounded-lg px-3 py-2 text-sm font-medium">
                <span className="text-lg">⚠️</span> High Demand - Bus may be full
              </div>
            )}
          </div>

          {/* Traffic Delay Card */}
          <div className="bg-bg-card rounded-2xl p-5 border border-border">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-1">
              Traffic Delay
            </p>
            <p className="text-2xl font-bold">
              {activeBus?.traffic_delay != null
                ? `${Math.round(activeBus.traffic_delay)}s`
                : "—"}
            </p>
            <p className="text-xs text-text-secondary mt-1">
              From TomTom Traffic API
            </p>
          </div>

          {/* Bus Position Card */}
          {activeBus?.position && (
            <div className="bg-bg-card rounded-2xl p-5 border border-border">
              <p className="text-xs uppercase tracking-widest text-text-secondary mb-1">
                Current Bus Position
              </p>
              <p className="text-sm font-mono">
                {activeBus.position.lat.toFixed(6)}, {activeBus.position.lng.toFixed(6)}
              </p>
              <p className="text-xs text-text-secondary mt-1">
                From BODS Real-time Feed
              </p>
            </div>
          )}

          {/* Status */}
          {loading && (
            <p className="text-text-secondary text-sm animate-pulse">
              Loading routes…
            </p>
          )}
          {error && (
            <p className="text-danger text-sm bg-danger/10 rounded-lg px-3 py-2">
              ⚠ {error}
            </p>
          )}
        </div>

        {/* RIGHT COLUMN: Map */}
        <div className="lg:col-span-2 bg-bg-card rounded-2xl border border-border overflow-hidden min-h-[500px] shadow-lg">
          <MapContainer
            center={mapCenter}
            zoom={13}
            className="w-full h-full min-h-[500px] lg:min-h-0"
            style={{ height: "100%" }}
          >
            <MapViewportController
              fitKey={mapFitKey}
              fitPoints={routeBoundsPoints}
              resizeKey={mapResizeKey}
            />
            {/* Themed map tiles */}
            <TileLayer
              key={theme}
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
              url={theme === "dark"
                ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
              }
            />

            {/* Route path polyline */}
            {routePath.length > 0 && (
              <Polyline
                positions={routePath}
                color={theme === "dark" ? "#3b82f6" : "#1d4ed8"}
                weight={4}
                opacity={0.7}
                dashArray="10, 10"
              />
            )}

            {/* Origin marker */}
            {originPos && (
              <Marker position={originPos} icon={originIcon}>
                <Popup>
                  <strong>Departure:</strong> {displayOriginName}
                </Popup>
              </Marker>
            )}

            {/* Destination marker */}
            {destPos && (
              <Marker position={destPos} icon={destIcon}>
                <Popup>
                  <strong>Destination:</strong> {displayDestName}
                  <br />
                  ETA: {eta} mins
                </Popup>
              </Marker>
            )}

            {/* Bus markers - show ALL buses */}
            {allBusPositions.map((bus, index) => (
              <Marker
                key={bus.key}
                position={bus.position}
                icon={createBusIcon(bus.delay_minutes)}
              >
                <Popup>
                  🚌 <strong>Bus {route?.route_name} #{index + 1}</strong>
                  <br />
                  <small>ID: {bus.vehicle_id || 'Unknown'}</small>
                  <br />
                  {bus.position[0].toFixed(5)}, {bus.position[1].toFixed(5)}
                  <br />
                  <strong>To:</strong> {displayDestName}
                  <br />
                  <strong>ETA:</strong> {bus.eta ?? '--'} mins
                  <br />
                  <strong>Passengers:</strong> {bus.passengers}
                </Popup>
              </Marker>
            ))}

            {/* Stop markers */}
            {stops.map((stop, stopIdx) => (
              stop.stop?.lat && stop.stop?.lng && (() => {
                const stopPrediction = getStopPrediction(stop);
                const arrivalTime =
                  stopPrediction?.predicted_arrival ||
                  stopPrediction?.scheduled_arrival ||
                  formatScheduleTime(stop.scheduled_arrival) ||
                  "--";
                const delayText =
                  stopPrediction?.delay_text ||
                  (formatScheduleTime(stop.scheduled_arrival) ? "Static schedule reference" : "No live prediction yet");

                return (
                  <Marker
                    key={stop.stop?.stop_id || `stop-${stopIdx}`}
                    position={[stop.stop.lat, stop.stop.lng]}
                    icon={stopIcon}
                  >
                    <Popup>
                      <div className="min-w-[190px] text-sm">
                        <p className="font-semibold">{stop.stop.stop_name}</p>
                        <p className="text-xs text-slate-500">Stop {stop.sequence + 1}</p>
                        <div className="mt-2 space-y-1">
                          <p>
                            <strong>Arrival:</strong> {arrivalTime}
                          </p>
                          <p>
                            <strong>Status:</strong> {getStopStatusLabel(stopPrediction?.status)}
                          </p>
                          {activeServiceTime && (
                            <p>
                              <strong>Service:</strong> {activeServiceTime}
                            </p>
                          )}
                          <p>
                            <strong>Delay:</strong> {delayText}
                          </p>
                        </div>
                      </div>
                    </Popup>
                  </Marker>
                );
              })()
            ))}
          </MapContainer>
        </div>
        </section>

        <HistoricalTrends
          history={routeHistory}
          theme={theme}
          title={historyTitle}
          subtitle={historySubtitle}
          loading={historyLoading}
        />
      </main>

      {/* ── Footer ────────────────────────────────────────────────── */}
      <footer className="text-center text-xs text-text-secondary py-3 border-t border-border">
        Transight AI • Real-time Bristol Bus Tracking • Data: BODS + TomTom + YOLOv8
      </footer>
    </div>
  );
}
