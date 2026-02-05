import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, IconButton, Typography, TextField,
  Paper, Chip, Avatar, Button
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import CloseIcon from '@mui/icons-material/Close';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PeopleIcon from '@mui/icons-material/People';
import TrafficIcon from '@mui/icons-material/Traffic';
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

function MapView({ userLocation, stops, selectedStop, selectedBus, viewMode, onStopClick, route72Geometry, stopBuses, onBusClick }) {
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
  
  useEffect(() => {
    if (selectedStop && mapRef.current && viewMode === 'bus-list') {
      mapRef.current.setView([selectedStop.lat || selectedStop.latitude, selectedStop.lng || selectedStop.longitude], 15);
    }
  }, [selectedStop, viewMode]);
  
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
      
      {/* ROUTE 72 LINE - Always show */}
      {route72Line.length > 1 && (
        <Polyline
          positions={route72Line}
          pathOptions={{ 
            color: '#8b5cf6', 
            weight: 6, 
            opacity: 0.7,
            lineCap: 'round',
            lineJoin: 'round'
          }}
        />
      )}
      
      {/* STOPS VIEW - Show all stops */}
      {viewMode === 'stops' && route72Geometry?.stops?.map(stop => (
        <Marker
          key={stop.id}
          position={[stop.lat, stop.lng]}
          icon={stopIcon(selectedStop?.id === stop.id || selectedStop?.sensor_id === stop.id)}
          eventHandlers={{ click: () => onStopClick(stop) }}
        >
          <Popup>
            <Typography variant="subtitle2">{stop.name}</Typography>
            <Typography variant="caption">Route 72 Stop #{stop.order}</Typography>
          </Popup>
        </Marker>
      ))}
      
      {/* BUS LIST VIEW - Show selected stop and nearby buses */}
      {viewMode === 'bus-list' && selectedStop && (
        <>
          {/* Selected Stop Marker */}
          <Marker 
            position={[selectedStop.lat || selectedStop.latitude, selectedStop.lng || selectedStop.longitude]} 
            icon={stopIcon(true)} 
          />
          
          {/* Buses near this stop */}
          {stopBuses.map(bus => (
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
                  <Typography variant="body2" fontWeight={700} color="#10b981">
                    ETA: {formatTime(bus.eta_minutes)}
                  </Typography>
                </Box>
              </Popup>
            </Marker>
          ))}
        </>
      )}
      
      {/* BUS DETAIL VIEW - Show selected bus trail */}
      {viewMode === 'bus-detail' && selectedBus && (
        <>
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
          
          {/* GPS Trail */}
          {busTrail.length > 1 && (
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
        </>
      )}
    </MapContainer>
  );
}

function App() {
  const [viewMode, setViewMode] = useState('stops');
  const [userLocation, setUserLocation] = useState(null);
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopBuses, setStopBuses] = useState([]);
  const [stopData, setStopData] = useState(null);
  const [selectedBus, setSelectedBus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  
  // Route 72 specific state
  const [route72Geometry, setRoute72Geometry] = useState(null);
  
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
  
  // Fetch Route 72 geometry once on load
  useEffect(() => {
    const fetchRouteGeometry = async () => {
      try {
        const geoRes = await axios.get(`${API_BASE_URL}/route/72/geometry`);
        setRoute72Geometry(geoRes.data);
      } catch (e) {
        console.error("Error fetching Route 72 geometry:", e);
      }
    };
    fetchRouteGeometry();
  }, []);
  
  const fetchStopBuses = useCallback(async (stop) => {
    if (!stop || !userLocation) return;
    setLoading(true);
    try {
      const atcoCode = stop.atco_code || stop.id;
      const res = await axios.get(`${API_BASE_URL}/stop/${atcoCode}/buses`, {
        params: { lat: userLocation[0], lon: userLocation[1] }
      });
      setStopBuses(res.data.buses || []);
      setStopData(res.data.stop_data || null);
      setLastUpdate(new Date());
    } catch (e) {
      console.error("Error fetching buses:", e);
    } finally {
      setLoading(false);
    }
  }, [userLocation]);
  
  // Poll buses when stop is selected
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
    
    // Search in Route 72 stops
    if (route72Geometry?.stops) {
      const results = route72Geometry.stops.filter(stop => 
        stop.name.toLowerCase().includes(query.toLowerCase())
      );
      setSearchResults(results.map(s => ({
        ...s,
        common_name: s.name,
        latitude: s.lat,
        longitude: s.lng
      })));
    }
  };
  
  const handleStopClick = (stop) => {
    setSelectedStop(stop);
    setSelectedBus(null);
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
      setViewMode('bus-list');
    } else if (viewMode === 'bus-list') {
      setSelectedStop(null);
      setStopBuses([]);
      setStopData(null);
      setSheetOpen(false);
      setViewMode('stops');
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
      setSheetExpanded(true);
    } else if (diff < -50) {
      setSheetExpanded(false);
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
          stops={[]}
          selectedStop={selectedStop}
          selectedBus={selectedBus}
          viewMode={viewMode}
          onStopClick={handleStopClick}
          route72Geometry={route72Geometry}
          stopBuses={stopBuses}
          onBusClick={handleBusClick}
        />
      </Box>
      
      {/* Back Button */}
      {(viewMode === 'bus-list' || viewMode === 'bus-detail') && (
        <Box sx={{ position: 'absolute', top: 16, left: 16, zIndex: 1000 }}>
          <IconButton 
            onClick={handleBack}
            sx={{ bgcolor: 'white', boxShadow: 2, '&:hover': { bgcolor: '#f5f5f5' } }}
          >
            <ArrowBackIcon />
          </IconButton>
        </Box>
      )}
      
      {/* Route 72 Header */}
      {viewMode === 'stops' && (
        <Box sx={{ position: 'absolute', top: 16, left: 16, right: 16, zIndex: 1000 }}>
          <Paper elevation={3} sx={{ borderRadius: 2, px: 2, py: 1.5, bgcolor: '#8b5cf6', color: 'white' }}>
            <Typography fontWeight={700} variant="h6">Route 72</Typography>
            <Typography variant="body2">Temple Meads ↔ UWE Frenchay</Typography>
            <Typography variant="caption">Tap a stop to see live buses</Typography>
          </Paper>
        </Box>
      )}
      
      {/* Search Bar */}
      {viewMode === 'stops' && (
        <Box sx={{ position: 'absolute', top: 100, left: 16, right: 16, zIndex: 1000 }}>
          <Paper elevation={3} sx={{ borderRadius: 3, overflow: 'hidden' }}>
            {!searchOpen ? (
              <Box 
                onClick={() => setSearchOpen(true)}
                sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1.5, bgcolor: 'white', cursor: 'pointer' }}
              >
                <SearchIcon sx={{ color: '#9ca3af', mr: 1.5 }} />
                <Typography color="#9ca3af">Search Route 72 stops...</Typography>
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
                        key={stop.id}
                        onClick={() => {
                          handleStopClick(stop);
                          setSearchOpen(false);
                          setSearchQuery('');
                          setSearchResults([]);
                        }}
                        sx={{ px: 2, py: 1.5, borderBottom: '1px solid #f3f4f6', cursor: 'pointer', '&:hover': { bgcolor: '#f9fafb' } }}
                      >
                        <Typography fontWeight={600}>{stop.name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Route 72 Stop #{stop.order}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            )}
          </Paper>
        </Box>
      )}
      
      {/* Stop Info Card (when stop selected) */}
      {viewMode === 'bus-list' && selectedStop && (
        <Box sx={{ position: 'absolute', top: 80, left: 16, right: 16, zIndex: 1000 }}>
          <Paper elevation={3} sx={{ borderRadius: 2, p: 2, bgcolor: 'white' }}>
            <Typography variant="h6" fontWeight={700}>{selectedStop.name}</Typography>
            <Typography variant="body2" color="text.secondary">Route 72 Stop #{selectedStop.order}</Typography>
            
            {/* LIVE Data Info */}
            {stopData && (
              <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid #e5e7eb' }}>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                  LIVE DATA:
                </Typography>
                
                {/* Traffic Info */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <TrafficIcon fontSize="small" color={stopData.traffic_delay > 5 ? "error" : stopData.traffic_delay > 0 ? "warning" : "success"} />
                  <Typography variant="body2">
                    Traffic: {stopData.current_speed > 0 ? `${stopData.current_speed} km/h` : 'No data'} 
                    {stopData.traffic_delay > 0 && `(+${Math.round(stopData.traffic_delay)} min delay)`}
                    {stopData.traffic_delay === 0 && '(Clear)'}
                  </Typography>
                </Box>
                
                {/* Crowd Info */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                  <Chip 
                    icon={<PeopleIcon />}
                    label={`${stopData.crowd_count} waiting`}
                    size="small"
                    color={stopData.crowd_count > 10 ? "error" : stopData.crowd_count > 5 ? "warning" : "success"}
                    variant={stopData.is_live ? "filled" : "outlined"}
                  />
                  <Typography variant="caption" color={stopData.is_live ? "success.main" : "text.secondary"}>
                    {stopData.is_live ? "● Live from camera" : stopData.crowd_count > 0 ? "From database" : "No sensor data"}
                  </Typography>
                </Box>
                
                {/* Total Delay */}
                {stopData.predicted_delay > 0 && (
                  <Box sx={{ mt: 1, p: 1, bgcolor: '#fff3e0', borderRadius: 1 }}>
                    <Typography variant="body2" fontWeight={700} color="warning.dark">
                      Total Predicted Delay: {stopData.predicted_delay.toFixed(1)} min
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      ({stopData.traffic_delay > 0 ? `Traffic: ${stopData.traffic_delay}min + ` : ''}
                      Crowd: {(stopData.predicted_delay - stopData.traffic_delay).toFixed(1)}min)
                    </Typography>
                  </Box>
                )}
              </Box>
            )}
          </Paper>
        </Box>
      )}
      
      {/* Bottom Sheet */}
      {sheetOpen && (
        <Box
          ref={sheetRef}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            bgcolor: 'white',
            borderRadius: '24px 24px 0 0',
            boxShadow: '0 -4px 20px rgba(0,0,0,0.1)',
            zIndex: 1000,
            maxHeight: sheetExpanded ? '80vh' : '40vh',
            transform: `translateY(${sheetExpanded ? 0 : '10%'})`,
            transition: 'transform 0.3s, max-height 0.3s'
          }}
        >
          {/* Drag Handle */}
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 1.5 }}>
            <Box sx={{ width: 40, height: 4, bgcolor: '#e5e7eb', borderRadius: 2 }} />
          </Box>
          
          {/* Content */}
          <Box sx={{ px: 2, pb: 3, overflow: 'auto', maxHeight: 'calc(80vh - 50px)' }}>
            {/* Buses List */}
            {viewMode === 'bus-list' && (
              <>
                <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
                  Buses Near Stop ({stopBuses.length})
                </Typography>
                
                {loading && stopBuses.length === 0 ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress />
                  </Box>
                ) : stopBuses.length === 0 ? (
                  <Typography color="text.secondary" align="center" py={4}>
                    No Route 72 buses nearby
                  </Typography>
                ) : (
                  stopBuses.map((bus) => (
                    <Paper
                      key={bus.bus_id}
                      onClick={() => handleBusClick(bus)}
                      sx={{
                        p: 2,
                        mb: 1.5,
                        borderRadius: 2,
                        cursor: 'pointer',
                        '&:hover': { bgcolor: '#f9fafb' }
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Avatar sx={{ bgcolor: '#8b5cf6', fontWeight: 700 }}>72</Avatar>
                        <Box sx={{ flex: 1 }}>
                          <Typography fontWeight={600}>→ {bus.destination}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {formatDist(bus.distance_to_stop)} away • {Math.round(bus.speed || 0)} km/h
                          </Typography>
                        </Box>
                        <Box sx={{ textAlign: 'right' }}>
                          <Typography variant="h6" fontWeight={700} color="primary">
                            {formatTime(bus.eta_minutes)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            ETA
                          </Typography>
                        </Box>
                      </Box>
                    </Paper>
                  ))
                )}
              </>
            )}
            
            {/* Bus Detail */}
            {viewMode === 'bus-detail' && selectedBus && (
              <>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                  <IconButton onClick={handleBack} sx={{ mr: 1 }}>
                    <ArrowBackIcon />
                  </IconButton>
                  <Typography variant="h6" fontWeight={700}>Bus Details</Typography>
                </Box>
                
                {/* Main Bus Info */}
                <Paper sx={{ p: 3, borderRadius: 3, bgcolor: '#8b5cf6', color: 'white', mb: 2 }}>
                  <Typography variant="h3" fontWeight={800} sx={{ mb: 1 }}>72</Typography>
                  <Typography variant="h6">→ {selectedBus.destination}</Typography>
                  <Box sx={{ mt: 2, display: 'flex', gap: 3 }}>
                    <Box>
                      <Typography variant="caption" sx={{ opacity: 0.8 }}>Speed</Typography>
                      <Typography fontWeight={700}>{Math.round(selectedBus.speed || 0)} km/h</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" sx={{ opacity: 0.8 }}>Distance</Typography>
                      <Typography fontWeight={700}>{formatDist(selectedBus.distance_to_stop || 0)}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" sx={{ opacity: 0.8 }}>ETA</Typography>
                      <Typography fontWeight={700}>{formatTime(selectedBus.eta_minutes)}</Typography>
                    </Box>
                  </Box>
                </Paper>
                
                {/* ETA Breakdown */}
                <Paper sx={{ p: 2, borderRadius: 2, bgcolor: '#f5f5f5', mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>How ETA is calculated:</Typography>
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">Travel time:</Typography>
                    <Typography variant="body2">{selectedBus.travel_time?.toFixed(1) || '?'} min</Typography>
                  </Box>
                  
                  {selectedBus.predicted_delay > 0 && (
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2" color="warning.main">Predicted delay:</Typography>
                      <Typography variant="body2" color="warning.main">+{selectedBus.predicted_delay?.toFixed(1)} min</Typography>
                    </Box>
                  )}
                  
                  <Box sx={{ borderTop: '1px solid #ddd', my: 1 }} />
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" fontWeight={700}>Total ETA:</Typography>
                    <Typography variant="body2" fontWeight={700}>{formatTime(selectedBus.eta_minutes)}</Typography>
                  </Box>
                </Paper>
                
                {/* Data Sources */}
                {stopData && (
                  <Paper sx={{ p: 2, borderRadius: 2, bgcolor: '#e3f2fd', mb: 2 }}>
                    <Typography variant="caption" color="text.secondary" display="block">DATA SOURCES:</Typography>
                    <Typography variant="body2">• Bus GPS: BODS API (Live)</Typography>
                    <Typography variant="body2">• Traffic: TomTom API ({stopData.current_speed > 0 ? 'Live' : 'Fallback'})</Typography>
                    <Typography variant="body2">• Crowd: {stopData.is_live ? 'Camera (Live)' : stopData.crowd_count > 0 ? 'Database' : 'No data (assumed 0)'}</Typography>
                  </Paper>
                )}
                
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" color="text.secondary" align="center">
                    Last updated: {lastUpdate?.toLocaleTimeString()}
                  </Typography>
                </Box>
              </>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
}

export default App;
