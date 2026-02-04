import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, IconButton, Typography, TextField,
  Paper, Chip, Avatar, Slide
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import CloseIcon from '@mui/icons-material/Close';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// User location icon
const userIcon = L.divIcon({
  html: `<div style="
    width: 20px; height: 20px;
    background: #3b82f6; border: 3px solid white;
    border-radius: 50%; box-shadow: 0 4px 12px rgba(59,130,246,0.5);
  "></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  className: 'user-icon'
});

// Stop icon
const stopIcon = (isSelected) => L.divIcon({
  html: `<div style="
    width: ${isSelected ? 40 : 32}px; height: ${isSelected ? 40 : 32}px;
    background: ${isSelected ? '#10b981' : 'white'};
    border: 3px solid ${isSelected ? '#10b981' : '#6366f1'};
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    transition: all 0.2s;
  ">
    <span style="font-size: ${isSelected ? 18 : 14}px;">🚏</span>
  </div>`,
  iconSize: [isSelected ? 40 : 32, isSelected ? 40 : 32],
  iconAnchor: [isSelected ? 20 : 16, isSelected ? 20 : 16],
  className: 'stop-icon'
});

// Bus icon
const busIcon = (route, color, bearing) => L.divIcon({
  html: `<div style="
    width: 42px; height: 42px;
    background: ${color}; border: 3px solid white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: white; font-weight: bold; font-size: 12px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.4);
    transform: rotate(${bearing || 0}deg);
  ">${route}</div>`,
  iconSize: [42, 42],
  iconAnchor: [21, 21],
  className: 'bus-icon'
});

// Colors
const ROUTE_COLORS = ['#6366f1', '#ec4899', '#8b5cf6', '#14b8a6', '#f59e0b', '#ef4444', '#3b82f6', '#10b981', '#f97316'];
const getRouteColor = (route) => {
  let hash = 0;
  for (let i = 0; i < route.length; i++) hash = route.charCodeAt(i) + ((hash << 5) - hash);
  return ROUTE_COLORS[Math.abs(hash) % ROUTE_COLORS.length];
};

