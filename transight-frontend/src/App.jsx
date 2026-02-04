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

// Bus icon
const busIcon = (route, color, bearing, isSelected) => L.divIcon({
  html: `<div style="
    width: ${isSelected ? 56 : 42}px; height: ${isSelected ? 56 : 42}px;
    background: ${color}; border: ${isSelected ? 4 : 3}px solid white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: white; font-weight: bold; font-size: ${isSelected ? 16 : 12}px;
    box-shadow: 0 ${isSelected ? 6 : 3}px ${isSelected ? 20 : 10}px rgba(0,0,0,${isSelected ? 0.6 : 0.4});
    transform: rotate(${bearing || 0}deg);
    z-index: ${isSelected ? 1000 : 100};
  ">${route}</div>`,
  iconSize: [isSelected ? 56 : 42, isSelected ? 56 : 42],
  iconAnchor: [isSelected ? 28 : 21, isSelected ? 28 : 21],
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

// Map with selected bus and its trail
function MapView({ userLocation, stops, selectedStop, selectedBus, viewMode, onStopClick }) {
  const mapRef = useRef(null);
  const initialized = useRef(false);
  
  useEffect(() => {
    if (!initialized.current && mapRef.current && userLocation) {
      mapRef.current.setView(userLocation, 14);
      initialized.current = true;
    }
  }, [userLocation]);
  
  // Pan to bus when selected
  useEffect(() => {
    if (selectedBus && mapRef.current) {
      mapRef.current.setView([selectedBus.latitude, selectedBus.longitude], 16);
    }
  }, [selectedBus?.bus_id]);
  
  // Build trail for selected bus
  const busTrail = selectedBus?.trail?.length > 1 
    ? selectedBus.trail.map(p => [p.lat, p.lon])
    : [];
  
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
      
      {/* Show stops in map mode */}
      {viewMode === 'stops' && stops.map(stop => (
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
      
      {/* Show selected stop marker in bus detail mode */}
      {viewMode === 'bus-detail' && selectedStop && (
        <Marker
          position={[selectedStop.latitude, selectedStop.longitude]}
          icon={stopIcon(true)}
        >
          <Popup>
            <Typography variant="subtitle2" fontWeight={700}>{selectedStop.common_name}</Typography>
          </Popup>
        </Marker>
      )}
      
      {/* BUS TRAIL - Blue line showing bus path */}
      {viewMode === 'bus-detail' && busTrail.length > 1 && (
        <Polyline
          positions={busTrail}
          pathOptions={{ 
            color: '#3b82f6', 
            weight: 5, 
            opacity: 0.8,
            lineCap: 'round',
            lineJoin: 'round'
          }}
        />
      )}
      
      {/* Selected bus marker */}
      {viewMode === 'bus-detail' && selectedBus && (
        <Marker
          position={[selectedBus.latitude, selectedBus.longitude]}
          icon={busIcon(selectedBus.route, getRouteColor(selectedBus.route), selectedBus.bearing, true)}
          zIndexOffset={2000}
        >
          <Popup>
            <Box sx={{ minWidth: 180 }}>
              <Typography variant="h6" fontWeight={700}>{selectedBus.route}</Typography>
              <Typography variant="subtitle2">→ {selectedBus.destination}</Typography>
              <Typography variant="caption" display="block" sx={{ mt: 1 }}>{selectedBus.operator}</Typography>
              <Chip 
                size="small" 
                label={selectedBus.delay_minutes > 0 ? `${selectedBus.delay_minutes}m late` : 'On time'}
                sx={{ mt: 1, bgcolor: selectedBus.delay_minutes > 0 ? '#fee2e2' : '#d1fae5', color: selectedBus.delay_minutes > 0 ? '#dc2626' : '#059669' }}
              />
            </Box>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}

function App() {
  const [viewMode, setViewMode] = useState('stops');
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
  
  // Bottom sheet height for dragging
  const [sheetHeight, setSheetHeight] = useState(400);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartY = useRef(0);
  const dragStartHeight = useRef(400);
  
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
    if (viewMode !== 'stops' && selectedStop) {
      fetchStopBuses(selectedStop);
      const interval = setInterval(() => fetchStopBuses(selectedStop), 10000);
      return () => clearInterval(interval);
    }
  }, [viewMode, selectedStop, fetchStopBuses]);
  
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
    setSheetHeight(400);
    fetchStopBuses(stop);
  };
  
  const handleBusClick = (bus) => {
    setSelectedBus(bus);
    setViewMode('bus-detail');
    setSheetHeight(350);
  };
  
  const handleBack = () => {
    if (viewMode === 'bus-detail') {
      setSelectedBus(null);
      setViewMode('bus-list');
      setSheetHeight(400);
    } else {
      setSelectedStop(null);
      setStopBuses([]);
      setViewMode('stops');
    }
  };
  
  // Drag handlers
  const handleDragStart = (e) => {
    setIsDragging(true);
    dragStartY.current = e.touches ? e.touches[0].clientY : e.clientY;
    dragStartHeight.current = sheetHeight;
  };
  
  const handleDragMove = (e) => {
    if (!isDragging) return;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    const delta = dragStartY.current - clientY;
    const newHeight = Math.max(200, Math.min(window.innerHeight * 0.8, dragStartHeight.current + delta));
    setSheetHeight(newHeight);
  };
  
  const handleDragEnd = () => {
    setIsDragging(false);
    // Snap to positions
    if (sheetHeight < 250) {
      setSheetHeight(200); // Minimized
    } else if (sheetHeight > 500) {
      setSheetHeight(window.innerHeight * 0.7); // Expanded
    } else {
      setSheetHeight(400); // Default
    }
  };
  
  return (
    <Box sx={{ width: '100%', height: '100vh', position: 'relative', overflow: 'hidden' }}>
      <style>{`
        .user-icon, .stop-icon, .bus-icon { background: transparent !important; border: none !important; }
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
              <Typography color="#9ca3af">
                {viewMode === 'stops' ? 'Search for a stop...' : 
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
      
      {/* Status */}
      <Paper sx={{ position: 'absolute', top: 80, left: 16, px: 2, py: 1, zIndex: 500 }}>
        <Typography variant="body2" fontWeight={600}>
          {viewMode === 'stops' && `${allStops.length} stops`}
          {viewMode === 'bus-list' && `${selectedStop?.common_name}`}
          {viewMode === 'bus-detail' && `Bus ${selectedBus?.route} → ${selectedBus?.destination}`}
        </Typography>
      </Paper>
      
      {/* My Location */}
      <IconButton
        sx={{ position: 'absolute', bottom: viewMode === 'stops' ? 100 : sheetHeight + 20, right: 16, bgcolor: 'white', boxShadow: 2, zIndex: 500 }}
      >
        <MyLocationIcon />
      </IconButton>
      
      {/* Draggable Bottom Sheet */}
      {viewMode !== 'stops' && (
        <Paper 
          sx={{ 
            position: 'absolute', 
            bottom: 0, 
            left: 0, 
            right: 0, 
            height: sheetHeight,
            borderRadius: '24px 24px 0 0',
            overflow: 'hidden',
            zIndex: 1000,
            transition: isDragging ? 'none' : 'height 0.3s ease',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          {/* Drag Handle */}
          <Box 
            onMouseDown={handleDragStart}
            onMouseMove={handleDragMove}
            onMouseUp={handleDragEnd}
            onMouseLeave={handleDragEnd}
            onTouchStart={handleDragStart}
            onTouchMove={handleDragMove}
            onTouchEnd={handleDragEnd}
            sx={{ 
              display: 'flex', 
              justifyContent: 'center', 
              pt: 1.5, 
              pb: 1,
              cursor: 'grab',
              '&:active': { cursor: 'grabbing' }
            }}
          >
            <Box sx={{ width: 48, height: 5, bgcolor: '#d1d5db', borderRadius: 3 }} />
          </Box>
          
          {/* Scrollable Content */}
          <Box sx={{ flex: 1, overflow: 'auto', px: 3, pb: 3 }}>
            {/* BUS LIST VIEW */}
            {viewMode === 'bus-list' && selectedStop && (
              <>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Box>
                    <Typography variant="h6" fontWeight={700}>{selectedStop.common_name}</Typography>
                    <Typography variant="body2" color="text.secondary">{selectedStop.locality}</Typography>
                  </Box>
                  <IconButton size="small" onClick={handleBack}>
                    <CloseIcon />
                  </IconButton>
                </Box>
                
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
                      TAP A BUS TO TRACK ({stopBuses.length})
                    </Typography>
                    
                    {stopBuses.map((bus) => (
                      <Paper 
                        key={bus.bus_id} 
                        onClick={() => handleBusClick(bus)}
                        sx={{ 
                          mb: 2, 
                          p: 2, 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: 2,
                          cursor: 'pointer',
                          '&:hover': { bgcolor: '#f3f4f6' }
                        }}
                      >
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
              </>
            )}
            
            {/* BUS DETAIL VIEW */}
            {viewMode === 'bus-detail' && selectedBus && selectedStop && (
              <>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <IconButton onClick={handleBack} sx={{ mr: 1 }}>
                    <ArrowBackIcon />
                  </IconButton>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="h6" fontWeight={700}>Bus {selectedBus.route}</Typography>
                    <Typography variant="body2" color="text.secondary">→ {selectedBus.destination}</Typography>
                  </Box>
                  <IconButton onClick={handleBack}>
                    <CloseIcon />
                  </IconButton>
                </Box>
                
                <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
                  <Chip 
                    icon={<LocationOnIcon sx={{ fontSize: 16 }} />}
                    label={`${formatDist(selectedBus.distance_to_stop)} to stop`}
                    sx={{ bgcolor: '#e0e7ff', color: '#4338ca' }}
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
                
                <Paper sx={{ p: 3, bgcolor: '#f8fafc', textAlign: 'center', mb: 3 }}>
                  <Typography variant="h1" fontWeight={800} color="#059669" sx={{ mb: 1, fontSize: '4rem' }}>
                    {formatTime(selectedBus.distance_to_stop * 2)}
                  </Typography>
                  <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                    Estimated arrival at {selectedStop.common_name}
                  </Typography>
                  
                  <Box sx={{ display: 'flex', justifyContent: 'center', gap: 4 }}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h5" fontWeight={700}>{Math.round(selectedBus.speed || 0)}</Typography>
                      <Typography variant="caption" color="text.secondary">km/h</Typography>
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
                </Paper>
                
                <Paper sx={{ p: 2, bgcolor: '#eff6ff', border: '1px solid #3b82f6' }}>
                  <Typography variant="subtitle2" color="#1e40af" fontWeight={700} sx={{ mb: 1 }}>
                    📍 LIVE LOCATION ON MAP
                  </Typography>
                  <Typography variant="body2" color="#3b82f6">
                    The blue line on the map shows Bus {selectedBus.route}'s travel path. 
                    The bus marker updates every 10 seconds with real-time position from BODS.
                  </Typography>
                </Paper>
                
                {lastUpdate && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block', textAlign: 'center' }}>
                    Last updated: {lastUpdate.toLocaleTimeString()}
                  </Typography>
                )}
              </>
            )}
          </Box>
        </Paper>
      )}
      
      {/* Hint */}
      {viewMode === 'stops' && (
        <Paper sx={{ position: 'absolute', bottom: 16, left: 16, right: 16, p: 2, borderRadius: 2 }}>
          <Typography fontWeight={600}>📍 {allStops.length} bus stops</Typography>
          <Typography variant="caption" color="text.secondary">Tap a stop → Select a bus → Track with live route</Typography>
        </Paper>
      )}
    </Box>
  );
}

export default App;
