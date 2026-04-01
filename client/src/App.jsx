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

/* ── Custom icons ──────────────────────────────────────────────────── */
const busIcon = new L.DivIcon({
  className: "bus-marker",
  html: `<div style="
    width:32px;height:32px;border-radius:50%;
    background:linear-gradient(135deg,#2563eb,#1d4ed8);
    border:3px solid #fff;box-shadow:0 0 16px rgba(37,99,235,.7);
    display:flex;align-items:center;justify-content:center;
    font-size:16px;animation:pulse 2s infinite;
  ">🚌</div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

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
  const [routes, setRoutes] = useState([]);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [buses, setBuses] = useState([]); // Array of all buses
  const [routePredictions, setRoutePredictions] = useState([]);
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
        setRoutePredictions(data.stops || []);
      })
      .catch(() => {
        setRoutePredictions([]);
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
  // Use first bus for main display, or show multi-bus info
  const primaryBus = buses.length > 0 ? buses[0] : null;
  const eta = primaryBus?.eta ?? "--";
  const passengers = primaryBus?.passenger_count ?? 0;
  const highDemand = passengers > 15;
  
  const originName = route?.origin_name ?? "—";
  const destName = route?.destination_name ?? "—";
  const selectedBus =
    buses.find((bus, index) => getBusKey(bus, index) === selectedBusKey) ||
    buses[0] ||
    null;
  const displayStopPredictions =
    selectedBus?.stop_predictions?.length > 0
      ? selectedBus.stop_predictions
      : routePredictions;
  const showingLivePredictions = selectedBus?.stop_predictions?.length > 0;
  
  // All bus positions for map
  const allBusPositions = buses.map((b, index) => ({
    key: getBusKey(b, index),
    vehicle_id: b.vehicle_id,
    operator: b.operator,
    position: [b.position.lat, b.position.lng],
    eta: b.eta,
    passengers: b.passenger_count,
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
  const mapCenter = primaryBus?.position ? [primaryBus.position.lat, primaryBus.position.lng] : originPos ?? [51.4545, -2.5879];
  
  // Bus to destination line
  const busToDestLine = primaryBus?.position && destPos ? [[primaryBus.position.lat, primaryBus.position.lng], destPos] : null;

  // ===================================================================
  // Render
  // ===================================================================
  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-bg-card/60 backdrop-blur-lg sticky top-0 z-50">
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

        {/* Route Selector */}
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
            <p className="text-lg font-semibold text-white mb-2">
              {destName}
            </p>
            
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

          {/* STOP-BY-STOP Arrival Times (Like First Bus App) */}
          {displayStopPredictions.length > 0 && (
            <div className="bg-bg-card rounded-2xl p-5 border border-border max-h-[400px] overflow-y-auto">
              <div className="flex items-end justify-between gap-3 mb-3">
                <div>
                  <p className="text-xs uppercase tracking-widest text-text-secondary">
                    {showingLivePredictions ? "Live Arrivals at Stops" : "Scheduled Stop Times"}
                  </p>
                  <p className="text-xs text-text-secondary mt-1">
                    {showingLivePredictions
                      ? "Select a live bus to inspect its stop-by-stop arrivals."
                      : "No live Route 72 bus is active right now, so timetable stop times are shown."}
                  </p>
                </div>
                {showingLivePredictions && buses.length > 1 && (
                  <select
                    value={selectedBusKey}
                    onChange={(e) => setSelectedBusKey(e.target.value)}
                    className="bg-bg-card border border-border text-text-primary rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent cursor-pointer max-w-[230px]"
                  >
                    {buses.map((bus, idx) => {
                      const key = getBusKey(bus, idx);
                      return (
                        <option key={key} value={key}>
                          {getBusLabel(bus, idx)}
                        </option>
                      );
                    })}
                  </select>
                )}
              </div>
              <div className="space-y-2">
                {displayStopPredictions.slice(0, 10).map((stop, idx) => (
                  <div 
                    key={stop.stop_id || idx} 
                    className={`flex items-center justify-between p-2 rounded-lg ${
                      stop.status === 'current' ? 'bg-accent/20 border border-accent' : 
                      stop.status === 'departed' ? 'opacity-50' :
                      stop.status === 'scheduled' ? 'bg-white/5 border border-border/60' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${
                        stop.status === 'current' ? 'bg-accent animate-pulse' : 
                        stop.status === 'departed' ? 'bg-text-secondary' :
                        stop.status === 'scheduled' ? 'bg-warning' : 'bg-success'
                      }`}></span>
                      <div>
                        <p className="text-sm font-medium">{stop.stop_name}</p>
                        <p className="text-xs text-text-secondary">
                          {stop.status === 'current' ? 'Current location' : 
                           stop.status === 'departed' ? 'Departed' :
                           stop.status === 'scheduled' ? 'Scheduled service' : 'Upcoming'}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold">{stop.predicted_arrival || stop.scheduled_arrival || "--"}</p>
                      {stop.delay_text && (
                        <p className={`text-xs ${
                          stop.delay_minutes > 0 ? 'text-danger' :
                          stop.delay_minutes < 0 ? 'text-success' : 'text-text-secondary'
                        }`}>
                          {stop.delay_text}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
                {displayStopPredictions.length > 10 && (
                  <p className="text-xs text-text-secondary text-center pt-2">
                    +{displayStopPredictions.length - 10} more stops
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Passengers Card */}
          <div className="bg-bg-card rounded-2xl p-5 border border-border">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-1">
              Passenger Count (YOLO)
            </p>
            <p className="text-3xl font-bold">{passengers}</p>
            <p className="text-xs text-text-secondary mt-1">
              Detected from video feed at bus stop
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
              {primaryBus?.traffic_delay != null
                ? `${Math.round(primaryBus.traffic_delay)}s`
                : "—"}
            </p>
            <p className="text-xs text-text-secondary mt-1">
              From TomTom Traffic API
            </p>
          </div>

          {/* Bus Position Card */}
          {primaryBus?.position && (
            <div className="bg-bg-card rounded-2xl p-5 border border-border">
              <p className="text-xs uppercase tracking-widest text-text-secondary mb-1">
                Current Bus Position
              </p>
              <p className="text-sm font-mono">
                {primaryBus.position.lat.toFixed(6)}, {primaryBus.position.lng.toFixed(6)}
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
        <div className="lg:col-span-2 bg-white rounded-2xl border border-border overflow-hidden min-h-[500px] shadow-lg">
          <MapContainer
            center={mapCenter}
            zoom={13}
            className="w-full h-full min-h-[500px] lg:min-h-0"
            style={{ height: "100%" }}
          >
            {/* Light theme map tiles */}
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {/* Route path polyline */}
            {routePath.length > 0 && (
              <Polyline
                positions={routePath}
                color="#3b82f6"
                weight={4}
                opacity={0.7}
                dashArray="10, 10"
              />
            )}

            {/* Bus to destination line */}
            {busToDestLine && (
              <Polyline
                positions={busToDestLine}
                color="#ef4444"
                weight={3}
                opacity={0.6}
                dashArray="5, 10"
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
                icon={busIcon}
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
              stop.stop?.lat && stop.stop?.lng && (
                <Marker
                  key={stop.stop?.stop_id || `stop-${stopIdx}`}
                  position={[stop.stop.lat, stop.stop.lng]}
                  icon={stopIcon}
                >
                  <Popup>
                    <strong>Stop {stop.sequence + 1}:</strong> {stop.stop.stop_name}
                  </Popup>
                </Marker>
              )
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
