/**
 * Transight AI — Phase 2 MVP Frontend
 *
 * Features:
 *   • Route Selector with origin/destination display
 *   • Live dashboard: ETA to destination, passenger count
 *   • React-Leaflet map with bus, route visualization
 */

import { useState, useEffect, useCallback } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

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

function getBusKey(bus, index = 0) {
  return `${bus.operator || "unknown"}:${bus.vehicle_id || `bus-${index}`}`;
}

function getBusLabel(bus, index = 0) {
  const operator = bus.operator && bus.operator !== "unknown" ? bus.operator : "Unknown operator";
  const vehicle = bus.vehicle_id && bus.vehicle_id !== "unknown" ? bus.vehicle_id : `Bus ${index + 1}`;
  return `${operator} • ${vehicle}`;
}

// =====================================================================
// Component: App
// =====================================================================
export default function App() {
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem("transight-theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch {}
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("transight-theme", theme); } catch {}
  }, [theme]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e) => {
      try { if (localStorage.getItem("transight-theme")) return; } catch {}
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
        console.log("[DEBUG] Status API response:", data);
        let nextBuses = [];
        // Handle new multi-bus format
        if (data.buses && Array.isArray(data.buses)) {
          console.log("[DEBUG] Setting buses:", data.buses.length, data.buses);
          nextBuses = data.buses;
        } else {
          console.log("[DEBUG] No buses array found, checking bus_available:", data.bus_available);
          // If no buses array but bus_available is false
          if (data.bus_available === false) {
            nextBuses = [];
          } else if (data.status) {
            // Old format - convert to new format
            console.log("[DEBUG] Converting old format to new");
            nextBuses = [{
              vehicle_id: 'unknown',
              position: { lat: data.status.bus_lat, lng: data.status.bus_lng },
              eta: data.status.predicted_eta,
              passenger_count: data.status.passenger_count,
              traffic_delay: data.status.traffic_delay,
              scheduled_service_time: data.status.scheduled_service_time,
              delay_minutes: data.status.delay_minutes,
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
        console.error("[DEBUG] Error fetching status:", e);
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


  /* ── Derived values ────────────────────────────────────────────── */
  const originName = route?.origin_name ?? "—";
  const destName = route?.destination_name ?? "—";
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
  const showingLivePredictions = activeBus?.stop_predictions?.length > 0;
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
  
  // Map center - prioritize: bus > origin > default
  const mapCenter = activeBus?.position ? [activeBus.position.lat, activeBus.position.lng] : originPos ?? [51.4545, -2.5879];

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
                {r.route_name} — {r.direction} → {r.destination_name}
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
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 lg:p-6">
        {/* LEFT COLUMN: Info Cards */}
        <div className="flex flex-col gap-4 lg:col-span-1">

          {/* JOURNEY Route Card */}
          <div className="bg-bg-card rounded-2xl p-5 border border-border">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-3">
              Journey Route
            </p>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-6 h-6 rounded-full bg-success/20 text-success flex items-center justify-center text-xs font-bold">A</span>
              <span className="font-medium">{originName}</span>
            </div>
            <div className="ml-3 w-0.5 h-6 bg-border"></div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-danger/20 text-danger flex items-center justify-center text-xs font-bold">B</span>
              <span className="font-medium">{destName}</span>
            </div>
          </div>

          {/* ETA TO DESTINATION Card */}
          <div className="bg-bg-card rounded-2xl p-6 border border-border card-glow text-center">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-1">
              {buses.length > 1 ? `${buses.length} Buses En Route` : 'Bus Arrives At'}
            </p>
            <p className="text-lg font-semibold text-text-primary mb-2">
              {destName}
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
                  <div key={getBusKey(bus, idx)} className="border-b border-border/50 pb-2 last:border-0">
                    <p className="text-sm text-text-secondary">
                      {bus.operator && bus.operator !== "unknown" ? `${bus.operator} ` : ""}
                      {bus.vehicle_id && bus.vehicle_id !== 'unknown' ? `(${bus.vehicle_id})` : `Bus #${idx + 1}`}
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
                  </div>
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
                  <strong>Departure:</strong> {originName}
                </Popup>
              </Marker>
            )}

            {/* Destination marker */}
            {destPos && (
              <Marker position={destPos} icon={destIcon}>
                <Popup>
                  <strong>Destination:</strong> {destName}
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
                  <strong>To:</strong> {destName}
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
                  stop.scheduled_arrival ||
                  "--";
                const delayText =
                  stopPrediction?.delay_text ||
                  (!showingLivePredictions && stop.scheduled_arrival ? "Scheduled service" : "No live prediction yet");

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
      </main>

      {/* ── Footer ────────────────────────────────────────────────── */}
      <footer className="text-center text-xs text-text-secondary py-3 border-t border-border">
        Transight AI • Real-time Bristol Bus Tracking • Data: BODS + TomTom + YOLOv8
      </footer>
    </div>
  );
}
