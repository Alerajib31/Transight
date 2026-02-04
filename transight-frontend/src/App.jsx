import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, AppBar, Toolbar, IconButton, Typography, TextField,
  Paper, Divider, useTheme, useMediaQuery, InputAdornment, Chip,
  List, ListItem, ListItemButton, ListItemText, ListItemIcon,
  BottomNavigation, BottomNavigationAction, SwipeableDrawer,
  Button, Fade, Slide, Card, CardContent, Badge
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import RefreshIcon from '@mui/icons-material/Refresh';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import NavigationIcon from '@mui/icons-material/Navigation';
import MapIcon from '@mui/icons-material/Map';
import ListIcon from '@mui/icons-material/List';
import StarIcon from '@mui/icons-material/Star';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
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

const busIcon = new L.Icon({
  iconUrl: 'https://cdn-icons-png.flaticon.com/512/3448/3448339.png',
  iconSize: [40, 40],
  iconAnchor: [20, 40],
});

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

function RecenterMap({ center }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, 15);
  }, [center, map]);
  return null;
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
  const isXSmall = useMediaQuery(theme.breakpoints.down('sm'));

  // State
  const [activeTab, setActiveTab] = useState(0); // 0 = Nearby, 1 = Search, 2 = Map
  const [userLocation, setUserLocation] = useState(null);
  const [locationError, setLocationError] = useState(false);
  const [loadingLocation, setLoadingLocation] = useState(true);
  
  const [nearbyStops, setNearbyStops] = useState([]);
  const [liveBuses, setLiveBuses] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopDetail, setStopDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const API_BASE_URL = "http://127.0.0.1:8000";
  const refreshInterval = useRef(null);

  // Get user location
  const getUserLocation = () => {
    setLoadingLocation(true);
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          setUserLocation([latitude, longitude]);
          setLocationError(false);
          setLoadingLocation(false);
          fetchNearbyStops(latitude, longitude);
          fetchLiveBuses(latitude, longitude);
        },
        (error) => {
          console.error("Geolocation failed:", error);
          setLocationError(true);
          setLoadingLocation(false);
          // Use Bristol as fallback for demo
          setUserLocation([51.4545, -2.5879]);
          fetchNearbyStops(51.4545, -2.5879);
          fetchLiveBuses(51.4545, -2.5879);
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    } else {
      setLocationError(true);
      setLoadingLocation(false);
    }
  };

  // Fetch nearby stops
  const fetchNearbyStops = async (lat, lon, radius = 1.0) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/nearby-stops`, {
        params: { latitude: lat, longitude: lon, radius }
      });
      setNearbyStops(response.data.nearby_stops || []);
    } catch (error) {
      console.error("Error fetching nearby stops:", error);
    }
  };

  // Fetch live buses
  const fetchLiveBuses = async (lat, lon, radius = 5.0) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/live-buses`, {
        params: { lat: lat, lon: lon, radius }
      });
      setLiveBuses(response.data.buses || []);
    } catch (error) {
      console.error("Error fetching live buses:", error);
    }
  };

  // Search stops
  const searchStops = async (query) => {
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
      console.error("Error searching stops:", error);
    }
  };

  // Fetch stop detail
  const fetchStopDetail = async (stopId) => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/stops/${stopId}`);
      setStopDetail(response.data);
    } catch (error) {
      console.error("Error fetching stop detail:", error);
    } finally {
      setLoading(false);
    }
  };

  // Refresh all data
  const refreshData = async () => {
    if (!userLocation) return;
    setRefreshing(true);
    await Promise.all([
      fetchNearbyStops(userLocation[0], userLocation[1]),
      fetchLiveBuses(userLocation[0], userLocation[1])
    ]);
    if (selectedStop) {
      await fetchStopDetail(selectedStop.stop_id);
    }
    setRefreshing(false);
  };

  // Initial load
  useEffect(() => {
    getUserLocation();
  }, []);

  // Auto-refresh
  useEffect(() => {
    if (!userLocation) return;
    
    refreshInterval.current = setInterval(() => {
      fetchLiveBuses(userLocation[0], userLocation[1]);
      if (selectedStop) {
        fetchStopDetail(selectedStop.stop_id);
      }
    }, 15000); // Every 15 seconds

    return () => clearInterval(refreshInterval.current);
  }, [userLocation, selectedStop]);

  // Debounced search
  useEffect(() => {
    const timeout = setTimeout(() => {
      searchStops(searchQuery);
    }, 300);
    return () => clearTimeout(timeout);
  }, [searchQuery]);

  // Handle stop selection
  const handleStopSelect = (stop) => {
    setSelectedStop(stop);
    fetchStopDetail(stop.stop_id);
  };

  // Handle back
  const handleBack = () => {
    setSelectedStop(null);
    setStopDetail(null);
  };

  // Get buses for a specific stop
  const getBusesForStop = (stopId) => {
    return liveBuses.filter(bus => bus.next_stop_ref === stopId);
  };

  // Get unique routes from live buses
  const getNearbyRoutes = () => {
    const routes = {};
    liveBuses.forEach(bus => {
      const route = bus.route;
      if (!routes[route]) {
        routes[route] = {
          route,
          destination: bus.destination,
          buses: []
        };
      }
      routes[route].buses.push(bus);
    });
    return Object.values(routes).sort((a, b) => a.route.localeCompare(b.route));
  };

  // Render stop detail view
  const StopDetailView = () => {
    if (!selectedStop) return null;
    
    const buses = stopDetail?.upcoming_buses || getBusesForStop(selectedStop.stop_id);
    
    return (
      <Box sx={{ height: '100%', overflow: 'auto', bgcolor: '#0a0e27' }}>
        {/* Header */}
        <AppBar position="sticky" sx={{ bgcolor: '#1e3a8a' }}>
          <Toolbar>
            <IconButton edge="start" color="inherit" onClick={handleBack} sx={{ mr: 1 }}>
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
            <IconButton color="inherit" onClick={refreshData}>
              <RefreshIcon sx={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            </IconButton>
          </Toolbar>
        </AppBar>

        {/* Bus List */}
        <Box sx={{ p: 2 }}>
          {loading ? (
            <Box display="flex" justifyContent="center" py={4}>
              <CircularProgress sx={{ color: '#6366f1' }} />
            </Box>
          ) : buses.length === 0 ? (
            <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
              <DirectionsBusIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1 }} />
              <Typography>No buses currently heading to this stop</Typography>
            </Paper>
          ) : (
            <>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 2, display: 'block' }}>
                LIVE DEPARTURES ({buses.length} buses)
              </Typography>
              <List sx={{ gap: 1.5, display: 'flex', flexDirection: 'column' }}>
                {buses.map((bus, idx) => (
                  <Slide key={bus.bus_id || idx} direction="up" in={true} style={{ transitionDelay: idx * 50 }}>
                    <Paper sx={{ 
                      bgcolor: 'rgba(30, 41, 59, 0.8)', 
                      border: '1px solid rgba(99, 102, 241, 0.2)',
                      overflow: 'hidden'
                    }}>
                      <ListItem>
                        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 2 }}>
                          {/* Route Number */}
                          <Box sx={{ 
                            minWidth: 60, height: 60, 
                            bgcolor: '#6366f1', 
                            borderRadius: 2,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '1.5rem', fontWeight: 800, color: 'white'
                          }}>
                            {bus.route}
                          </Box>
                          
                          {/* Info */}
                          <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Typography variant="subtitle1" fontWeight={700} color="white" noWrap>
                              {bus.destination}
                            </Typography>
                            <Typography variant="caption" color="rgba(255,255,255,0.6)" display="block">
                              {bus.operator} • Bus {bus.bus_id}
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                              <Chip 
                                size="small" 
                                label={bus.delay_minutes > 0 ? `${bus.delay_minutes}m late` : 'On time'}
                                sx={{ 
                                  bgcolor: bus.delay_minutes > 2 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)',
                                  color: bus.delay_minutes > 2 ? '#ef4444' : '#22c55e',
                                  fontSize: '0.7rem'
                                }} 
                              />
                              <Typography variant="caption" color="rgba(255,255,255,0.5)">
                                {bus.speed} km/h
                              </Typography>
                            </Box>
                          </Box>

                          {/* ETA */}
                          <Box sx={{ textAlign: 'right' }}>
                            <Typography variant="h5" fontWeight={800} color="#22c55e">
                              {formatArrival(bus.delay_minutes > 0 ? bus.delay_minutes + 5 : 5)}
                            </Typography>
                            <Typography variant="caption" color="rgba(255,255,255,0.5)">
                              {bus.expected_arrival ? new Date(bus.expected_arrival).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}
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

        {/* Prediction Card */}
        {stopDetail?.prediction && (
          <Box sx={{ px: 2, pb: 2 }}>
            <Paper sx={{ 
              p: 2, 
              bgcolor: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
              background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
              color: 'white'
            }}>
              <Typography variant="caption" sx={{ opacity: 0.8 }}>AI PREDICTION</Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
                <Box>
                  <Typography variant="h4" fontWeight={800}>
                    {stopDetail.prediction.total_time_min} min
                  </Typography>
                  <Typography variant="caption">Estimated arrival</Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography variant="body2" fontWeight={600}>
                    Crowd: {stopDetail.prediction.crowd_count} people
                  </Typography>
                  <Typography variant="caption" sx={{ opacity: 0.8 }}>
                    {stopDetail.prediction.traffic_status}
                  </Typography>
                </Box>
              </Box>
            </Paper>
          </Box>
        )}
      </Box>
    );
  };

  // Render nearby stops list
  const NearbyView = () => (
    <Box sx={{ height: '100%', overflow: 'auto', bgcolor: '#0a0e27' }}>
      {/* Header */}
      <AppBar position="sticky" sx={{ bgcolor: '#1e3a8a' }}>
        <Toolbar>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" fontWeight={700}>Nearby Stops</Typography>
            <Typography variant="caption" sx={{ opacity: 0.8 }}>
              {userLocation ? `${userLocation[0].toFixed(4)}, ${userLocation[1].toFixed(4)}` : 'Getting location...'}
            </Typography>
          </Box>
          <IconButton color="inherit" onClick={getUserLocation}>
            <MyLocationIcon />
          </IconButton>
          <IconButton color="inherit" onClick={refreshData}>
            <RefreshIcon sx={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Box sx={{ p: 2 }}>
        {/* Nearby Routes */}
        {getNearbyRoutes().length > 0 && (
          <>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1.5, display: 'block' }}>
              ACTIVE ROUTES NEARBY
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
              {getNearbyRoutes().slice(0, 8).map(route => (
                <Chip 
                  key={route.route}
                  label={`${route.route} → ${route.destination}`}
                  size="small"
                  sx={{ 
                    bgcolor: 'rgba(99, 102, 241, 0.2)', 
                    color: '#a5b4fc',
                    border: '1px solid rgba(99, 102, 241, 0.3)'
                  }}
                />
              ))}
            </Box>
          </>
        )}

        {/* Stops List */}
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1.5, display: 'block' }}>
          STOPS WITHIN 1km ({nearbyStops.length})
        </Typography>
        
        {nearbyStops.length === 0 ? (
          <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
            <LocationOnIcon sx={{ fontSize: 48, opacity: 0.3, mb: 1 }} />
            <Typography>No stops found nearby</Typography>
            <Button 
              variant="outlined" 
              size="small" 
              onClick={() => userLocation && fetchNearbyStops(userLocation[0], userLocation[1], 2.0)}
              sx={{ mt: 2, color: '#6366f1', borderColor: '#6366f1' }}
            >
              Search 2km radius
            </Button>
          </Paper>
        ) : (
          <List sx={{ gap: 1, display: 'flex', flexDirection: 'column' }}>
            {nearbyStops.map((stop, idx) => {
              const busesAtStop = getBusesForStop(stop.stop_id);
              return (
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
                          <Typography variant="caption" color="rgba(255,255,255,0.5)" component="span">
                            {stop.indicator} {stop.locality} • {formatDistance(stop.distance_km)}
                          </Typography>
                          {busesAtStop.length > 0 && (
                            <Box sx={{ mt: 0.5 }}>
                              <Typography variant="caption" sx={{ color: '#22c55e' }}>
                                🚌 {busesAtStop.length} bus{busesAtStop.length > 1 ? 'es' : ''} approaching
                              </Typography>
                            </Box>
                          )}
                        </>
                      }
                    />
                    {busesAtStop.length > 0 && (
                      <Badge 
                        badgeContent={busesAtStop.length} 
                        color="success"
                        sx={{ '& .MuiBadge-badge': { bgcolor: '#22c55e' } }}
                      />
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

  // Render search view
  const SearchView = () => (
    <Box sx={{ height: '100%', overflow: 'auto', bgcolor: '#0a0e27' }}>
      {/* Header */}
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
            <Typography>Type to search for bus stops</Typography>
          </Paper>
        ) : searchResults.length === 0 ? (
          <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>
            <Typography>No stops found for "{searchQuery}"</Typography>
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
                    border: '1px solid rgba(99, 102, 241, 0.2)',
                    '&:hover': { bgcolor: 'rgba(99, 102, 241, 0.15)' }
                  }}
                >
                  <ListItemIcon>
                    <LocationOnIcon sx={{ color: '#6366f1' }} />
                  </ListItemIcon>
                  <ListItemText 
                    primary={
                      <Typography variant="subtitle1" fontWeight={600} color="white">
                        {stop.name}
                      </Typography>
                    }
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

  // Render map view
  const MapView = () => (
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
              eventHandlers={{
                click: () => handleStopSelect(stop)
              }}
            >
              <Popup>
                <Box sx={{ minWidth: 150 }}>
                  <Typography variant="subtitle2" fontWeight={700}>{stop.name}</Typography>
                  <Typography variant="caption" display="block" color="text.secondary">
                    {stop.indicator} {stop.locality}
                  </Typography>
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

          {/* Live Buses */}
          {liveBuses.map((bus) => (
            <Marker 
              key={bus.bus_id} 
              position={[bus.latitude, bus.longitude]} 
              icon={busIcon}
            >
              <Popup>
                <Box>
                  <Typography variant="subtitle2" fontWeight={700}>Bus {bus.route}</Typography>
                  <Typography variant="caption" display="block">To: {bus.destination}</Typography>
                  <Typography variant="caption" display="block">Speed: {bus.speed} km/h</Typography>
                  <Typography variant="caption" display="block" color={bus.delay_minutes > 0 ? 'error' : 'success'}>
                    {bus.delay_minutes > 0 ? `${bus.delay_minutes} min late` : 'On time'}
                  </Typography>
                </Box>
              </Popup>
            </Marker>
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
          <Typography color="rgba(255,255,255,0.6)">Getting your location...</Typography>
        </Box>
      )}

      {/* Map Controls */}
      <Box sx={{ 
        position: 'absolute', 
        bottom: 80, 
        right: 16, 
        display: 'flex', 
        flexDirection: 'column', 
        gap: 1 
      }}>
        <IconButton 
          onClick={getUserLocation}
          sx={{ 
            bgcolor: '#1e3a8a', 
            color: 'white',
            '&:hover': { bgcolor: '#1e40af' },
            boxShadow: 3
          }}
        >
          <MyLocationIcon />
        </IconButton>
        <IconButton 
          onClick={refreshData}
          sx={{ 
            bgcolor: '#1e3a8a', 
            color: 'white',
            '&:hover': { bgcolor: '#1e40af' },
            boxShadow: 3
          }}
        >
          <RefreshIcon sx={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
        </IconButton>
      </Box>

      {/* Bus Count Badge */}
      <Box sx={{ 
        position: 'absolute', 
        top: 16, 
        left: 16, 
        bgcolor: 'rgba(10, 14, 39, 0.9)',
        backdropFilter: 'blur(10px)',
        px: 2,
        py: 1,
        borderRadius: 2,
        border: '1px solid rgba(99, 102, 241, 0.3)'
      }}>
        <Typography variant="body2" color="white">
          🚌 {liveBuses.length} buses nearby
        </Typography>
      </Box>
    </Box>
  );

  // Main render
  return (
    <Box sx={{ width: '100%', height: '100vh', overflow: 'hidden', bgcolor: '#0a0e27' }}>
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>

      {selectedStop ? (
        <StopDetailView />
      ) : (
        <>
          {/* Main Content Area */}
          <Box sx={{ height: 'calc(100vh - 70px)', overflow: 'hidden' }}>
            {activeTab === 0 && <NearbyView />}
            {activeTab === 1 && <SearchView />}
            {activeTab === 2 && <MapView />}
          </Box>

          {/* Bottom Navigation */}
          <Paper 
            sx={{ 
              position: 'fixed', 
              bottom: 0, 
              left: 0, 
              right: 0,
              bgcolor: '#0f172a',
              borderTop: '1px solid rgba(99, 102, 241, 0.2)',
              zIndex: 1000
            }} 
            elevation={0}
          >
            <BottomNavigation
              value={activeTab}
              onChange={(e, newValue) => setActiveTab(newValue)}
              sx={{ 
                bgcolor: 'transparent',
                '& .MuiBottomNavigationAction-root': {
                  color: 'rgba(255,255,255,0.5)',
                  '&.Mui-selected': { color: '#6366f1' }
                }
              }}
            >
              <BottomNavigationAction 
                label="Nearby" 
                icon={<LocationOnIcon />} 
              />
              <BottomNavigationAction 
                label="Search" 
                icon={<SearchIcon />} 
              />
              <BottomNavigationAction 
                label="Map" 
                icon={<MapIcon />} 
              />
            </BottomNavigation>
          </Paper>
        </>
      )}
    </Box>
  );
}

export default App;
