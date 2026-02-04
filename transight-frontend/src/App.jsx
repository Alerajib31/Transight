import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, AppBar, Toolbar, IconButton, Typography, TextField,
  Paper, InputAdornment, Chip, List, ListItem, Button, Slide, Avatar,
  BottomSheet
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import CloseIcon from '@mui/icons-material/Close';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
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

// Icons
const userLocationIcon = L.divIcon({
  className: 'user-location',
  html: `<div style="
    width: 24px; height: 24px;
    background: #3b82f6;
    border: 4px solid white;
    border-radius: 50%;
    box-shadow: 0 4px 12px rgba(59,130,246,0.5);
    animation: pulse 2s infinite;
  "></div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12]
});

const stopIcon = L.divIcon({
  className: 'stop-icon',
  html: `<div style="
    width: 32px; height: 32px;
    background: white;
    border: 3px solid #6366f1;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  ">
    <span style="font-size: 14px;">🚏</span>
  </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16]
});

const selectedStopIcon = L.divIcon({
  className: 'stop-icon-selected',
  html: `<div style="
    width: 40px; height: 40px;
    background: #10b981;
    border: 4px solid white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 12px rgba(16,185,129,0.5);
    animation: bounce 1s infinite;
  ">
    <span style="font-size: 18px;">🚏</span>
  </div>`,
  iconSize: [40, 40],
  iconAnchor: [20, 20]
});

const busIcon = (route, color) => L.divIcon({
  className: 'bus-icon',
  html: `<div style="
    width: 40px; height: 40px;
    background: ${color};
    border: 3px solid white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: white; font-weight: bold; font-size: 12px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.4);
  ">${route}</div>`,
  iconSize: [40, 40],
  iconAnchor: [20, 20]
});

// Route colors
const ROUTE_COLORS = ['#6366f1', '#ec4899', '#8b5cf6', '#14b8a6', '#f59e0b', '#ef4444', '#3b82f6', '#10b981', '#f97316'];
const getRouteColor = (route) => {
  let hash = 0;
  for (let i = 0; i < route.length; i++) {
    hash = route.charCodeAt(i) + ((hash << 5) - hash);
  }
  return ROUTE_COLORS[Math.abs(hash) % ROUTE_COLORS.length];
};

