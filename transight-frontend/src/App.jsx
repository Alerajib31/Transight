import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, AppBar, Toolbar, IconButton, Typography, TextField,
  Paper, useTheme, useMediaQuery, InputAdornment, Chip,
  List, ListItem, ListItemButton, ListItemText, ListItemIcon,
  BottomNavigation, BottomNavigationAction, Button, Slide, Badge,
  Dialog, DialogTitle, DialogContent, Autocomplete
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import MapIcon from '@mui/icons-material/Map';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import CloseIcon from '@mui/icons-material/Close';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
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

// Create bus icon
const createBusIcon = (bearing, route, color) => {
  return L.divIcon({
    className: 'bus-marker',
    html: `
      <div style="
        width: 36px; height: 36px; 
        background: ${color}; border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 3px 10px rgba(0,0,0,0.4);
        display: flex; align-items: center; justify-content: center;
        color: white; font-weight: bold; font-size: 11px;
        transform: rotate(${bearing}deg);
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
    background: #3b82f6; border: 3px solid white;
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

const formatTime = (minutes) => minutes <= 1 ? 'Due' : `${Math.round(minutes)} min`;
const formatDistance = (km) => km < 1 ? `${Math.round(km * 1000)}m` : `${km.toFixed(1)}km`;

// Map component - NO forced recentering
function MapView({ userLocation, nearbyStops, relevantBuses, onStopClick }) {
  const mapRef = useRef(null);
  
  // Only set initial center, don't force recenter
  useEffect(() => {
    if (mapRef.current && userLocation) {
      mapRef.current.setView(userLocation, 15);
    }
  }, []); // Empty deps - only on mount

  return (
    <Box sx={{ height: '100%', position: 'relative' }}>
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
          <Marker position={userLocation} icon={userIcon}>
            <Popup><Typography variant="subtitle2">Your Location</Typography></Popup>
          </Marker>
        )}
        
        {/* Stops */}
        {nearbyStops.map(stop => (
          <Marker
            key={stop.atco_code}
            position={[stop.latitude, stop.longitude]}
            icon={stopIcon}
            eventHandlers={{ click: () => onStopClick(stop) }}
          >
            <Popup>
              <Typography variant="subtitle2" fontWeight={700}>{stop.common_name}</Typography>
              <Button size="small" variant="contained" fullWidth sx={{ mt: 1 }} onClick={() => onStopClick(stop)}>
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
        
        {/* Buses - using stable positions */}
        {relevantBuses.map(bus => (
          <Marker
            key={bus.bus_id}
            position={[bus.latitude, bus.longitude]}
            icon={createBusIcon(bus.bearing || 0, bus.route, getRouteColor(bus.route))}
          >
            <Popup>
              <Box sx={{ minWidth: 180 }}>
                <Typography variant="subtitle2" fontWeight={700}>{bus.route} → {bus.destination}</Typography>
                <Typography variant="caption" display="block">{bus.operator}</Typography>
                <Typography variant="caption" display="block">Speed: {Math.round(bus.speed || 0)} km/h</Typography>
                <Typography variant="caption" color={bus.delay_minutes > 0 ? 'error.main' : 'success.main'}>
                  {bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
                </Typography>
              </Box>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      
      {/* Controls */}
      <Box sx={{ position: 'absolute', bottom: 80, right: 16, display: 'flex', flexDirection: 'column', gap: 1 }}>
        <IconButton sx={{ bgcolor: '#1e3a8a', color: 'white', '&:hover': { bgcolor: '#1e40af' }, boxShadow: 3 }}>
          <MyLocationIcon />
        </IconButton>
      </Box>
      
      {/* Info */}
      <Paper sx={{ position: 'absolute', top: 16, left: 16, bgcolor: 'rgba(10,14,39,0.9)', px: 2, py: 1 }}>
        <Typography variant="body2" color="white">{relevantBuses.length} buses nearby</Typography>
      </Paper>
    </Box>
  );
}

// Main App
function App() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  // State
  const [activeTab, setActiveTab] = useState(0);
  const [userLocation, setUserLocation] = useState(null);
  const [nearbyStops, setNearbyStops] = useState([]);
  const [relevantBuses, setRelevantBuses] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Journey search state - SEPARATE to prevent re-render issues
  const [journeyDialogOpen, setJourneyDialogOpen] = useState(false);
  const [destinationQuery, setDestinationQuery] = useState('');
  const [destinationResults, setDestinationResults] = useState([]);
  const [selectedDestination, setSelectedDestination] = useState(null);
  
  // Search tab state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  
  const API_BASE_URL = "http://127.0.0.1:8000";
  
  // Get location once on mount
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserLocation([pos.coords.latitude, pos.coords.longitude]);
        },
        (err) => {
          console.log("Geolocation failed, using Bristol");
          setUserLocation([51.4545, -2.5879]);
        }
      );
    } else {
      setUserLocation([51.4545, -2.5879]);
    }
  }, []);
  
  // Fetch data when location available - with larger radius
  const fetchData = useCallback(async () => {
    if (!userLocation) return;
    
    setLoading(true);
    try {
      // Use larger radius (5km) to find stops
      const res = await axios.get(`${API_BASE_URL}/my-buses`, {
        params: { lat: userLocation[0], lon: userLocation[1], radius: 5.0 }
      });
      
      setNearbyStops(res.data.stops || []);
      setRelevantBuses(res.data.buses || []);
      setLastUpdate(new Date());
    } catch (e) {
      console.error("Error:", e);
    } finally {
      setLoading(false);
    }
  }, [userLocation]);
  
  // Initial fetch and interval
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);
  
  // Destination search - debounced
  useEffect(() => {
    if (!destinationQuery || destinationQuery.length < 2) {
      setDestinationResults([]);
      return;
    }
    
    const timer = setTimeout(async () => {
      try {
        const params = { q: destinationQuery };
        if (userLocation) {
          params.lat = userLocation[0];
          params.lon = userLocation[1];
        }
        const res = await axios.get(`${API_BASE_URL}/search-stops`, { params });
        setDestinationResults(res.data.results || []);
      } catch (e) {
        console.error("Search error:", e);
      }
    }, 400);
    
    return () => clearTimeout(timer);
  }, [destinationQuery, userLocation]);
  
  // Search tab search
  const handleSearch = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    setSearchLoading(true);
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
    } finally {
      setSearchLoading(false);
    }
  }, [userLocation]);
  
  // Nearby View
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
            onClick={() => setJourneyDialogOpen(true)}
            sx={{ bgcolor: '#10b981', mr: 1 }}
          >
            Plan Journey
          </Button>
          <IconButton color="inherit" onClick={fetchData}>
            <MyLocationIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
      
      <Box sx={{ p: 2 }}>
        {loading && nearbyStops.length === 0 ? (
          <Box display="flex" justifyContent="center" py={8}>
            <CircularProgress sx={{ color: '#6366f1' }} />
          </Box>
        ) : nearbyStops.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)' }}>
            <LocationOnIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1, color: 'white' }} />
            <Typography color="rgba(255,255,255,0.6)">No stops found nearby</Typography>
            <Typography variant="caption" color="rgba(255,255,255,0.4)" display="block" sx={{ mt: 1 }}>
              Try searching for your destination
            </Typography>
            <Button 
              variant="outlined" 
              sx={{ mt: 2, color: '#6366f1', borderColor: '#6366f1' }}
              onClick={() => setJourneyDialogOpen(true)}
            >
              Plan a Journey
            </Button>
          </Paper>
        ) : (
          <>
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
                    />
                  ))}
                </Box>
              </>
            )}
            
            {/* Stops */}
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1.5, display: 'block' }}>
              NEARBY STOPS ({nearbyStops.length})
            </Typography>
            
            <List sx={{ gap: 1, display: 'flex', flexDirection: 'column' }}>
              {nearbyStops.map((stop, idx) => {
                const stopBuses = relevantBuses.filter(b => 
                  b.next_stop_ref === stop.atco_code || 
                  (b.nearest_stop === stop.common_name && b.nearest_stop_dist < 0.5)
                );
                
                return (
                  <Slide key={stop.atco_code} direction="up" in={true} style={{ transitionDelay: idx * 30 }}>
                    <Paper 
                      onClick={() => setSelectedStop(stop)}
                      sx={{ 
                        p: 2,
                        cursor: 'pointer',
                        bgcolor: stopBuses.length > 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(30, 41, 59, 0.8)', 
                        border: stopBuses.length > 0 ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(99, 102, 241, 0.2)',
                        '&:hover': { bgcolor: stopBuses.length > 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(99, 102, 241, 0.15)' }
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box sx={{ 
                          width: 40, height: 40, 
                          bgcolor: stopBuses.length > 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(99, 102, 241, 0.2)', 
                          borderRadius: '50%',
                          display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}>
                          <LocationOnIcon sx={{ color: stopBuses.length > 0 ? '#10b981' : '#6366f1' }} />
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <Typography variant="subtitle1" fontWeight={600} color="white">
                            {stop.common_name}
                          </Typography>
                          <Typography variant="caption" color="rgba(255,255,255,0.5)">
                            {stop.indicator} {stop.locality} • {formatDistance(stop.distance_km)}
                          </Typography>
                          {stopBuses.length > 0 && (
                            <Box sx={{ mt: 0.5, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                              {stopBuses.slice(0, 3).map(b => (
                                <Chip 
                                  key={b.bus_id}
                                  label={`${b.route}`}
                                  size="small"
                                  sx={{ height: 20, fontSize: '0.7rem', bgcolor: getRouteColor(b.route), color: 'white' }}
                                />
                              ))}
                            </Box>
                          )}
                        </Box>
                        {stopBuses.length > 0 && (
                          <Badge badgeContent={stopBuses.length} color="success" />
                        )}
                      </Box>
                    </Paper>
                  </Slide>
                );
              })}
            </List>
          </>
        )}
      </Box>
    </Box>
  );
  
  // Search Tab View
  const SearchView = () => (
    <Box sx={{ height: '100%', overflow: 'auto', bgcolor: '#0a0e27' }}>
      <AppBar position="sticky" sx={{ bgcolor: '#1e3a8a' }}>
        <Toolbar>
          <TextField
            fullWidth
            placeholder="Search for a stop..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              handleSearch(e.target.value);
            }}
            autoFocus
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: 'rgba(255,255,255,0.5)' }} />
                </InputAdornment>
              ),
              sx: {
                bgcolor: 'rgba(255,255,255,0.1)',
                borderRadius: 2,
                color: 'white',
                '& input::placeholder': { color: 'rgba(255,255,255,0.5)' },
                '& fieldset': { border: 'none' }
              }
            }}
          />
        </Toolbar>
      </AppBar>
      
      <Box sx={{ p: 2 }}>
        {searchLoading ? (
          <Box display="flex" justifyContent="center" py={4}>
            <CircularProgress sx={{ color: '#6366f1' }} />
          </Box>
        ) : searchQuery.length < 2 ? (
          <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
            <SearchIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1 }} />
            <Typography>Type at least 2 characters to search</Typography>
          </Paper>
        ) : searchResults.length === 0 ? (
          <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
            <Typography>No stops found</Typography>
          </Paper>
        ) : (
          <List sx={{ gap: 1, display: 'flex', flexDirection: 'column' }}>
            {searchResults.map((stop) => (
              <Paper 
                key={stop.atco_code}
                onClick={() => {
                  setSelectedStop(stop);
                  setActiveTab(0);
                }}
                sx={{ 
                  p: 2,
                  cursor: 'pointer',
                  bgcolor: 'rgba(30, 41, 59, 0.8)', 
                  border: '1px solid rgba(99, 102, 241, 0.2)',
                  '&:hover': { bgcolor: 'rgba(99, 102, 241, 0.15)' }
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <LocationOnIcon sx={{ color: '#6366f1' }} />
                  <Box>
                    <Typography fontWeight={600} color="white">{stop.common_name}</Typography>
                    <Typography variant="caption" color="rgba(255,255,255,0.5)">
                      {stop.locality} {stop.distance_km && `• ${formatDistance(stop.distance_km)}`}
                    </Typography>
                  </Box>
                </Box>
              </Paper>
            ))}
          </List>
        )}
      </Box>
    </Box>
  );
  
  // Stop Detail Dialog
  const StopDetailDialog = () => {
    if (!selectedStop) return null;
    
    const stopBuses = relevantBuses.filter(b => 
      b.next_stop_ref === selectedStop.atco_code || 
      (b.nearest_stop === selectedStop.common_name && b.nearest_stop_dist < 0.5)
    );
    
    return (
      <Dialog open={!!selectedStop} onClose={() => setSelectedStop(null)} fullScreen={isMobile}>
        <DialogTitle sx={{ bgcolor: '#1e3a8a', color: 'white', display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton color="inherit" onClick={() => setSelectedStop(null)}>
            <ArrowBackIcon />
          </IconButton>
          <Box>
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
            <List sx={{ gap: 1, display: 'flex', flexDirection: 'column' }}>
              {stopBuses.map((bus, idx) => (
                <Slide key={bus.bus_id} direction="up" in={true} style={{ transitionDelay: idx * 50 }}>
                  <Paper sx={{ p: 2, bgcolor: 'rgba(30,41,59,0.8)', border: '1px solid rgba(99,102,241,0.2)' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
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
                          {bus.operator}
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
                  </Paper>
                </Slide>
              ))}
            </List>
          )}
        </DialogContent>
      </Dialog>
    );
  };
  
  // Journey Dialog - FIXED to not reset input
  const JourneyDialog = () => (
    <Dialog open={journeyDialogOpen} onClose={() => setJourneyDialogOpen(false)} fullWidth maxWidth="sm">
      <DialogTitle sx={{ bgcolor: '#1e3a8a', color: 'white' }}>
        Plan Your Journey
        <IconButton color="inherit" onClick={() => setJourneyDialogOpen(false)} sx={{ position: 'absolute', right: 8, top: 8 }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ bgcolor: '#0a0e27', pt: 3 }}>
        <Typography variant="body2" color="rgba(255,255,255,0.6)" sx={{ mb: 2 }}>
          Enter your destination to find buses from your nearest stops
        </Typography>
        
        <TextField
          fullWidth
          label="Where do you want to go?"
          value={destinationQuery}
          onChange={(e) => setDestinationQuery(e.target.value)}
          autoFocus
          sx={{
            '& .MuiOutlinedInput-root': {
              bgcolor: 'rgba(255,255,255,0.1)',
              color: 'white',
              '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' }
            },
            '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.6)' }
          }}
        />
        
        {destinationResults.length > 0 && (
          <List sx={{ mt: 2, maxHeight: 300, overflow: 'auto' }}>
            {destinationResults.map((stop) => (
              <Paper
                key={stop.atco_code}
                onClick={() => {
                  setSelectedDestination(stop);
                  setDestinationQuery(stop.common_name);
                }}
                sx={{
                  mb: 1,
                  p: 2,
                  cursor: 'pointer',
                  bgcolor: selectedDestination?.atco_code === stop.atco_code ? 'rgba(99,102,241,0.3)' : 'rgba(30,41,59,0.8)',
                  border: '1px solid rgba(99,102,241,0.2)',
                  '&:hover': { bgcolor: 'rgba(99,102,241,0.2)' }
                }}
              >
                <Typography fontWeight={600} color="white">{stop.common_name}</Typography>
                <Typography variant="caption" color="rgba(255,255,255,0.5)">
                  {stop.locality} {stop.distance_km && `• ${formatDistance(stop.distance_km)}`}
                </Typography>
              </Paper>
            ))}
          </List>
        )}
        
        {selectedDestination && (
          <Button
            variant="contained"
            fullWidth
            sx={{ mt: 2, bgcolor: '#6366f1' }}
            onClick={() => {
              setJourneyDialogOpen(false);
              setActiveTab(0);
              // Could filter buses here based on destination
            }}
          >
            Show Buses to {selectedDestination.common_name}
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
  
  return (
    <Box sx={{ width: '100%', height: '100vh', overflow: 'hidden', bgcolor: '#0a0e27' }}>
      <Box sx={{ height: 'calc(100vh - 70px)', overflow: 'hidden' }}>
        {activeTab === 0 && <NearbyView />}
        {activeTab === 1 && <SearchView />}
        {activeTab === 2 && (
          <MapView 
            userLocation={userLocation}
            nearbyStops={nearbyStops}
            relevantBuses={relevantBuses}
            onStopClick={setSelectedStop}
          />
        )}
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
      <JourneyDialog />
    </Box>
  );
}

export default App;
