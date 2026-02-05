import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, IconButton, Typography, TextField,
  Paper, Chip, Avatar
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import CloseIcon from '@mui/icons-material/Close';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
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

const stopIcon = (isSelected) => L.divIcon({
  html: `<div style="
    width: ${isSelected ? 44 : 36}px; height: ${isSelected ? 44 : 36}px;
    background: ${isSelected ? '#10b981' : 'white'};
    border: 3px solid ${isSelected ? '#10b981' : '#6366f1'};
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  ">
    <span style="font-size: ${isSelected ? 20 : 16}px;">🚏</span>
  </div>`,
  iconSize: [isSelected ? 44 : 36, isSelected ? 44 : 36],
  iconAnchor: [isSelected ? 22 : 18, isSelected ? 22 : 18],
  className: 'stop-icon'
});

const busIcon = (route, color, bearing) => L.divIcon({
  html: `<div style="
    width: 52px; height: 52px;
    background: ${color}; border: 4px solid white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: white; font-weight: bold; font-size: 14px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.5);
    transform: rotate(${bearing || 0}deg);
    z-index: 1000;
  ">${route}</div>`,
  iconSize: [52, 52],
  iconAnchor: [26, 26],
  className: 'bus-icon'
});

const ROUTE_COLORS = ['#6366f1', '#ec4899', '#8b5cf6', '#14b8a6', '#f59e0b', '#ef4444', '#3b82f6', '#10b981', '#f97316'];
const getRouteColor = (route) => {
  let hash = 0;
  for (let i = 0; i < route.length; i++) hash = route.charCodeAt(i) + ((hash << 5) - hash);
  return ROUTE_COLORS[Math.abs(hash) % ROUTE_COLORS.length];
};