const formatTime = (minutes) => minutes <= 1 ? 'Due' : `${Math.round(minutes)} min`;
const formatDistance = (km) => km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`;

// Map Component - Does NOT auto-recenter
function MapComponent({ userLocation, stops, selectedStop, buses, onStopClick }) {
  const mapRef = useRef(null);
  const initializedRef = useRef(false);
  
  // Only set view on first load
  useEffect(() => {
    if (!initializedRef.current && mapRef.current && userLocation) {
      mapRef.current.setView(userLocation, 15);
      initializedRef.current = true;
    }
  }, [userLocation]);
  
  // When stop selected, pan to it (but don't force on every render)
  useEffect(() => {
    if (selectedStop && mapRef.current) {
      mapRef.current.setView([selectedStop.latitude, selectedStop.longitude], 17);
    }
  }, [selectedStop?.atco_code]);
  
  return (
    <MapContainer
      center={userLocation || [51.4545, -2.5879]}
      zoom={15}
      style={{ height: "100%", width: "100%" }}
      zoomControl={false}
      whenCreated={(map) => { mapRef.current = map; }}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      
      {/* User location */}
      {userLocation && (
        <Marker position={userLocation} icon={userLocationIcon} zIndexOffset={1000}>
          <Popup><Typography variant="subtitle2">You are here</Typography></Popup>
        </Marker>
      )}
      
      {/* Bus stops */}
      {stops.map(stop => (
        <Marker
          key={stop.atco_code}
          position={[stop.latitude, stop.longitude]}
          icon={selectedStop?.atco_code === stop.atco_code ? selectedStopIcon : stopIcon}
          eventHandlers={{ click: () => onStopClick(stop) }}
          zIndexOffset={selectedStop?.atco_code === stop.atco_code ? 500 : 0}
        />
      ))}
      
      {/* Buses for selected stop only */}
      {buses.map(bus => (
        <Marker
          key={bus.bus_id}
          position={[bus.latitude, bus.longitude]}
          icon={busIcon(bus.route, getRouteColor(bus.route))}
        >
          <Popup>
            <Box sx={{ minWidth: 150 }}>
              <Typography variant="subtitle2" fontWeight={700}>{bus.route} → {bus.destination}</Typography>
              <Typography variant="caption" display="block">{bus.operator}</Typography>
              <Typography variant="caption" display="block" color={bus.delay_minutes > 0 ? 'error' : 'success'}>
                {bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
              </Typography>
            </Box>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

// Main App
function App() {
  // State
  const [userLocation, setUserLocation] = useState(null);
  const [nearbyStops, setNearbyStops] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopBuses, setStopBuses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  // Search state
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  
  const API_BASE_URL = "http://127.0.0.1:8000";
  
  // Get user location once
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setUserLocation([pos.coords.latitude, pos.coords.longitude]),
        () => setUserLocation([51.4545, -2.5879]) // Bristol fallback
      );
    } else {
      setUserLocation([51.4545, -2.5879]);
    }
  }, []);
  
  // Fetch nearby stops when location available
  const fetchNearbyStops = useCallback(async () => {
    if (!userLocation) return;
    
    try {
      const res = await axios.get(`${API_BASE_URL}/nearby-stops`, {
        params: { latitude: userLocation[0], longitude: userLocation[1], radius: 5 }
      });
      setNearbyStops(res.data.stops || []);
    } catch (e) {
      console.error("Error fetching stops:", e);
    }
  }, [userLocation]);
  
  useEffect(() => {
    fetchNearbyStops();
  }, [fetchNearbyStops]);
  
  // Fetch buses for selected stop
  const fetchBusesForStop = useCallback(async (stop) => {
    if (!stop || !userLocation) return;
    
    setLoading(true);
    try {
      // Get buses heading to this stop
      const res = await axios.get(`${API_BASE_URL}/my-buses`, {
        params: { 
          lat: userLocation[0], 
          lon: userLocation[1], 
          radius: 10 // Larger radius to find buses heading to this stop
        }
      });
      
      // Filter buses for this specific stop
      const buses = (res.data.buses || []).filter(b => 
        b.next_stop_ref === stop.atco_code ||
        (b.nearest_stop === stop.common_name && b.nearest_stop_dist < 1)
      );
      
      setStopBuses(buses);
      setLastUpdate(new Date());
    } catch (e) {
      console.error("Error fetching buses:", e);
    } finally {
      setLoading(false);
    }
  }, [userLocation]);
  
  // Auto-refresh buses for selected stop
  useEffect(() => {
    if (!selectedStop) return;
    
    fetchBusesForStop(selectedStop);
    const interval = setInterval(() => fetchBusesForStop(selectedStop), 15000);
    return () => clearInterval(interval);
  }, [selectedStop, fetchBusesForStop]);
  
  // Handle stop selection
  const handleStopClick = (stop) => {
    setSelectedStop(stop);
    fetchBusesForStop(stop);
  };
  
  // Search stops
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
  
  // Handle search result click
  const handleSearchResultClick = (stop) => {
    setSearchOpen(false);
    setSearchQuery('');
    setSearchResults([]);
    handleStopClick(stop);
  };
  
  return (
    <Box sx={{ width: '100%', height: '100vh', overflow: 'hidden', bgcolor: '#0a0e27', position: 'relative' }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.1); opacity: 0.8; }
        }
        @keyframes bounce {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-5px); }
        }
        .user-location { background: transparent !important; border: none !important; }
        .stop-icon { background: transparent !important; border: none !important; }
        .stop-icon-selected { background: transparent !important; border: none !important; }
        .bus-icon { background: transparent !important; border: none !important; }
      `}</style>
      
      {/* Map - Always visible as background */}
      <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
        <MapComponent
          userLocation={userLocation}
          stops={nearbyStops}
          selectedStop={selectedStop}
          buses={selectedStop ? stopBuses : []}
          onStopClick={handleStopClick}
        />
      </Box>
      
      {/* Top Bar with Search */}
      <Box sx={{ 
        position: 'absolute', 
        top: 16, 
        left: 16, 
        right: 16,
        zIndex: 1000
      }}>
        <Paper elevation={3} sx={{ borderRadius: 3, overflow: 'hidden' }}>
          {!searchOpen ? (
            // Default search bar
            <Box 
              onClick={() => setSearchOpen(true)}
              sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                px: 2, 
                py: 1.5,
                bgcolor: 'white',
                cursor: 'pointer'
              }}
            >
              <SearchIcon sx={{ color: '#9ca3af', mr: 1.5 }} />
              <Typography color="#9ca3af">Search for a stop...</Typography>
            </Box>
          ) : (
            // Expanded search
            <Box sx={{ bgcolor: 'white' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1 }}>
                <SearchIcon sx={{ color: '#9ca3af', mr: 1.5 }} />
                <TextField
                  fullWidth
                  placeholder="Search for a stop..."
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  autoFocus
                  variant="standard"
                  InputProps={{ disableUnderline: true }}
                />
                <IconButton size="small" onClick={() => {
                  setSearchOpen(false);
                  setSearchQuery('');
                  setSearchResults([]);
                }}>
                  <CloseIcon />
                </IconButton>
              </Box>
              
              {/* Search Results */}
              {searchResults.length > 0 && (
                <List sx={{ maxHeight: 300, overflow: 'auto', borderTop: '1px solid #e5e7eb' }}>
                  {searchResults.map((stop) => (
                    <Box
                      key={stop.atco_code}
                      onClick={() => handleSearchResultClick(stop)}
                      sx={{
                        px: 2, py: 1.5,
                        borderBottom: '1px solid #f3f4f6',
                        cursor: 'pointer',
                        '&:hover': { bgcolor: '#f9fafb' }
                      }}
                    >
                      <Typography fontWeight={600} color="#1f2937">{stop.common_name}</Typography>
                      <Typography variant="caption" color="#6b7280">
                        {stop.locality} {stop.distance_km && `• ${formatDistance(stop.distance_km)}`}
                      </Typography>
                    </Box>
                  ))}
                </List>
              )}
            </Box>
          )}
        </Paper>
      </Box>
      
      {/* My Location Button */}
      <IconButton
        onClick={() => {
          if (userLocation && window.map) {
            window.map.setView(userLocation, 15);
          }
        }}
        sx={{
          position: 'absolute',
          bottom: selectedStop ? 320 : 100,
          right: 16,
          bgcolor: 'white',
          boxShadow: 2,
          '&:hover': { bgcolor: '#f3f4f6' }
        }}
      >
        <MyLocationIcon />
      </IconButton>
      
      {/* Stop Detail Bottom Sheet */}
      {selectedStop && (
        <Slide direction="up" in={true}>
          <Paper 
            sx={{ 
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              maxHeight: '50vh',
              borderRadius: '20px 20px 0 0',
              zIndex: 1000,
              overflow: 'auto'
            }}
          >
            {/* Handle bar */}
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 1, pb: 0.5 }}>
              <Box sx={{ width: 40, height: 4, bgcolor: '#d1d5db', borderRadius: 2 }} />
            </Box>
            
            {/* Header */}
            <Box sx={{ px: 2, pb: 2, borderBottom: '1px solid #e5e7eb' }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h6" fontWeight={700} color="#1f2937">
                    {selectedStop.common_name}
                  </Typography>
                  <Typography variant="body2" color="#6b7280">
                    {selectedStop.indicator} {selectedStop.locality} • {formatDistance(selectedStop.distance_km)}
                  </Typography>
                </Box>
                <IconButton size="small" onClick={() => {
                  setSelectedStop(null);
                  setStopBuses([]);
                }}>
                  <CloseIcon />
                </IconButton>
              </Box>
              
              {lastUpdate && (
                <Typography variant="caption" color="#9ca3af" sx={{ mt: 0.5, display: 'block' }}>
                  Updated {lastUpdate.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                </Typography>
              )}
            </Box>
            
            {/* Buses List */}
            <Box sx={{ p: 2 }}>
              {loading && stopBuses.length === 0 ? (
                <Box display="flex" justifyContent="center" py={4}>
                  <CircularProgress size={30} />
                </Box>
              ) : stopBuses.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <Typography color="#6b7280">No buses currently approaching</Typography>
                </Box>
              ) : (
                <>
                  <Typography variant="caption" color="#6b7280" sx={{ mb: 2, display: 'block' }}>
                    {stopBuses.length} BUS{stopBuses.length !== 1 ? 'ES' : ''} APPROACHING
                  </Typography>
                  
                  {stopBuses.map((bus, idx) => (
                    <Paper
                      key={bus.bus_id}
                      sx={{
                        mb: 1.5,
                        p: 2,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 2,
                        bgcolor: 'white',
                        border: '1px solid #e5e7eb',
                        borderRadius: 2
                      }}
                    >
                      {/* Route Number */}
                      <Avatar
                        sx={{
                          bgcolor: getRouteColor(bus.route),
                          color: 'white',
                          fontWeight: 700,
                          width: 48,
                          height: 48,
                          fontSize: '1rem'
                        }}
                      >
                        {bus.route}
                      </Avatar>
                      
                      {/* Info */}
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="subtitle1" fontWeight={700} color="#1f2937" noWrap>
                          {bus.destination}
                        </Typography>
                        <Typography variant="caption" color="#6b7280" display="block">
                          {bus.operator}
                        </Typography>
                        <Chip
                          size="small"
                          label={bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
                          sx={{
                            mt: 0.5,
                            height: 20,
                            fontSize: '0.7rem',
                            bgcolor: bus.delay_minutes > 0 ? '#fee2e2' : '#d1fae5',
                            color: bus.delay_minutes > 0 ? '#dc2626' : '#059669',
                            fontWeight: 600
                          }}
                        />
                      </Box>
                      
                      {/* Arrival Time */}
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography variant="h5" fontWeight={800} color="#059669">
                          {formatTime(Math.max(1, bus.distance_to_user * 2))}
                        </Typography>
                        <Typography variant="caption" color="#9ca3af">
                          <AccessTimeIcon sx={{ fontSize: 12, mr: 0.5, verticalAlign: 'middle' }} />
                          arriving
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
      
      {/* Nearby stops hint when no stop selected */}
      {!selectedStop && nearbyStops.length > 0 && (
        <Paper
          sx={{
            position: 'absolute',
            bottom: 16,
            left: 16,
            right: 16,
            p: 2,
            borderRadius: 2,
            zIndex: 500
          }}
        >
          <Typography variant="subtitle2" fontWeight={600} color="#1f2937">
            📍 {nearbyStops.length} stops nearby
          </Typography>
          <Typography variant="caption" color="#6b7280">
            Tap a stop on the map to see arriving buses
          </Typography>
        </Paper>
      )}
    </Box>
  );
}

export default App;
