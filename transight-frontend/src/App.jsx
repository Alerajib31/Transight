import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, AppBar, Toolbar, IconButton, Typography, TextField,
  Paper, useTheme, useMediaQuery, InputAdornment, Chip,
  List, ListItem, ListItemButton, ListItemText, ListItemIcon,
  BottomNavigation, BottomNavigationAction, Button, Slide, Badge
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import RefreshIcon from '@mui/icons-material/Refresh';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import NavigationIcon from '@mui/icons-material/Navigation';
import MapIcon from '@mui/icons-material/Map';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline, CircleMarker } from 'react-leaflet';
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

// Rotated bus icon based on bearing
const createBusIcon = (bearing, route) => {
  const color = getRouteColor(route);
  return L.divIcon({
    className: 'custom-bus-icon',
    html: `
      <div style="
        width: 40px; 
        height: 40px; 
        background: ${color}; 
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 11px;
        transform: rotate(${bearing}deg);
        transition: transform 0.5s ease;
      ">
        <span style="transform: rotate(${-bearing}deg)">${route}</span>
      </div>
    `,
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  });
};

const userIcon = new L.Icon({
  iconUrl: 'https://cdn-icons-png.flaticon.com/512/447/447031.png',
  iconSize: [40, 40],
  iconAnchor: [20, 40],
});

const stopIcon = new L.Icon({
  iconUrl: 'https://cdn-icons-png.flaticon.com/512/684/684908.png',
  iconSize: [32, 32],
  iconAnchor: [16, 32],
});

// Route colors
const ROUTE_COLORS = [
  '#6366f1', '#ec4899', '#8b5cf6', '#14b8a6', '#f59e0b',
  '#ef4444', '#3b82f6', '#10b981', '#f97316', '#84cc16'
];
const routeColorMap = {};
let colorIndex = 0;

function getRouteColor(route) {
  if (!routeColorMap[route]) {
    routeColorMap[route] = ROUTE_COLORS[colorIndex % ROUTE_COLORS.length];
    colorIndex++;
  }
  return routeColorMap[route];
}

function RecenterMap({ center }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, 15);
  }, [center, map]);
  return null;
}

// Smooth animated marker component
function AnimatedBusMarker({ bus, onClick }) {
  const markerRef = useRef(null);
  const positionRef = useRef([bus.latitude, bus.longitude]);
  const targetRef = useRef([bus.latitude, bus.longitude]);
  const animationRef = useRef(null);
  
  useEffect(() => {
    targetRef.current = [bus.latitude, bus.longitude];
  }, [bus.latitude, bus.longitude]);
  
  useEffect(() => {
    const animate = () => {
      const current = positionRef.current;
      const target = targetRef.current;
      
      // Smooth interpolation
      const newLat = current[0] + (target[0] - current[0]) * 0.1;
      const newLon = current[1] + (target[1] - current[1]) * 0.1;
      
      positionRef.current = [newLat, newLon];
      
      if (markerRef.current) {
        markerRef.current.setLatLng([newLat, newLon]);
      }
      
      animationRef.current = requestAnimationFrame(animate);
    };
    
    animationRef.current = requestAnimationFrame(animate);
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);
  
  const icon = createBusIcon(bus.bearing || 0, bus.route);
  
  return (
    <Marker
      ref={markerRef}
      position={positionRef.current}
      icon={icon}
      eventHandlers={{ click: () => onClick(bus) }}
    >
      <Popup>
        <Box sx={{ minWidth: 180 }}>
          <Typography variant="subtitle2" fontWeight={700}>
            Bus {bus.route} → {bus.destination}
          </Typography>
          <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
            Operator: {bus.operator}
          </Typography>
          <Typography variant="caption" display="block">
            Speed: {Math.round(bus.speed || 0)} km/h
          </Typography>
          <Typography variant="caption" display="block" color={bus.delay_minutes > 0 ? 'error.main' : 'success.main'}>
            {bus.delay_minutes > 0 ? `${bus.delay_minutes} min late` : 'On time'}
          </Typography>
          {bus.next_stop && bus.next_stop !== "Unknown" && (
            <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'primary.main' }}>
              Next: {bus.next_stop}
            </Typography>
          )}
        </Box>
      </Popup>
    </Marker>
  );
}

// Format arrival time
const formatArrival = (minutes) => {
  if (minutes <= 1) return 'Due';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
};

// Format distance
const formatDistance = (km) => {
  if (km < 1) return `${Math.round(km * 1000)}m`;
  return `${km.toFixed(1)}km`;
};