const formatTime = (mins) => mins <= 1 ? 'Due' : `${Math.round(mins)} min`;
const formatDist = (km) => km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`;

// Map Component
function MapView({ userLocation, stops, selectedStop, buses, onStopClick }) {
  const mapRef = useRef(null);
  const initialized = useRef(false);
  
  useEffect(() => {
    if (!initialized.current && mapRef.current && userLocation) {
      mapRef.current.setView(userLocation, 14);
      initialized.current = true;
    }
  }, [userLocation]);
  
  return (
    <MapContainer
      center={userLocation || [51.4545, -2.5879]}
      zoom={14}
      style={{ height: "100%", width: "100%" }}
      zoomControl={false}
      whenCreated={(m) => { mapRef.current = m; }}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      
      {userLocation && (
        <Marker position={userLocation} icon={userIcon} zIndexOffset={1000}>
          <Popup><Typography variant="subtitle2">You are here</Typography></Popup>
        </Marker>
      )}
      
      {stops.map(stop => (
        <Marker
          key={stop.atco_code}
          position={[stop.latitude, stop.longitude]}
          icon={stopIcon(selectedStop?.atco_code === stop.atco_code)}
          eventHandlers={{ click: () => onStopClick(stop) }}
          zIndexOffset={selectedStop?.atco_code === stop.atco_code ? 500 : 0}
        >
          <Popup>
            <Typography variant="subtitle2" fontWeight={700}>{stop.common_name}</Typography>
            <Typography variant="caption">{stop.locality}</Typography>
          </Popup>
        </Marker>
      ))}
      
      {buses.map(bus => (
        <Marker
          key={bus.bus_id}
          position={[bus.latitude, bus.longitude]}
          icon={busIcon(bus.route, getRouteColor(bus.route), bus.bearing)}
        >
          <Popup>
            <Box sx={{ minWidth: 150 }}>
              <Typography variant="subtitle2" fontWeight={700}>{bus.route} → {bus.destination}</Typography>
              <Typography variant="caption" display="block">{bus.operator}</Typography>
              <Typography variant="caption" color={bus.delay_minutes > 0 ? 'error' : 'success'}>
                {bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
              </Typography>
            </Box>
          </Popup>
        </Marker>
      ))}
      
      {buses.map(bus => bus.trail?.length > 1 && (
        <Polyline
          key={`trail-${bus.bus_id}`}
          positions={bus.trail.slice(-10).map(p => [p.lat, p.lon])}
          pathOptions={{ color: getRouteColor(bus.route), weight: 2, opacity: 0.4 }}
        />
      ))}
    </MapContainer>
  );
}

function App() {
  const [userLocation, setUserLocation] = useState(null);
  const [allStops, setAllStops] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopBuses, setStopBuses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  
  const API_BASE_URL = "http://127.0.0.1:8000";
  
  // Get location
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setUserLocation([pos.coords.latitude, pos.coords.longitude]),
        () => setUserLocation([51.4545, -2.5879])
      );
    } else {
      setUserLocation([51.4545, -2.5879]);
    }
  }, []);
  
  // Fetch all Bristol stops
  const fetchAllStops = useCallback(async () => {
    if (!userLocation) return;
    
    try {
      const res = await axios.get(`${API_BASE_URL}/stops`, {
        params: { lat: userLocation[0], lon: userLocation[1], radius: 50 }
      });
      setAllStops(res.data.stops || []);
    } catch (e) {
      console.error("Error fetching stops:", e);
    }
  }, [userLocation]);
  
  useEffect(() => {
    fetchAllStops();
  }, [fetchAllStops]);
  
  // Fetch buses for selected stop
  const fetchStopBuses = useCallback(async (stop) => {
    if (!stop || !userLocation) return;
    
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/stop/${stop.atco_code}/buses`, {
        params: { lat: userLocation[0], lon: userLocation[1] }
      });
      
      setStopBuses(res.data.buses || []);
      setLastUpdate(new Date());
    } catch (e) {
      console.error("Error fetching buses:", e);
    } finally {
      setLoading(false);
    }
  }, [userLocation]);
  
  // Auto-refresh
  useEffect(() => {
    if (!selectedStop) return;
    
    fetchStopBuses(selectedStop);
    const interval = setInterval(() => fetchStopBuses(selectedStop), 10000);
    return () => clearInterval(interval);
  }, [selectedStop, fetchStopBuses]);
  
  // Search
  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    try {
      const params = { q: query };
      if (userLocation) {
        params.lat = userLocation[0];
        params.lon = userLocation[1];
      }
      const res = await axios.get(`${API_BASE_URL}/search-stops`, { params });
      setSearchResults(res.data.results || []);
    } catch (e) {
      console.error("Search error:", e);
    }
  };
  
  const handleStopClick = (stop) => {
    setSelectedStop(stop);
    fetchStopBuses(stop);
  };
  
  return (
    <Box sx={{ width: '100%', height: '100vh', position: 'relative' }}>
      <style>{`
        .user-icon, .stop-icon, .bus-icon { background: transparent !important; border: none !important; }
      `}</style>
      
      {/* Map */}
      <Box sx={{ position: 'absolute', inset: 0 }}>
        <MapView
          userLocation={userLocation}
          stops={allStops}
          selectedStop={selectedStop}
          buses={selectedStop ? stopBuses : []}
          onStopClick={handleStopClick}
        />
      </Box>
      
      {/* Search Bar */}
      <Box sx={{ position: 'absolute', top: 16, left: 16, right: 16, zIndex: 1000 }}>
        <Paper elevation={3} sx={{ borderRadius: 3, overflow: 'hidden' }}>
          {!searchOpen ? (
            <Box 
              onClick={() => setSearchOpen(true)}
              sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1.5, bgcolor: 'white', cursor: 'pointer' }}
            >
              <SearchIcon sx={{ color: '#9ca3af', mr: 1.5 }} />
              <Typography color="#9ca3af">Search for a stop...</Typography>
            </Box>
          ) : (
            <Box sx={{ bgcolor: 'white' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1 }}>
                <SearchIcon sx={{ color: '#9ca3af', mr: 1.5 }} />
                <TextField
                  fullWidth
                  placeholder="Search stops..."
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  autoFocus
                  variant="standard"
                  InputProps={{ disableUnderline: true }}
                />
                <IconButton size="small" onClick={() => { setSearchOpen(false); setSearchQuery(''); setSearchResults([]); }}>
                  <CloseIcon />
                </IconButton>
              </Box>
              
              {searchResults.length > 0 && (
                <Box sx={{ maxHeight: 300, overflow: 'auto', borderTop: '1px solid #e5e7eb' }}>
                  {searchResults.map((stop) => (
                    <Box
                      key={stop.atco_code}
                      onClick={() => {
                        handleStopClick(stop);
                        setSearchOpen(false);
                        setSearchQuery('');
                        setSearchResults([]);
                      }}
                      sx={{ px: 2, py: 1.5, borderBottom: '1px solid #f3f4f6', cursor: 'pointer', '&:hover': { bgcolor: '#f9fafb' } }}
                    >
                      <Typography fontWeight={600}>{stop.common_name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {stop.locality} {stop.distance_km && `• ${formatDist(stop.distance_km)}`}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          )}
        </Paper>
      </Box>
      
      {/* Stats */}
      <Paper sx={{ position: 'absolute', top: 80, left: 16, px: 2, py: 1, zIndex: 500 }}>
        <Typography variant="body2" fontWeight={600}>
          {allStops.length} stops • {selectedStop ? stopBuses.length : 0} buses
        </Typography>
      </Paper>
      
      {/* My Location */}
      <IconButton
        sx={{ position: 'absolute', bottom: selectedStop ? 340 : 100, right: 16, bgcolor: 'white', boxShadow: 2 }}
      >
        <MyLocationIcon />
      </IconButton>
      
      {/* Bottom Sheet - Stop Detail */}
      {selectedStop && (
        <Slide direction="up" in={true}>
          <Paper sx={{ position: 'absolute', bottom: 0, left: 0, right: 0, maxHeight: '55vh', borderRadius: '24px 24px 0 0', overflow: 'auto' }}>
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 1, pb: 0.5 }}>
              <Box sx={{ width: 40, height: 4, bgcolor: '#d1d5db', borderRadius: 2 }} />
            </Box>
            
            <Box sx={{ px: 3, pb: 2, borderBottom: '1px solid #e5e7eb' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <Box>
                  <Typography variant="h6" fontWeight={700}>{selectedStop.common_name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {selectedStop.locality} • {formatDist(selectedStop.distance_km)}
                  </Typography>
                </Box>
                <IconButton size="small" onClick={() => { setSelectedStop(null); setStopBuses([]); }}>
                  <CloseIcon />
                </IconButton>
              </Box>
              {lastUpdate && (
                <Typography variant="caption" color="text.secondary">
                  Updated {lastUpdate.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                </Typography>
              )}
            </Box>
            
            <Box sx={{ p: 3 }}>
              {loading && stopBuses.length === 0 ? (
                <Box display="flex" justifyContent="center" py={4}>
                  <CircularProgress size={30} />
                </Box>
              ) : stopBuses.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <DirectionsBusIcon sx={{ fontSize: 48, color: '#d1d5db', mb: 1 }} />
                  <Typography color="text.secondary">No buses approaching</Typography>
                </Box>
              ) : (
                <>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block', fontWeight: 600 }}>
                    {stopBuses.length} BUS{stopBuses.length !== 1 ? 'ES' : ''} APPROACHING
                  </Typography>
                  
                  {stopBuses.map((bus) => (
                    <Paper key={bus.bus_id} sx={{ mb: 2, p: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Avatar sx={{ bgcolor: getRouteColor(bus.route), width: 48, height: 48, fontWeight: 700 }}>
                        {bus.route}
                      </Avatar>
                      <Box sx={{ flex: 1 }}>
                        <Typography fontWeight={700}>{bus.destination}</Typography>
                        <Typography variant="caption" color="text.secondary">{bus.operator}</Typography>
                        <Chip
                          size="small"
                          label={bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
                          sx={{
                            ml: 1,
                            bgcolor: bus.delay_minutes > 0 ? '#fee2e2' : '#d1fae5',
                            color: bus.delay_minutes > 0 ? '#dc2626' : '#059669',
                            fontWeight: 600
                          }}
                        />
                      </Box>
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography variant="h5" fontWeight={800} color="#059669">
                          {formatTime(bus.distance_to_stop * 2)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          <AccessTimeIcon sx={{ fontSize: 12, verticalAlign: 'middle' }} /> arriving
                        </Typography>
                      </Box>
                    </Paper>
                  ))}
                </>
              )}
            </Box>
          </Paper>
        </Slide>
      )}
      
      {/* Hint */}
      {!selectedStop && allStops.length > 0 && (
        <Paper sx={{ position: 'absolute', bottom: 16, left: 16, right: 16, p: 2, borderRadius: 2 }}>
          <Typography fontWeight={600}>📍 {allStops.length} bus stops in Bristol</Typography>
          <Typography variant="caption" color="text.secondary">Tap any stop to see arriving buses</Typography>
        </Paper>
      )}
    </Box>
  );
}

export default App;