const formatTime = (mins) => mins <= 1 ? 'Due' : `${Math.round(mins)} min`;
const formatDist = (km) => km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`;

function MapView({ userLocation, stops, selectedStop, selectedBus, viewMode, onStopClick, route72Geometry, route72Buses, onBusClick }) {
  const mapRef = useRef(null);
  const initialized = useRef(false);
  
  useEffect(() => {
    if (!initialized.current && mapRef.current && userLocation) {
      mapRef.current.setView(userLocation, 14);
      initialized.current = true;
    }
  }, [userLocation]);
  
  useEffect(() => {
    if (selectedBus && mapRef.current) {
      mapRef.current.setView([selectedBus.latitude, selectedBus.longitude], 15);
    }
  }, [selectedBus?.bus_id]);
  
  // Route 72 geometry line
  const route72Line = route72Geometry?.geometry?.map(p => [p.lat, p.lng]) || [];
  
  const busTrail = selectedBus?.trail?.length > 1 
    ? selectedBus.trail.map(p => [p.lat, p.lon])
    : [];
  
  return (
    <MapContainer
      center={userLocation || [51.4545, -2.5879]}
      zoom={13}
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
      
      {/* ROUTE 72 VIEW */}
      {(viewMode === 'route72' || viewMode === 'stops') && route72Line.length > 1 && (
        <>
          {/* Route 72 Line - Purple */}
          <Polyline
            positions={route72Line}
            pathOptions={{ 
              color: '#8b5cf6', 
              weight: 8, 
              opacity: 0.9,
              lineCap: 'round',
              lineJoin: 'round'
            }}
          />
          {/* Route 72 Stops */}
          {route72Geometry?.stops?.map(stop => (
            <Marker
              key={stop.id}
              position={[stop.lat, stop.lng]}
              icon={stopIcon(selectedStop?.atco_code === stop.atco_code)}
              eventHandlers={{ click: () => onStopClick(stop) }}
            >
              <Popup>
                <Typography variant="subtitle2">{stop.name}</Typography>
                <Typography variant="caption">Route 72 Stop #{stop.order}</Typography>
              </Popup>
            </Marker>
          ))}
          {/* Route 72 Buses */}
          {route72Buses.map(bus => (
            <Marker
              key={bus.bus_id}
              position={[bus.latitude, bus.longitude]}
              icon={busIcon('72', '#8b5cf6', bus.bearing)}
              zIndexOffset={2000}
              eventHandlers={{ click: () => onBusClick(bus) }}
            >
              <Popup>
                <Box sx={{ minWidth: 200 }}>
                  <Typography variant="h6" fontWeight={700} color="#8b5cf6">Route 72</Typography>
                  <Typography variant="body2">→ {bus.destination}</Typography>
                  <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                    Speed: {Math.round(bus.speed || 0)} km/h
                  </Typography>
                  {bus.route_progress && (
                    <Typography variant="caption" display="block" color="text.secondary">
                      Near: {bus.route_progress.nearest_stop}
                    </Typography>
                  )}
                </Box>
              </Popup>
            </Marker>
          ))}
        </>
      )}
      
      {viewMode === 'stops' && !route72Geometry && stops.map(stop => (
        <Marker
          key={stop.atco_code}
          position={[stop.latitude, stop.longitude]}
          icon={stopIcon(selectedStop?.atco_code === stop.atco_code)}
          eventHandlers={{ click: () => onStopClick(stop) }}
        />
      ))}
      
      {viewMode === 'bus-detail' && selectedStop && (
        <Marker position={[selectedStop.latitude, selectedStop.longitude]} icon={stopIcon(true)} />
      )}
      
      {/* BUS DETAIL VIEW - GPS Trail */}
      {viewMode === 'bus-detail' && busTrail.length > 1 && (
        <>
          <Polyline
            positions={busTrail}
            pathOptions={{ 
              color: 'white', 
              weight: 10, 
              opacity: 0.8,
              lineCap: 'round',
              lineJoin: 'round'
            }}
          />
          <Polyline
            positions={busTrail}
            pathOptions={{ 
              color: '#3b82f6', 
              weight: 6, 
              opacity: 1,
              lineCap: 'round',
              lineJoin: 'round'
            }}
          />
        </>
      )}
      
      {viewMode === 'bus-detail' && selectedBus && (
        <Marker
          position={[selectedBus.latitude, selectedBus.longitude]}
          icon={busIcon(selectedBus.route, getRouteColor(selectedBus.route), selectedBus.bearing)}
          zIndexOffset={2000}
        >
          <Popup>
            <Box sx={{ minWidth: 180 }}>
              <Typography variant="h6" fontWeight={700}>{selectedBus.route}</Typography>
              <Typography>→ {selectedBus.destination}</Typography>
              <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                Speed: {Math.round(selectedBus.speed || 0)} km/h
              </Typography>
            </Box>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}

function App() {
  const [viewMode, setViewMode] = useState('route72'); // Default to Route 72 view
  const [userLocation, setUserLocation] = useState(null);
  const [allStops, setAllStops] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopBuses, setStopBuses] = useState([]);
  const [selectedBus, setSelectedBus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  
  // Route 72 specific state
  const [route72Geometry, setRoute72Geometry] = useState(null);
  const [route72Buses, setRoute72Buses] = useState([]);
  
  // Bottom sheet state
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetExpanded, setSheetExpanded] = useState(false);
  const sheetRef = useRef(null);
  const startY = useRef(0);
  const currentY = useRef(0);
  
  const API_BASE_URL = "http://127.0.0.1:8000";
  
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
  
  // Fetch Route 72 geometry and buses
  const fetchRoute72Data = useCallback(async () => {
    try {
      // Fetch route geometry
      const geoRes = await axios.get(`${API_BASE_URL}/route/72/geometry`);
      setRoute72Geometry(geoRes.data);
      
      // Fetch Route 72 buses
      const busesRes = await axios.get(`${API_BASE_URL}/route/72/buses`);
      setRoute72Buses(busesRes.data.buses || []);
      setLastUpdate(new Date());
    } catch (e) {
      console.error("Error fetching Route 72 data:", e);
    }
  }, []);
  
  // Poll Route 72 data every 10 seconds
  useEffect(() => {
    fetchRoute72Data();
    const interval = setInterval(fetchRoute72Data, 10000);
    return () => clearInterval(interval);
  }, [fetchRoute72Data]);
  
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
  
  useEffect(() => {
    if (!sheetOpen || !selectedStop) return;
    
    fetchStopBuses(selectedStop);
    const interval = setInterval(() => fetchStopBuses(selectedStop), 10000);
    return () => clearInterval(interval);
  }, [sheetOpen, selectedStop, fetchStopBuses]);
  
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
    setViewMode('bus-list');
    setSheetOpen(true);
    setSheetExpanded(false);
    fetchStopBuses(stop);
  };
  
  const handleBusClick = (bus) => {
    setSelectedBus(bus);
    setViewMode('bus-detail');
    setSheetExpanded(false);
  };
  
  const handleBack = () => {
    if (viewMode === 'bus-detail') {
      setSelectedBus(null);
      setViewMode('route72');
    } else if (viewMode === 'bus-list') {
      setSelectedStop(null);
      setStopBuses([]);
      setSheetOpen(false);
      setViewMode('route72');
    } else {
      setViewMode('route72');
    }
  };
  
  // Touch handlers for smooth sheet dragging
  const handleTouchStart = (e) => {
    startY.current = e.touches[0].clientY;
  };
  
  const handleTouchMove = (e) => {
    currentY.current = e.touches[0].clientY;
  };
  
  const handleTouchEnd = () => {
    const diff = startY.current - currentY.current;
    if (diff > 50) {
      setSheetExpanded(true); // Swipe up
    } else if (diff < -50) {
      setSheetExpanded(false); // Swipe down
    }
  };
  
  return (
    <Box sx={{ width: '100%', height: '100vh', position: 'relative', overflow: 'hidden' }}>
      <style>{`
        .user-icon, .stop-icon, .bus-icon { background: transparent !important; border: none !important; }
        .sheet-transition { transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
      `}</style>
      
      {/* Map */}
      <Box sx={{ position: 'absolute', inset: 0 }}>
        <MapView
          userLocation={userLocation}
          stops={allStops}
          selectedStop={selectedStop}
          selectedBus={selectedBus}
          viewMode={viewMode}
          onStopClick={handleStopClick}
          route72Geometry={route72Geometry}
          route72Buses={route72Buses}
          onBusClick={handleBusClick}
        />
      </Box>
      
      {/* Route 72 Header */}
      <Box sx={{ position: 'absolute', top: 80, left: 16, zIndex: 1000 }}>
        <Paper elevation={3} sx={{ borderRadius: 2, px: 2, py: 1, bgcolor: '#8b5cf6', color: 'white' }}>
          <Typography fontWeight={700}>Route 72</Typography>
          <Typography variant="caption" display="block">Temple Meads ↔ UWE Frenchay</Typography>
          <Typography variant="caption" display="block">{route72Buses.length} bus{route72Buses.length !== 1 ? 'es' : ''} active</Typography>
        </Paper>
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
              <Typography color="#9ca3af">
                {viewMode === 'route72' ? 'Route 72 - Temple Meads to UWE' : 
                 viewMode === 'stops' ? 'Search for a stop...' : 
                 viewMode === 'bus-list' ? selectedStop?.common_name :
                 `Bus ${selectedBus?.route} to ${selectedBus?.destination}`}
              </Typography>
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
                      <Typography fontWeight={600}>{stop.common_name || stop.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {stop.locality || 'Bristol'} {stop.distance_km && `• ${formatDist(stop.distance_km)}`}
                        {stop.order && ` • Stop #${stop.order}`}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          )}
        </Paper>
      </Box>
      
      {/* My Location */}
      <IconButton
        sx={{ position: 'absolute', bottom: sheetOpen ? (sheetExpanded ? '80%' : '50%') : 100, right: 16, bgcolor: 'white', boxShadow: 2, zIndex: 500 }}
      >
        <MyLocationIcon />
      </IconButton>
      
      {/* Draggable Bottom Sheet */}
      {sheetOpen && (
        <Box
          ref={sheetRef}
          className="sheet-transition"
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: sheetExpanded ? '80%' : '50%',
            bgcolor: 'white',
            borderRadius: '24px 24px 0 0',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 -4px 20px rgba(0,0,0,0.15)'
          }}
        >
          {/* Drag Handle */}
          <Box 
            onClick={() => setSheetExpanded(!sheetExpanded)}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
            sx={{ 
              display: 'flex', 
              justifyContent: 'center', 
              pt: 2, 
              pb: 1,
              cursor: 'pointer',
              userSelect: 'none'
            }}
          >
            <Box sx={{ width: 56, height: 6, bgcolor: '#d1d5db', borderRadius: 3 }} />
          </Box>
          
          {/* Content */}
          <Box sx={{ flex: 1, overflow: 'auto', px: 3, pb: 3 }}>
            {/* BUS LIST */}
            {viewMode === 'bus-list' && selectedStop && (
              <>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                  <Box>
                    <Typography variant="h5" fontWeight={700}>{selectedStop.common_name}</Typography>
                    <Typography variant="body2" color="text.secondary">{selectedStop.locality}</Typography>
                  </Box>
                  <IconButton onClick={handleBack}>
                    <CloseIcon />
                  </IconButton>
                </Box>
                
                {loading && stopBuses.length === 0 ? (
                  <Box display="flex" justifyContent="center" py={4}>
                    <CircularProgress size={30} />
                  </Box>
                ) : stopBuses.length === 0 ? (
                  <Box sx={{ textAlign: 'center', py: 6 }}>
                    <DirectionsBusIcon sx={{ fontSize: 64, color: '#d1d5db', mb: 2 }} />
                    <Typography color="text.secondary">No buses approaching</Typography>
                  </Box>
                ) : (
                  <>
                    <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block', fontWeight: 600, textTransform: 'uppercase' }}>
                      Select a bus to track ({stopBuses.length})
                    </Typography>
                    
                    {stopBuses.map((bus) => (
                      <Paper 
                        key={bus.bus_id} 
                        onClick={() => handleBusClick(bus)}
                        elevation={2}
                        sx={{ 
                          mb: 2, 
                          p: 2.5, 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: 2,
                          cursor: 'pointer',
                          borderRadius: 3,
                          '&:hover': { bgcolor: '#f8fafc', transform: 'translateY(-2px)', transition: 'all 0.2s' }
                        }}
                      >
                        <Avatar sx={{ bgcolor: getRouteColor(bus.route), width: 52, height: 52, fontWeight: 700, fontSize: '1.1rem' }}>
                          {bus.route}
                        </Avatar>
                        <Box sx={{ flex: 1 }}>
                          <Typography fontWeight={700} fontSize="1.1rem">{bus.destination}</Typography>
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
                          <Typography variant="h4" fontWeight={800} color="#059669">
                            {formatTime(bus.distance_to_stop * 2)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            arriving
                          </Typography>
                        </Box>
                      </Paper>
                    ))}
                  </>
                )}
              </>
            )}
            
            {/* BUS DETAIL */}
            {viewMode === 'bus-detail' && selectedBus && selectedStop && (
              <>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                  <IconButton onClick={handleBack} sx={{ mr: 1 }}>
                    <ArrowBackIcon />
                  </IconButton>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="h5" fontWeight={700}>Bus {selectedBus.route}</Typography>
                    <Typography variant="body2" color="text.secondary">→ {selectedBus.destination}</Typography>
                  </Box>
                  <IconButton onClick={handleBack}>
                    <CloseIcon />
                  </IconButton>
                </Box>
                
                <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
                  <Chip 
                    icon={<LocationOnIcon sx={{ fontSize: 16 }} />}
                    label={`${formatDist(selectedBus.distance_to_stop)} to ${selectedStop.common_name}`}
                    sx={{ bgcolor: '#e0e7ff', color: '#4338ca', fontWeight: 600 }}
                  />
                  <Chip 
                    label={selectedBus.delay_minutes > 0 ? `${selectedBus.delay_minutes}m late` : 'On time'}
                    sx={{
                      bgcolor: selectedBus.delay_minutes > 0 ? '#fee2e2' : '#d1fae5',
                      color: selectedBus.delay_minutes > 0 ? '#dc2626' : '#059669',
                      fontWeight: 600
                    }}
                  />
                </Box>
                
                {/* ETA Card */}
                <Paper sx={{ p: 4, bgcolor: '#f0fdf4', border: '2px solid #86efac', borderRadius: 4, textAlign: 'center', mb: 3 }}>
                  <Typography variant="h1" fontWeight={800} color="#059669" sx={{ fontSize: '5rem', lineHeight: 1 }}>
                    {formatTime(selectedBus.distance_to_stop * 2)}
                  </Typography>
                  <Typography variant="body1" color="text.secondary" sx={{ mt: 1 }}>
                    Estimated arrival at {selectedStop.common_name}
                  </Typography>
                </Paper>
                
                {/* Stats */}
                <Box sx={{ display: 'flex', justifyContent: 'space-around', mb: 3 }}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h5" fontWeight={700}>{Math.round(selectedBus.speed || 0)}</Typography>
                    <Typography variant="caption" color="text.secondary">km/h speed</Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h5" fontWeight={700}>{formatDist(selectedBus.distance_to_user)}</Typography>
                    <Typography variant="caption" color="text.secondary">from you</Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h5" fontWeight={700}>{selectedBus.operator}</Typography>
                    <Typography variant="caption" color="text.secondary">operator</Typography>
                  </Box>
                </Box>
                
                {/* Route Info */}
                <Paper sx={{ p: 3, bgcolor: '#eff6ff', border: '2px solid #3b82f6', borderRadius: 3 }}>
                  <Typography variant="subtitle1" fontWeight={700} color="#1e40af" sx={{ mb: 1 }}>
                    📍 LIVE BUS LOCATION
                  </Typography>
                  <Typography variant="body2" color="#3b82f6">
                    The <strong>thick blue line</strong> on the map shows where Bus {selectedBus.route} has traveled. 
                    The bus icon updates every 10 seconds with real-time GPS position from BODS.
                  </Typography>
                  {selectedBus.trail && selectedBus.trail.length > 0 && (
                    <Typography variant="caption" color="#3b82f6" sx={{ mt: 1, display: 'block' }}>
                      Trail has {selectedBus.trail.length} GPS points
                    </Typography>
                  )}
                </Paper>
                
                {lastUpdate && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
                    Last updated: {lastUpdate.toLocaleTimeString()}
                  </Typography>
                )}
              </>
            )}
          </Box>
        </Box>
      )}
      
      {/* Hint */}
      {!sheetOpen && (
        <Paper sx={{ position: 'absolute', bottom: 16, left: 16, right: 16, p: 2, borderRadius: 2 }}>
          <Typography fontWeight={600}>📍 {allStops.length} bus stops</Typography>
          <Typography variant="caption" color="text.secondary">Tap a stop → Select a bus → See live route</Typography>
        </Paper>
      )}
    </Box>
  );
}

export default App;