function App() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // State
  const [activeTab, setActiveTab] = useState(0);
  const [userLocation, setUserLocation] = useState(null);
  const [locationError, setLocationError] = useState(false);
  
  const [nearbyStops, setNearbyStops] = useState([]);
  const [liveBuses, setLiveBuses] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopDetail, setStopDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  const API_BASE_URL = "http://127.0.0.1:8000";
  
  // Store previous buses for smooth transition
  const prevBusesRef = useRef({});

  // Get user location
  const getUserLocation = useCallback(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          setUserLocation([latitude, longitude]);
          setLocationError(false);
        },
        (error) => {
          console.error("Geolocation failed:", error);
          setLocationError(true);
          // Fallback to Bristol
          setUserLocation([51.4545, -2.5879]);
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    }
  }, []);

  // Fetch nearby stops
  const fetchNearbyStops = useCallback(async (lat, lon) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/nearby-stops`, {
        params: { latitude: lat, longitude: lon, radius: 1.5 }
      });
      setNearbyStops(response.data.nearby_stops || []);
    } catch (error) {
      console.error("Error fetching stops:", error);
    }
  }, []);

  // Fetch live buses - updates without page refresh
  const fetchLiveBuses = useCallback(async (lat, lon) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/live-buses`, {
        params: { lat, lon, radius: 5 }
      });
      
      const newBuses = response.data.buses || [];
      
      // Merge with previous positions for smooth animation
      const mergedBuses = newBuses.map(newBus => {
        const prevBus = prevBusesRef.current[newBus.bus_id];
        if (prevBus) {
          // Use previous position as starting point for animation
          return {
            ...newBus,
            _prevLat: prevBus.latitude,
            _prevLon: prevBus.longitude,
            _lastUpdate: Date.now()
          };
        }
        return newBus;
      });
      
      // Store current for next update
      const busMap = {};
      newBuses.forEach(b => busMap[b.bus_id] = b);
      prevBusesRef.current = busMap;
      
      setLiveBuses(mergedBuses);
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Error fetching buses:", error);
    }
  }, []);

  // Search stops
  const searchStops = useCallback(async (query) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const params = { q: query };
      if (userLocation) {
        params.lat = userLocation[0];
        params.lon = userLocation[1];
      }
      const response = await axios.get(`${API_BASE_URL}/search`, { params });
      setSearchResults(response.data.results || []);
    } catch (error) {
      console.error("Error searching:", error);
    }
  }, [userLocation]);

  // Fetch stop detail
  const fetchStopDetail = useCallback(async (stopId) => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/stops/${stopId}`);
      setStopDetail(response.data);
    } catch (error) {
      console.error("Error fetching stop:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle stop selection
  const handleStopSelect = useCallback((stop) => {
    setSelectedStop(stop);
    fetchStopDetail(stop.stop_id);
  }, [fetchStopDetail]);

  // Initial load
  useEffect(() => {
    getUserLocation();
  }, [getUserLocation]);

  // Fetch data when location available
  useEffect(() => {
    if (!userLocation) return;
    
    fetchNearbyStops(userLocation[0], userLocation[1]);
    fetchLiveBuses(userLocation[0], userLocation[1]);
    
    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      fetchLiveBuses(userLocation[0], userLocation[1]);
      if (selectedStop) {
        fetchStopDetail(selectedStop.stop_id);
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [userLocation, fetchNearbyStops, fetchLiveBuses, selectedStop, fetchStopDetail]);

  // Debounced search
  useEffect(() => {
    const timeout = setTimeout(() => searchStops(searchQuery), 300);
    return () => clearTimeout(timeout);
  }, [searchQuery, searchStops]);

  // Get unique routes
  const getNearbyRoutes = useCallback(() => {
    const routes = {};
    liveBuses.forEach(bus => {
      const route = bus.route;
      if (!routes[route]) {
        routes[route] = {
          route,
          destination: bus.destination,
          buses: 0,
          color: getRouteColor(route)
        };
      }
      routes[route].buses++;
    });
    return Object.values(routes).sort((a, b) => a.route.localeCompare(b.route));
  }, [liveBuses]);

  // Stop Detail View
  const StopDetailView = () => {
    if (!selectedStop) return null;
    
    const busesAtStop = liveBuses.filter(b => b.next_stop_ref === selectedStop.stop_id);
    
    return (
      <Box sx={{ height: '100%', overflow: 'auto', bgcolor: '#0a0e27' }}>
        <AppBar position="sticky" sx={{ bgcolor: '#1e3a8a' }}>
          <Toolbar>
            <IconButton edge="start" color="inherit" onClick={() => setSelectedStop(null)} sx={{ mr: 1 }}>
              <ArrowBackIcon />
            </IconButton>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="h6" sx={{ fontSize: '1.1rem', fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {selectedStop.name}
              </Typography>
              <Typography variant="caption" sx={{ opacity: 0.8 }}>
                {selectedStop.indicator} {selectedStop.locality}
              </Typography>
            </Box>
          </Toolbar>
        </AppBar>

        <Box sx={{ p: 2 }}>
          {loading ? (
            <Box display="flex" justifyContent="center" py={4}>
              <CircularProgress sx={{ color: '#6366f1' }} />
            </Box>
          ) : busesAtStop.length === 0 ? (
            <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
              <DirectionsBusIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1 }} />
              <Typography>No buses currently approaching</Typography>
            </Paper>
          ) : (
            <>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 2, display: 'block' }}>
                LIVE DEPARTURES ({busesAtStop.length} buses)
              </Typography>
              <List sx={{ gap: 1.5, display: 'flex', flexDirection: 'column' }}>
                {busesAtStop.map((bus, idx) => (
                  <Slide key={bus.bus_id} direction="up" in={true} style={{ transitionDelay: idx * 50 }}>
                    <Paper sx={{ bgcolor: 'rgba(30, 41, 59, 0.8)', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
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
                          <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Typography variant="subtitle1" fontWeight={700} color="white" noWrap>
                              {bus.destination}
                            </Typography>
                            <Typography variant="caption" color="rgba(255,255,255,0.6)" display="block">
                              {bus.operator}
                            </Typography>
                            <Chip 
                              size="small" 
                              label={bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
                              sx={{ 
                                mt: 0.5,
                                bgcolor: bus.delay_minutes > 2 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)',
                                color: bus.delay_minutes > 2 ? '#ef4444' : '#22c55e',
                                fontSize: '0.7rem', height: 20
                              }} 
                            />
                          </Box>
                          <Box sx={{ textAlign: 'right' }}>
                            <Typography variant="h5" fontWeight={800} color="#22c55e">
                              {formatArrival(Math.max(1, 5 - Math.floor((bus.distance_km || 0) * 2)))}
                            </Typography>
                          </Box>
                        </Box>
                      </ListItem>
                    </Paper>
                  </Slide>
                ))}
              </List>
            </>
          )}
        </Box>
      </Box>
    );
  };

  // Nearby View
  const NearbyView = () => (
    <Box sx={{ height: '100%', overflow: 'auto', bgcolor: '#0a0e27' }}>
      <AppBar position="sticky" sx={{ bgcolor: '#1e3a8a' }}>
        <Toolbar>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" fontWeight={700}>Nearby Stops</Typography>
            {lastUpdate && (
              <Typography variant="caption" sx={{ opacity: 0.8 }}>
                Updated: {lastUpdate.toLocaleTimeString()}
              </Typography>
            )}
          </Box>
          <IconButton color="inherit" onClick={getUserLocation}>
            <MyLocationIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Box sx={{ p: 2 }}>
        {/* Active Routes */}
        {getNearbyRoutes().length > 0 && (
          <>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1.5, display: 'block' }}>
              ACTIVE ROUTES ({getNearbyRoutes().length})
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
              {getNearbyRoutes().map(r => (
                <Chip 
                  key={r.route}
                  label={`${r.route} (${r.buses})`}
                  size="small"
                  sx={{ 
                    bgcolor: `${r.color}30`,
                    color: r.color,
                    border: `1px solid ${r.color}50`,
                    fontWeight: 600
                  }}
                />
              ))}
            </Box>
          </>
        )}

        {/* Stops List */}
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1.5, display: 'block' }}>
          STOPS NEAR YOU ({nearbyStops.length})
        </Typography>
        
        {nearbyStops.length === 0 ? (
          <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
            <LocationOnIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1 }} />
            <Typography>No stops found</Typography>
          </Paper>
        ) : (
          <List sx={{ gap: 1, display: 'flex', flexDirection: 'column' }}>
            {nearbyStops.map((stop, idx) => (
              <Slide key={stop.stop_id} direction="up" in={true} style={{ transitionDelay: idx * 30 }}>
                <Paper 
                  component={ListItemButton}
                  onClick={() => handleStopSelect(stop)}
                  sx={{ 
                    bgcolor: 'rgba(30, 41, 59, 0.8)', 
                    border: '1px solid rgba(99, 102, 241, 0.2)',
                    '&:hover': { bgcolor: 'rgba(99, 102, 241, 0.15)' }
                  }}
                >
                  <ListItemIcon>
                    <Box sx={{ 
                      width: 40, height: 40, 
                      bgcolor: 'rgba(99, 102, 241, 0.2)', 
                      borderRadius: '50%',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      <LocationOnIcon sx={{ color: '#6366f1' }} />
                    </Box>
                  </ListItemIcon>
                  <ListItemText 
                    primary={
                      <Typography variant="subtitle1" fontWeight={600} color="white">
                        {stop.name}
                      </Typography>
                    }
                    secondary={
                      <>
                        <Typography variant="caption" color="rgba(255,255,255,0.5)">
                          {stop.indicator} {stop.locality} • {formatDistance(stop.distance_km)}
                        </Typography>
                        {stop.buses_approaching > 0 && (
                          <Typography variant="caption" sx={{ color: '#22c55e', display: 'block', mt: 0.5 }}>
                            {stop.buses_approaching} bus{stop.buses_approaching > 1 ? 'es' : ''} approaching
                          </Typography>
                        )}
                      </>
                    }
                  />
                  {stop.buses_approaching > 0 && (
                    <Badge badgeContent={stop.buses_approaching} color="success" />
                  )}
                </Paper>
              </Slide>
            ))}
          </List>
        )}
      </Box>
    </Box>
  );

  // Search View
  const SearchView = () => (
    <Box sx={{ height: '100%', overflow: 'auto', bgcolor: '#0a0e27' }}>
      <AppBar position="sticky" sx={{ bgcolor: '#1e3a8a' }}>
        <Toolbar>
          <TextField
            fullWidth
            placeholder="Search stops..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
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
        {searchQuery.trim() === '' ? (
          <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
            <SearchIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1 }} />
            <Typography>Type to search</Typography>
          </Paper>
        ) : searchResults.length === 0 ? (
          <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
            <Typography>No stops found</Typography>
          </Paper>
        ) : (
          <List sx={{ gap: 1, display: 'flex', flexDirection: 'column' }}>
            {searchResults.map((stop, idx) => (
              <Slide key={stop.stop_id} direction="up" in={true} style={{ transitionDelay: idx * 30 }}>
                <Paper 
                  component={ListItemButton}
                  onClick={() => {
                    handleStopSelect(stop);
                    setActiveTab(0);
                  }}
                  sx={{ 
                    bgcolor: 'rgba(30, 41, 59, 0.8)', 
                    border: '1px solid rgba(99, 102, 241, 0.2)'
                  }}
                >
                  <ListItemIcon>
                    <LocationOnIcon sx={{ color: '#6366f1' }} />
                  </ListItemIcon>
                  <ListItemText 
                    primary={<Typography fontWeight={600} color="white">{stop.name}</Typography>}
                    secondary={
                      <Typography variant="caption" color="rgba(255,255,255,0.5)">
                        {stop.locality} {stop.distance_km && `• ${formatDistance(stop.distance_km)}`}
                      </Typography>
                    }
                  />
                </Paper>
              </Slide>
            ))}
          </List>
        )}
      </Box>
    </Box>
  );

  // Map View with smooth bus animation
  const MapView = () => {
    const [selectedBus, setSelectedBus] = useState(null);
    
    return (
      <Box sx={{ height: '100%', position: 'relative' }}>
        {userLocation ? (
          <MapContainer 
            center={userLocation} 
            zoom={15} 
            style={{ height: "100%", width: "100%" }}
            zoomControl={false}
          >
            <TileLayer 
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" 
              attribution='&copy; OpenStreetMap' 
            />
            
            {/* User Location */}
            <Marker position={userLocation} icon={userIcon}>
              <Popup>
                <Typography variant="subtitle2" fontWeight={700}>Your Location</Typography>
              </Popup>
            </Marker>

            {/* Bus Stops */}
            {nearbyStops.map((stop) => (
              <Marker 
                key={stop.stop_id} 
                position={[stop.latitude, stop.longitude]} 
                icon={stopIcon}
                eventHandlers={{ click: () => handleStopSelect(stop) }}
              >
                <Popup>
                  <Box sx={{ minWidth: 150 }}>
                    <Typography variant="subtitle2" fontWeight={700}>{stop.name}</Typography>
                    <Button 
                      size="small" 
                      variant="contained"
                      fullWidth
                      sx={{ mt: 1, bgcolor: '#6366f1' }}
                      onClick={() => handleStopSelect(stop)}
                    >
                      View Buses
                    </Button>
                  </Box>
                </Popup>
              </Marker>
            ))}

            {/* Bus Trails */}
            {liveBuses.map((bus) => (
              bus.trail && bus.trail.length > 1 && (
                <Polyline
                  key={`trail-${bus.bus_id}`}
                  positions={bus.trail.map(p => [p.lat, p.lon])}
                  pathOptions={{ 
                    color: getRouteColor(bus.route),
                    weight: 3,
                    opacity: 0.5,
                    dashArray: '5, 10'
                  }}
                />
              )
            ))}

            {/* Live Buses - Animated */}
            {liveBuses.map((bus) => (
              <AnimatedBusMarker 
                key={bus.bus_id} 
                bus={bus} 
                onClick={setSelectedBus}
              />
            ))}
          </MapContainer>
        ) : (
          <Box sx={{ 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            flexDirection: 'column',
            gap: 2,
            bgcolor: '#0a0e27'
          }}>
            <CircularProgress sx={{ color: '#6366f1' }} />
            <Typography color="rgba(255,255,255,0.6)">Getting location...</Typography>
          </Box>
        )}

        {/* Map Controls */}
        <Box sx={{ position: 'absolute', bottom: 80, right: 16, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <IconButton 
            onClick={getUserLocation}
            sx={{ bgcolor: '#1e3a8a', color: 'white', '&:hover': { bgcolor: '#1e40af' }, boxShadow: 3 }}
          >
            <MyLocationIcon />
          </IconButton>
        </Box>

        {/* Bus Count */}
        <Box sx={{ 
          position: 'absolute', 
          top: 16, 
          left: 16, 
          bgcolor: 'rgba(10, 14, 39, 0.9)',
          backdropFilter: 'blur(10px)',
          px: 2, py: 1,
          borderRadius: 2,
          border: '1px solid rgba(99, 102, 241, 0.3)'
        }}>
          <Typography variant="body2" color="white">
            Live Buses: {liveBuses.length}
          </Typography>
          {lastUpdate && (
            <Typography variant="caption" color="rgba(255,255,255,0.6)">
              Updated: {lastUpdate.toLocaleTimeString()}
            </Typography>
          )}
        </Box>

        {/* Legend */}
        <Box sx={{
          position: 'absolute',
          bottom: 80,
          left: 16,
          bgcolor: 'rgba(10, 14, 39, 0.9)',
          backdropFilter: 'blur(10px)',
          p: 1.5,
          borderRadius: 2,
          border: '1px solid rgba(255,255,255,0.1)',
          maxWidth: 150
        }}>
          <Typography variant="caption" color="white" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
            Routes
          </Typography>
          {getNearbyRoutes().slice(0, 5).map(r => (
            <Box key={r.route} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: r.color }} />
              <Typography variant="caption" color="rgba(255,255,255,0.8)">{r.route}</Typography>
            </Box>
          ))}
        </Box>
      </Box>
    );
  };

  return (
    <Box sx={{ width: '100%', height: '100vh', overflow: 'hidden', bgcolor: '#0a0e27' }}>
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .custom-bus-icon { background: transparent !important; border: none !important; }
      `}</style>

      {selectedStop ? (
        <StopDetailView />
      ) : (
        <>
          <Box sx={{ height: 'calc(100vh - 70px)', overflow: 'hidden' }}>
            {activeTab === 0 && <NearbyView />}
            {activeTab === 1 && <SearchView />}
            {activeTab === 2 && <MapView />}
          </Box>

          <Paper sx={{ position: 'fixed', bottom: 0, left: 0, right: 0, bgcolor: '#0f172a', borderTop: '1px solid rgba(99, 102, 241, 0.2)', zIndex: 1000 }} elevation={0}>
            <BottomNavigation
              value={activeTab}
              onChange={(e, newValue) => setActiveTab(newValue)}
              sx={{ 
                bgcolor: 'transparent',
                '& .MuiBottomNavigationAction-root': { color: 'rgba(255,255,255,0.5)', '&.Mui-selected': { color: '#6366f1' } }
              }}
            >
              <BottomNavigationAction label="Nearby" icon={<LocationOnIcon />} />
              <BottomNavigationAction label="Search" icon={<SearchIcon />} />
              <BottomNavigationAction label="Map" icon={<MapIcon />} />
            </BottomNavigation>
          </Paper>
        </>
      )}
    </Box>
  );
}

export default App;
