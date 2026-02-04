import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, AppBar, Toolbar, IconButton, Typography, TextField,
  Paper, useTheme, useMediaQuery, InputAdornment, Chip,
  List, ListItem, ListItemButton, ListItemText, ListItemIcon,
  BottomNavigation, BottomNavigationAction, Button, Slide, Badge,
  Autocomplete, Dialog, DialogTitle, DialogContent
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import NavigationIcon from '@mui/icons-material/Navigation';
import MapIcon from '@mui/icons-material/Map';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import CloseIcon from '@mui/icons-material/Close';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';

// Fix Leaflet icons
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Bus icon with rotation
const createBusIcon = (bearing, route, color) => {
  return L.divIcon({
    className: 'bus-marker',
    html: `
      <div style="
        width: 36px; 
        height: 36px; 
        background: ${color}; 
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 3px 10px rgba(0,0,0,0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 11px;
        transform: rotate(${bearing}deg);
        transition: transform 0.3s ease;
      ">
        <span style="transform: rotate(${-bearing}deg)">${route}</span>
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 18]
  });
};

const userIcon = L.divIcon({
  className: 'user-marker',
  html: `<div style="
    width: 20px; height: 20px;
    background: #3b82f6;
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 2px 8px rgba(59,130,246,0.5);
  "></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

const stopIcon = new L.Icon({
  iconUrl: 'https://cdn-icons-png.flaticon.com/512/684/684908.png',
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

// Route colors
const ROUTE_COLORS = ['#6366f1', '#ec4899', '#8b5cf6', '#14b8a6', '#f59e0b', '#ef4444', '#3b82f6', '#10b981'];
const routeColorMap = {};
let colorIdx = 0;

const getRouteColor = (route) => {
  if (!routeColorMap[route]) {
    routeColorMap[route] = ROUTE_COLORS[colorIdx % ROUTE_COLORS.length];
    colorIdx++;
  }
  return routeColorMap[route];
};

// Format time
const formatTime = (minutes) => {
  if (minutes <= 1) return 'Due';
  return `${Math.round(minutes)} min`;
};

const formatDistance = (km) => km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`;

// Map component with stable center
function MapController({ center }) {
  const map = useMap();
  const centerRef = useRef(center);
  
  useEffect(() => {
    if (center[0] !== centerRef.current[0] || center[1] !== centerRef.current[1]) {
      centerRef.current = center;
      map.setView(center, 15);
    }
  }, [center, map]);
  
  return null;
}

// Animated bus marker
const BusMarker = React.memo(({ bus, isSelected, onClick }) => {
  const markerRef = useRef(null);
  const positionRef = useRef([bus.latitude, bus.longitude]);
  
  useEffect(() => {
    if (markerRef.current) {
      // Smooth transition to new position
      markerRef.current.setLatLng([bus.latitude, bus.longitude]);
    }
    positionRef.current = [bus.latitude, bus.longitude];
  }, [bus.latitude, bus.longitude]);
  
  const icon = useMemo(() => 
    createBusIcon(bus.bearing || 0, bus.route, getRouteColor(bus.route)),
    [bus.route, bus.bearing]
  );
  
  return (
    <Marker
      ref={markerRef}
      position={positionRef.current}
      icon={icon}
      eventHandlers={{ click: () => onClick(bus) }}
    >
      <Popup>
        <Box sx={{ minWidth: 180, p: 0.5 }}>
          <Typography variant="subtitle2" fontWeight={700}>
            {bus.route} → {bus.destination}
          </Typography>
          <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
            {bus.operator}
          </Typography>
          <Typography variant="caption" display="block">
            Speed: {Math.round(bus.speed || 0)} km/h
          </Typography>
          <Typography variant="caption" display="block" color={bus.delay_minutes > 0 ? 'error.main' : 'success.main'}>
            {bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
          </Typography>
        </Box>
      </Popup>
    </Marker>
  );
});

// Main App
function App() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  // Navigation
  const [activeTab, setActiveTab] = useState(0);
  const [selectedStop, setSelectedStop] = useState(null);
  const [selectedBus, setSelectedBus] = useState(null);
  const [showJourneySearch, setShowJourneySearch] = useState(false);
  
  // Location
  const [userLocation, setUserLocation] = useState(null);
  const [locationError, setLocationError] = useState(false);
  
  // Data
  const [nearbyStops, setNearbyStops] = useState([]);
  const [relevantBuses, setRelevantBuses] = useState([]);
  const [allBuses, setAllBuses] = useState([]);
  const [searchResults, setSearchResults] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Destination search
  const [destSearch, setDestSearch] = useState('');
  const [destOptions, setDestOptions] = useState([]);
  const [selectedDest, setSelectedDest] = useState(null);
  
  const API_BASE_URL = "http://127.0.0.1:8000";
  const mapRef = useRef(null);
  
  // Get user location
  const getUserLocation = useCallback(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = [pos.coords.latitude, pos.coords.longitude];
          setUserLocation(loc);
          setLocationError(false);
        },
        (err) => {
          console.error("Geolocation error:", err);
          setLocationError(true);
          // Default to Bristol for testing
          setUserLocation([51.4545, -2.5879]);
        },
        { enableHighAccuracy: true }
      );
    }
  }, []);
  
  // Fetch my buses (buses approaching my stops)
  const fetchMyBuses = useCallback(async () => {
    if (!userLocation) return;
    
    try {
      const res = await axios.get(`${API_BASE_URL}/my-buses`, {
        params: { lat: userLocation[0], lon: userLocation[1], radius: 1.5 }
      });
      
      setNearbyStops(res.data.stops || []);
      setRelevantBuses(res.data.buses || []);
      setLastUpdate(new Date());
    } catch (e) {
      console.error("Error fetching buses:", e);
    }
  }, [userLocation]);
  
  // Fetch all buses for map
  const fetchAllBuses = useCallback(async () => {
    if (!userLocation) return;
    
    try {
      const res = await axios.get(`${API_BASE_URL}/all-buses-in-area`, {
        params: { lat: userLocation[0], lon: userLocation[1], radius: 8 }
      });
      setAllBuses(res.data.buses || []);
    } catch (e) {
      console.error("Error fetching all buses:", e);
    }
  }, [userLocation]);
  
  // Search stops
  const searchStops = useCallback(async (query) => {
    if (!query) {
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
  }, [userLocation]);
  
  // Destination search
  const searchDestination = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setDestOptions([]);
      return;
    }
    
    try {
      const res = await axios.get(`${API_BASE_URL}/search-stops`, {
        params: { q: query, lat: userLocation?.[0], lon: userLocation?.[1] }
      });
      setDestOptions(res.data.results || []);
    } catch (e) {
      console.error("Dest search error:", e);
    }
  }, [userLocation]);
  
  // Initial load
  useEffect(() => {
    getUserLocation();
  }, [getUserLocation]);
  
  // Auto-refresh
  useEffect(() => {
    if (!userLocation) return;
    
    fetchMyBuses();
    fetchAllBuses();
    
    const interval = setInterval(() => {
      fetchMyBuses();
      fetchAllBuses();
    }, 10000);
    
    return () => clearInterval(interval);
  }, [userLocation, fetchMyBuses, fetchAllBuses]);
  
  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => searchStops(searchQuery), 300);
    return () => clearTimeout(t);
  }, [searchQuery, searchStops]);
  
  // Debounced destination search
  useEffect(() => {
    const t = setTimeout(() => searchDestination(destSearch), 400);
    return () => clearTimeout(t);
  }, [destSearch, searchDestination]);
  
  // Views
  const NearbyView = () => (
    <Box sx={{ height: '100%', overflow: 'auto', bgcolor: '#0a0e27' }}>
      <AppBar position="sticky" sx={{ bgcolor: '#1e3a8a' }}>
        <Toolbar>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" fontWeight={700}>My Buses</Typography>
            {lastUpdate && (
              <Typography variant="caption" sx={{ opacity: 0.8 }}>
                Updated {lastUpdate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
              </Typography>
            )}
          </Box>
          <Button 
            variant="contained" 
            size="small"
            onClick={() => setShowJourneySearch(true)}
            sx={{ bgcolor: '#10b981', '&:hover': { bgcolor: '#059669' } }}
          >
            Plan Journey
          </Button>
          <IconButton color="inherit" onClick={getUserLocation} sx={{ ml: 1 }}>
            <MyLocationIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
      
      <Box sx={{ p: 2 }}>
        {/* Active Routes */}
        {relevantBuses.length > 0 && (
          <>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1.5, display: 'block' }}>
              BUSES NEAR YOU ({relevantBuses.length})
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
              {Object.entries(
                relevantBuses.reduce((acc, b) => {
                  acc[b.route] = (acc[b.route] || 0) + 1;
                  return acc;
                }, {})
              ).map(([route, count]) => (
                <Chip 
                  key={route}
                  label={`${route} (${count})`}
                  size="small"
                  sx={{ 
                    bgcolor: `${getRouteColor(route)}30`,
                    color: getRouteColor(route),
                    border: `1px solid ${getRouteColor(route)}50`,
                    fontWeight: 600
                  }}
                  onClick={() => setSelectedBus(relevantBuses.find(b => b.route === route))}
                />
              ))}
            </Box>
          </>
        )}
        
        {/* Stops with approaching buses */}
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1.5, display: 'block' }}>
          NEARBY STOPS ({nearbyStops.length})
        </Typography>
        
        {nearbyStops.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)' }}>
            <LocationOnIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1, color: 'white' }} />
            <Typography color="rgba(255,255,255,0.6)">No stops found nearby</Typography>
            <Typography variant="caption" color="rgba(255,255,255,0.4)" display="block" sx={{ mt: 1 }}>
              Try searching for your destination
            </Typography>
            <Button 
              variant="outlined" 
              size="small"
              onClick={() => setShowJourneySearch(true)}
              sx={{ mt: 2, color: '#6366f1', borderColor: '#6366f1' }}
            >
              Plan a Journey
            </Button>
          </Paper>
        ) : (
          <List sx={{ gap: 1, display: 'flex', flexDirection: 'column' }}>
            {nearbyStops.map((stop, idx) => {
              const stopBuses = relevantBuses.filter(b => b.next_stop_ref === stop.atco_code);
              
              return (
                <Slide key={stop.atco_code} direction="up" in={true} style={{ transitionDelay: idx * 30 }}>
                  <Paper 
                    component={ListItemButton}
                    onClick={() => setSelectedStop(stop)}
                    sx={{ 
                      bgcolor: stopBuses.length > 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(30, 41, 59, 0.8)', 
                      border: stopBuses.length > 0 ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(99, 102, 241, 0.2)',
                      '&:hover': { bgcolor: stopBuses.length > 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(99, 102, 241, 0.15)' }
                    }}
                  >
                    <ListItemIcon>
                      <Box sx={{ 
                        width: 40, height: 40, 
                        bgcolor: stopBuses.length > 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(99, 102, 241, 0.2)', 
                        borderRadius: '50%',
                        display: 'flex', alignItems: 'center', justifyContent: 'center'
                      }}>
                        <LocationOnIcon sx={{ color: stopBuses.length > 0 ? '#10b981' : '#6366f1' }} />
                      </Box>
                    </ListItemIcon>
                    <ListItemText 
                      primary={
                        <Typography variant="subtitle1" fontWeight={600} color="white">
                          {stop.common_name}
                        </Typography>
                      }
                      secondary={
                        <>
                          <Typography variant="caption" color="rgba(255,255,255,0.5)">
                            {stop.indicator} {stop.locality} • {formatDistance(stop.distance_km)}
                          </Typography>
                          {stopBuses.length > 0 && (
                            <Box sx={{ mt: 0.5, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                              {stopBuses.slice(0, 3).map(b => (
                                <Chip 
                                  key={b.bus_id}
                                  label={`${b.route} ${formatTime(Math.max(1, b.distance_to_user * 3))}`}
                                  size="small"
                                  sx={{ 
                                    height: 20, fontSize: '0.7rem',
                                    bgcolor: getRouteColor(b.route),
                                    color: 'white'
                                  }}
                                />
                              ))}
                              {stopBuses.length > 3 && (
                                <Typography variant="caption" color="#10b981">
                                  +{stopBuses.length - 3} more
                                </Typography>
                              )}
                            </Box>
                          )}
                        </>
                      }
                    />
                    {stopBuses.length > 0 && (
                      <Badge badgeContent={stopBuses.length} color="success" />
                    )}
                  </Paper>
                </Slide>
              );
            })}
          </List>
        )}
      </Box>
    </Box>
  );
  
  // Map View - Optimized to prevent re-renders
  const MapView = () => {
    const mapCenter = useMemo(() => userLocation || [51.4545, -2.5879], [userLocation]);
    
    return (
      <Box sx={{ height: '100%', position: 'relative' }}>
        <MapContainer 
          center={mapCenter}
          zoom={15}
          style={{ height: "100%", width: "100%" }}
          zoomControl={false}
          whenCreated={(map) => { mapRef.current = map; }}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <MapController center={mapCenter} />
          
          {/* User location */}
          {userLocation && (
            <Marker position={userLocation} icon={userIcon}>
              <Popup><Typography variant="subtitle2">Your Location</Typography></Popup>
            </Marker>
          )}
          
          {/* Nearby stops */}
          {nearbyStops.map(stop => (
            <Marker
              key={stop.atco_code}
              position={[stop.latitude, stop.longitude]}
              icon={stopIcon}
              eventHandlers={{ click: () => setSelectedStop(stop) }}
            >
              <Popup>
                <Typography variant="subtitle2" fontWeight={700}>{stop.common_name}</Typography>
                <Button size="small" variant="contained" fullWidth sx={{ mt: 1 }} onClick={() => setSelectedStop(stop)}>
                  View Buses
                </Button>
              </Popup>
            </Marker>
          ))}
          
          {/* Bus trails */}
          {relevantBuses.map(bus => bus.trail?.length > 1 && (
            <Polyline
              key={`trail-${bus.bus_id}`}
              positions={bus.trail.map(p => [p.lat, p.lon])}
              pathOptions={{ color: getRouteColor(bus.route), weight: 2, opacity: 0.4, dashArray: '5,5' }}
            />
          ))}
          
          {/* Relevant buses only */}
          {relevantBuses.map(bus => (
            <BusMarker
              key={bus.bus_id}
              bus={bus}
              isSelected={selectedBus?.bus_id === bus.bus_id}
              onClick={setSelectedBus}
            />
          ))}
        </MapContainer>
        
        {/* Controls */}
        <Box sx={{ position: 'absolute', bottom: 80, right: 16, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <IconButton 
            onClick={getUserLocation}
            sx={{ bgcolor: '#1e3a8a', color: 'white', '&:hover': { bgcolor: '#1e40af' }, boxShadow: 3 }}
          >
            <MyLocationIcon />
          </IconButton>
        </Box>
        
        {/* Info panel */}
        <Box sx={{ 
          position: 'absolute', top: 16, left: 16, right: 16,
          display: 'flex', justifyContent: 'space-between'
        }}>
          <Paper sx={{ bgcolor: 'rgba(10,14,39,0.9)', backdropFilter: 'blur(10px)', px: 2, py: 1, borderRadius: 2 }}>
            <Typography variant="body2" color="white">
              {relevantBuses.length} buses near you
            </Typography>
          </Paper>
          
          <Paper sx={{ bgcolor: 'rgba(10,14,39,0.9)', backdropFilter: 'blur(10px)', px: 2, py: 1, borderRadius: 2 }}>
            <Typography variant="caption" color="rgba(255,255,255,0.6)">
              {lastUpdate?.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'})}
            </Typography>
          </Paper>
        </Box>
      </Box>
    );
  };
  
  // Stop detail dialog
  const StopDetailDialog = () => {
    if (!selectedStop) return null;
    
    const stopBuses = relevantBuses.filter(b => b.next_stop_ref === selectedStop.atco_code);
    
    return (
      <Dialog open={!!selectedStop} onClose={() => setSelectedStop(null)} fullScreen={isMobile}>
        <DialogTitle sx={{ bgcolor: '#1e3a8a', color: 'white', display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton color="inherit" onClick={() => setSelectedStop(null)}>
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" fontWeight={700}>{selectedStop.common_name}</Typography>
            <Typography variant="caption" sx={{ opacity: 0.8 }}>
              {selectedStop.indicator} {selectedStop.locality}
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent sx={{ bgcolor: '#0a0e27', p: 2 }}>
          {stopBuses.length === 0 ? (
            <Typography color="rgba(255,255,255,0.6)" sx={{ py: 4, textAlign: 'center' }}>
              No buses currently approaching this stop
            </Typography>
          ) : (
            <List>
              {stopBuses.map((bus, idx) => (
                <Slide key={bus.bus_id} direction="up" in={true} style={{ transitionDelay: idx * 50 }}>
                  <Paper sx={{ mb: 1, bgcolor: 'rgba(30,41,59,0.8)', border: '1px solid rgba(99,102,241,0.2)' }}>
                    <ListItem>
                      <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 2 }}>
                        <Box sx={{ 
                          minWidth: 56, height: 56, 
                          bgcolor: getRouteColor(bus.route), 
                          borderRadius: 2,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: '1.25rem', fontWeight: 800, color: 'white'
                        }}>
                          {bus.route}
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <Typography variant="subtitle1" fontWeight={700} color="white">
                            {bus.destination}
                          </Typography>
                          <Typography variant="caption" color="rgba(255,255,255,0.6)">
                            {bus.operator} • {Math.round(bus.speed || 0)} km/h
                          </Typography>
                          <Chip 
                            size="small" 
                            label={bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
                            sx={{ 
                              mt: 0.5, height: 20,
                              bgcolor: bus.delay_minutes > 2 ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)',
                              color: bus.delay_minutes > 2 ? '#ef4444' : '#22c55e',
                              fontSize: '0.7rem'
                            }} 
                          />
                        </Box>
                        <Box sx={{ textAlign: 'right' }}>
                          <Typography variant="h5" fontWeight={800} color="#22c55e">
                            {formatTime(Math.max(1, bus.distance_to_user * 3))}
                          </Typography>
                        </Box>
                      </Box>
                    </ListItem>
                  </Paper>
                </Slide>
              ))}
            </List>
          )}
        </DialogContent>
      </Dialog>
    );
  };
  
  // Journey search dialog
  const JourneySearchDialog = () => (
    <Dialog open={showJourneySearch} onClose={() => setShowJourneySearch(false)} fullWidth maxWidth="sm">
      <DialogTitle sx={{ bgcolor: '#1e3a8a', color: 'white' }}>
        Plan Your Journey
        <IconButton color="inherit" onClick={() => setShowJourneySearch(false)} sx={{ position: 'absolute', right: 8, top: 8 }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ bgcolor: '#0a0e27', pt: 3 }}>
        <Typography variant="body2" color="rgba(255,255,255,0.6)" sx={{ mb: 2 }}>
          Search for your destination to find buses from your nearest stops
        </Typography>
        
        <Autocomplete
          options={destOptions}
          getOptionLabel={(opt) => `${opt.common_name}${opt.locality ? ', ' + opt.locality : ''}`}
          inputValue={destSearch}
          onInputChange={(e, v) => setDestSearch(v)}
          onChange={(e, v) => setSelectedDest(v)}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Where do you want to go?"
              fullWidth
              sx={{
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'rgba(255,255,255,0.1)',
                  color: 'white',
                  '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' }
                },
                '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.6)' }
              }}
            />
          )}
        />
        
        {selectedDest && (
          <Box sx={{ mt: 3 }}>
            <Typography variant="subtitle2" color="white" fontWeight={700}>
              Destination: {selectedDest.common_name}
            </Typography>
            <Typography variant="caption" color="rgba(255,255,255,0.6)">
              {selectedDest.locality}
            </Typography>
            <Button
              variant="contained"
              fullWidth
              sx={{ mt: 2, bgcolor: '#6366f1' }}
              onClick={() => {
                setShowJourneySearch(false);
                // Could add journey planning logic here
                setActiveTab(0);
              }}
            >
              Find Buses
            </Button>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
  
  return (
    <Box sx={{ width: '100%', height: '100vh', overflow: 'hidden', bgcolor: '#0a0e27' }}>
      <style>{`
        .bus-marker { background: transparent !important; border: none !important; }
        .user-marker { background: transparent !important; border: none !important; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
      `}</style>
      
      <Box sx={{ height: 'calc(100vh - 70px)', overflow: 'hidden' }}>
        {activeTab === 0 && <NearbyView />}
        {activeTab === 2 && <MapView />}
      </Box>
      
      <Paper sx={{ position: 'fixed', bottom: 0, left: 0, right: 0, bgcolor: '#0f172a', borderTop: '1px solid rgba(99,102,241,0.2)', zIndex: 1000 }} elevation={0}>
        <BottomNavigation
          value={activeTab}
          onChange={(e, v) => setActiveTab(v)}
          sx={{ 
            bgcolor: 'transparent',
            '& .MuiBottomNavigationAction-root': { color: 'rgba(255,255,255,0.5)', '&.Mui-selected': { color: '#6366f1' } }
          }}
        >
          <BottomNavigationAction label="My Buses" icon={<DirectionsBusIcon />} />
          <BottomNavigationAction label="Search" icon={<SearchIcon />} />
          <BottomNavigationAction label="Map" icon={<MapIcon />} />
        </BottomNavigation>
      </Paper>
      
      <StopDetailDialog />
      <JourneySearchDialog />
    </Box>
  );
}

export default App;
