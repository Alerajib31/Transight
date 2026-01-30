import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Box, CircularProgress, AppBar, Toolbar, IconButton, Select, MenuItem,
  FormControl, InputLabel, Grid, Paper, Divider, useTheme, useMediaQuery,
  LinearProgress, Stack, Slide, Typography, CardContent, Chip, SwipeableDrawer
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import GroupsIcon from '@mui/icons-material/Groups';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrafficIcon from '@mui/icons-material/Traffic';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import NavigationIcon from '@mui/icons-material/Navigation';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import TimerIcon from '@mui/icons-material/Timer';
import ScheduleIcon from '@mui/icons-material/Schedule';
import PeopleAltIcon from '@mui/icons-material/PeopleAlt';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup, useMap, Circle, Polyline } from 'react-leaflet';
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

const busIcon = new L.Icon({
  iconUrl: 'https://cdn-icons-png.flaticon.com/512/3448/3448339.png',
  iconSize: [45, 45],
});

const userIcon = new L.Icon({
  iconUrl: 'https://cdn-icons-png.flaticon.com/512/847/847969.png',
  iconSize: [40, 40],
});

function RecenterMap({ center }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, 15);
  }, [center, map]);
  return null;
}

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedStop, setSelectedStop] = useState("STOP_001");
  const [userLocation, setUserLocation] = useState(null);
  const [busLocations, setBusLocations] = useState([]);
  const [allStops, setAllStops] = useState([]);
  const [nearbyStops, setNearbyStops] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [locationError, setLocationError] = useState(false);

  const theme = useTheme();
  const isXSmall = useMediaQuery(theme.breakpoints.down('sm'));
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.between('sm', 'lg'));

  const API_BASE_URL = "http://127.0.0.1:8000";

  // Fetch prediction for selected stop
  const fetchPrediction = async () => {
    setRefreshing(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/predict/${selectedStop}`);
      setData(response.data);
      setLoading(false);
    } catch (error) {
      console.error("Error fetching prediction:", error);
      setLoading(false);
    } finally {
      setRefreshing(false);
    }
  };

  // Fetch all bus stops
  const fetchAllStops = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/stops`);
      setAllStops(response.data.stops || []);
    } catch (error) {
      console.error("Error fetching stops:", error);
      setAllStops([]);
    }
  };

  // Fetch live bus locations with fallback
  const fetchLiveBuses = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/live-buses`);
      const buses = response.data.buses || [];
      setBusLocations(buses);
      
      // If no BODS data, generate mock Bristol buses for testing
      if (buses.length === 0) {
        const mockBuses = [
          { bus_id: "BUS001", route: "72", latitude: 51.4510, longitude: -2.5850, speed: 25, occupancy: 12 },
          { bus_id: "BUS002", route: "10", latitude: 51.4520, longitude: -2.5870, speed: 30, occupancy: 8 },
          { bus_id: "BUS003", route: "72", latitude: 51.4480, longitude: -2.5830, speed: 20, occupancy: 15 }
        ];
        setBusLocations(mockBuses);
      }
    } catch (error) {
      console.error("Error fetching live buses:", error);
      // Mock data for testing
      setBusLocations([
        { bus_id: "BUS001", route: "72", latitude: 51.4510, longitude: -2.5850, speed: 25, occupancy: 12 },
        { bus_id: "BUS002", route: "10", latitude: 51.4520, longitude: -2.5870, speed: 30, occupancy: 8 },
        { bus_id: "BUS003", route: "72", latitude: 51.4480, longitude: -2.5830, speed: 20, occupancy: 15 }
      ]);
    }
  };

  // Fetch nearby stops based on user location
  const fetchNearbyStops = async (lat, lon) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/nearby-stops`, {
        params: { latitude: lat, longitude: lon, radius: 2.0 }
      });
      setNearbyStops(response.data.nearby_stops || []);
    } catch (error) {
      console.error("Error fetching nearby stops:", error);
      setNearbyStops([]);
    }
  };

  // Get user location on mount - PRIORITY: Real geolocation, NO fallback
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          const newLocation = [latitude, longitude];
          setUserLocation(newLocation);
          setLocationError(false);
          console.log("✅ Real location acquired:", latitude, longitude);
          fetchNearbyStops(latitude, longitude);
        },
        (error) => {
          console.error("❌ Geolocation failed:", error);
          setLocationError(true);
          // DO NOT fall back to Bristol - let user be aware
        }
      );
    } else {
      console.error("❌ Geolocation not supported");
      setLocationError(true);
    }
  }, []);

  // Fetch initial data when stops load
  useEffect(() => {
    fetchPrediction();
    fetchAllStops();
    fetchLiveBuses();
  }, [selectedStop]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(() => {
      fetchPrediction();
      fetchLiveBuses();
    }, 10000);

    return () => clearInterval(interval);
  }, [autoRefresh, selectedStop]);

  const handleStopChange = (event) => {
    setSelectedStop(event.target.value);
    setLoading(true);
  };

  const getETATime = () => {
    if (!data?.eta_time) return '';
    return data.eta_time;
  };

  const getStatusColor = (crowdLevel, totalTime) => {
    if (totalTime > 15) return '#ef4444';  // Red
    if (totalTime > 10) return '#f97316';  // Orange
    return '#22c55e';  // Green
  };

  const PredictionCard = ({ compact = false }) => (
    loading && !data ? (
      <Box display="flex" justifyContent="center" py={compact ? 2 : 4}>
        <CircularProgress size={compact ? 40 : 60} sx={{ color: '#6366f1' }} />
      </Box>
    ) : data ? (
      <Slide direction="up" in={true}>
        <Paper elevation={0} sx={{ borderRadius: compact ? 2 : 3, overflow: 'hidden', background: `linear-gradient(135deg, ${getStatusColor(data.crowd_level, data.total_time_min)} 0%, ${getStatusColor(data.crowd_level, data.total_time_min)}cc 100%)`, border: '1px solid rgba(255,255,255,0.1)', position: 'relative' }}>
          <Box className="orb" sx={{ position: 'absolute', top: '-50px', right: '-50px', width: '200px', height: '200px', background: 'radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%)', borderRadius: '50%', filter: 'blur(40px)' }} />
          <CardContent sx={{ p: compact ? 2 : 3, position: 'relative', zIndex: 1 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={compact ? 1 : 2}>
              <Box>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', letterSpacing: '1px' }}>LIVE PREDICTION</Typography>
                <Typography variant={compact ? "body2" : "h6"} fontWeight={800} sx={{ color: 'white', mt: 0.5 }}>{data.stop_name}</Typography>
              </Box>
              <NotificationsActiveIcon className="pulse-icon" sx={{ color: 'white', fontSize: compact ? 20 : 24 }} />
            </Box>

            <Paper elevation={0} sx={{ background: 'rgba(255,255,255,0.95)', p: compact ? 1.5 : 2.5, borderRadius: 2, textAlign: 'center', mb: compact ? 1.5 : 2, boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
              <Typography sx={{ fontWeight: 900, fontSize: compact ? '2rem' : '3.5rem', color: getStatusColor(data.crowd_level, data.total_time_min), lineHeight: 1, mb: 0.5 }}>
                {data.total_time_min}
              </Typography>
              <Typography variant={compact ? "caption" : "body2"} sx={{ color: '#64748b', fontWeight: 600, mb: compact ? 0.5 : 1 }}>minutes</Typography>
              <Divider sx={{ my: compact ? 0.5 : 1 }} />
              <Box display="flex" alignItems="center" justifyContent="center" gap={1} sx={{ flexWrap: 'wrap', mt: compact ? 0.5 : 1 }}>
                <AccessTimeIcon sx={{ color: '#6366f1', fontSize: compact ? 14 : 18 }} />
                <Typography variant={compact ? "caption" : "body2"} sx={{ color: '#475569', fontWeight: 600 }}>Arrives at {getETATime()}</Typography>
              </Box>
            </Paper>

            <Grid container spacing={compact ? 0.5 : 1} mb={compact ? 1 : 1.5}>
              <Grid item xs={6}>
                <Paper elevation={0} sx={{ p: compact ? 1 : 1.5, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(10px)', textAlign: 'center' }}>
                  <PeopleAltIcon sx={{ color: '#fbbf24', fontSize: compact ? 20 : 28, mb: 0.3 }} />
                  <Typography variant={compact ? "body2" : "h6"} fontWeight={800} sx={{ color: 'white', mb: 0.3 }}>{data.crowd_count}</Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>People Waiting</Typography>
                </Paper>
              </Grid>
              <Grid item xs={6}>
                <Paper elevation={0} sx={{ p: compact ? 1 : 1.5, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(10px)', textAlign: 'center' }}>
                  <TrafficIcon sx={{ color: '#f87171', fontSize: compact ? 20 : 28, mb: 0.3 }} />
                  <Typography variant="caption" fontWeight={700} sx={{ color: 'white', mb: 0.3, display: 'block' }}>{data.traffic_status}</Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>Traffic</Typography>
                </Paper>
              </Grid>
            </Grid>

            <Paper elevation={0} sx={{ bgcolor: 'rgba(255,255,255,0.1)', p: compact ? 1.5 : 2, borderRadius: 2, backdropFilter: 'blur(10px)', mb: compact ? 1 : 1.5 }}>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <TimerIcon sx={{ color: '#fbbf24', fontSize: compact ? 16 : 20 }} />
                <Typography variant={compact ? "caption" : "body2"} fontWeight={700} sx={{ color: 'white' }}>Delay Breakdown</Typography>
              </Box>
              <Grid container spacing={compact ? 0.5 : 1}>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', bgcolor: 'rgba(0,0,0,0.2)', p: compact ? 0.8 : 1, borderRadius: 1.5 }}>
                    <TrafficIcon sx={{ color: '#f87171', fontSize: compact ? 14 : 18 }} />
                    <Typography variant={compact ? "caption" : "body2"} fontWeight={800} sx={{ color: 'white', display: 'block' }}>{data.traffic_delay.toFixed(1)} min</Typography>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontSize: compact ? '0.6rem' : '0.7rem' }}>Traffic</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', bgcolor: 'rgba(0,0,0,0.2)', p: compact ? 0.8 : 1, borderRadius: 1.5 }}>
                    <ScheduleIcon sx={{ color: '#60a5fa', fontSize: compact ? 14 : 18 }} />
                    <Typography variant={compact ? "caption" : "body2"} fontWeight={800} sx={{ color: 'white', display: 'block' }}>{data.dwell_delay.toFixed(1)} min</Typography>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontSize: compact ? '0.6rem' : '0.7rem' }}>Boarding</Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>

            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', bgcolor: 'rgba(255,255,255,0.1)', p: compact ? 1 : 1.5, borderRadius: 2, backdropFilter: 'blur(10px)' }}>
              <Typography variant={compact ? "caption" : "body2"} sx={{ color: 'white', fontWeight: 600 }}>Confidence: {(data.confidence * 100).toFixed(0)}%</Typography>
              <Chip label={data.crowd_level} size={compact ? "small" : "medium"} sx={{ bgcolor: data.crowd_level === "High" ? '#ef4444' : '#22c55e', color: 'white', fontWeight: 700, fontSize: compact ? '0.7rem' : '0.8rem' }}/>
            </Box>
          </CardContent>
        </Paper>
      </Slide>
    ) : null
  );

  return (
    <Box sx={{ width: '100%', height: '100vh', overflow: 'hidden', background: '#0a0e27', display: 'flex', flexDirection: 'column' }}>
      {/* HEADER */}
      <AppBar position="sticky" elevation={0} sx={{ background: 'rgba(15, 23, 42, 0.95)', backdropFilter: 'blur(20px)', borderBottom: '1px solid rgba(99, 102, 241, 0.2)' }}>
        <Toolbar sx={{ justifyContent: 'space-between', px: isXSmall ? 1 : 2, py: isXSmall ? 0.5 : 1 }}>
          <Box display="flex" alignItems="center" gap={1} sx={{ minWidth: 0, flex: 1 }}>
            <Box sx={{ width: isXSmall ? 36 : 44, height: isXSmall ? 36 : 44, borderRadius: '12px', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: '0 8px 32px rgba(102, 126, 234, 0.4)' }}>
              <DirectionsBusIcon sx={{ color: 'white', fontSize: isXSmall ? 18 : 24 }} />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant={isXSmall ? "body2" : "h6"} fontWeight={800} sx={{ color: 'white', whiteSpace: 'nowrap' }}>Transight AI</Typography>
              {!isXSmall && <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', display: 'block' }}>Real-Time Prediction</Typography>}
            </Box>
          </Box>
          <Box display="flex" gap={1}>
            <IconButton 
              onClick={() => setAutoRefresh(!autoRefresh)} 
              size={isXSmall ? "small" : "medium"} 
              sx={{ bgcolor: autoRefresh ? 'rgba(34, 197, 94, 0.2)' : 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)', '&:hover': { bgcolor: 'rgba(99, 102, 241, 0.2)' }, flexShrink: 0 }}
            >
              <NavigationIcon sx={{ color: autoRefresh ? '#22c55e' : '#6366f1' }} />
            </IconButton>
            <IconButton 
              onClick={fetchPrediction} 
              size={isXSmall ? "small" : "medium"} 
              sx={{ bgcolor: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)', '&:hover': { bgcolor: 'rgba(99, 102, 241, 0.2)' }, flexShrink: 0 }}
            >
              <RefreshIcon sx={{ color: '#6366f1', animation: refreshing ? 'rotate 1s linear infinite' : 'none', '@keyframes rotate': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } } }} />
            </IconButton>
          </Box>
        </Toolbar>
        {refreshing && <LinearProgress sx={{ bgcolor: 'rgba(99, 102, 241, 0.1)', height: 2 }} />}
      </AppBar>

      {/* MAIN CONTENT */}
      <Box sx={{ display: 'flex', flex: 1, width: '100%', gap: 0, overflow: 'hidden' }}>
        
        {/* DESKTOP/TABLET SIDEBAR */}
        {!isMobile && (
          <Box sx={{ width: isTablet ? '45%' : '420px', height: '100%', overflowY: 'auto', background: 'linear-gradient(180deg, #0f172a 0%, #1e293b 100%)', borderRight: '1px solid rgba(99, 102, 241, 0.2)', p: isTablet ? 2 : 3, '&::-webkit-scrollbar': { width: '8px' }, '&::-webkit-scrollbar-track': { background: 'rgba(0,0,0,0.1)' }, '&::-webkit-scrollbar-thumb': { background: 'rgba(99, 102, 241, 0.5)', borderRadius: '4px' }, flexShrink: 0 }}>
            <Stack spacing={isTablet ? 2 : 2.5}>
              {/* STOP SELECTOR */}
              <Paper elevation={0} sx={{ p: isTablet ? 1.5 : 2, borderRadius: 2, background: 'rgba(30, 41, 59, 0.8)', border: '1px solid rgba(99, 102, 241, 0.2)', backdropFilter: 'blur(10px)' }}>
                <FormControl fullWidth size={isTablet ? "small" : "medium"}>
                  <InputLabel sx={{ color: 'rgba(255,255,255,0.7)' }}>Bus Stop</InputLabel>
                  <Select value={selectedStop} label="Bus Stop" onChange={handleStopChange} sx={{ borderRadius: 2, color: 'white', '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(99, 102, 241, 0.3)' }, '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(99, 102, 241, 0.5)' }, '& .MuiSvgIcon-root': { color: 'white' } }}>
                    {allStops.map((stop) => (
                      <MenuItem key={stop.stop_id} value={stop.stop_id}>
                        🚏 {stop.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Paper>

              {/* NEARBY STOPS */}
              {nearbyStops.length > 0 && (
                <Paper elevation={0} sx={{ p: isTablet ? 1.5 : 2, borderRadius: 2, background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.1) 100%)', border: '1px solid rgba(59, 130, 246, 0.3)', backdropFilter: 'blur(10px)' }}>
                  <Box display="flex" alignItems="center" gap={1} mb={1.5}>
                    <NavigationIcon sx={{ color: '#3b82f6', fontSize: isTablet ? 18 : 22 }} />
                    <Typography variant={isTablet ? "subtitle2" : "body2"} fontWeight={700} sx={{ color: 'white' }}>Nearby Stops</Typography>
                  </Box>
                  <Stack spacing={1}>
                    {nearbyStops.slice(0, 3).map((stop) => (
                      <Box 
                        key={stop.stop_id}
                        onClick={() => setSelectedStop(stop.stop_id)}
                        sx={{ p: 1, borderRadius: 1.5, bgcolor: 'rgba(0,0,0,0.2)', cursor: 'pointer', '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.2)' }, transition: 'all 0.2s' }}
                      >
                        <Typography variant="caption" fontWeight={700} sx={{ color: 'white' }}>
                          {stop.name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', display: 'block' }}>
                          {stop.distance_km} km away
                        </Typography>
                      </Box>
                    ))}
                  </Stack>
                </Paper>
              )}

              {/* LOCATION INFO */}
              <Paper elevation={0} sx={{ p: isTablet ? 1.5 : 2, borderRadius: 2, background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(16, 185, 129, 0.1) 100%)', border: '1px solid rgba(34, 197, 94, 0.3)', backdropFilter: 'blur(10px)' }}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <NavigationIcon sx={{ color: '#22c55e', fontSize: isTablet ? 18 : 22 }} />
                  <Typography variant={isTablet ? "subtitle2" : "body2"} fontWeight={700} sx={{ color: 'white' }}>Your Location</Typography>
                </Box>
                {userLocation ? (
                  <Box sx={{ fontFamily: 'monospace', fontSize: isTablet ? '0.7rem' : '0.8rem', color: 'rgba(255,255,255,0.8)', bgcolor: 'rgba(0,0,0,0.2)', p: isTablet ? 1 : 1.5, borderRadius: 2, mb: 1 }}>
                    <Box>📍 {userLocation[0].toFixed(4)}°</Box>
                    <Box>{userLocation[1].toFixed(4)}°</Box>
                  </Box>
                ) : (
                  <Box sx={{ fontFamily: 'monospace', fontSize: isTablet ? '0.7rem' : '0.8rem', color: '#ef4444', bgcolor: 'rgba(239, 68, 68, 0.1)', p: isTablet ? 1 : 1.5, borderRadius: 2, mb: 1 }}>
                    {locationError ? '❌ Location access denied' : '⏳ Requesting location...'}
                  </Box>
                )}
              </Paper>

              {/* PREDICTION CARD */}
              <PredictionCard compact={isTablet} />
              
              {/* LIVE BUSES INFO */}
              {busLocations.length > 0 && (
                <Paper elevation={0} sx={{ p: isTablet ? 1.5 : 2, borderRadius: 2, background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(139, 92, 246, 0.1) 100%)', border: '1px solid rgba(168, 85, 247, 0.3)', backdropFilter: 'blur(10px)' }}>
                  <Box display="flex" alignItems="center" gap={1} mb={1}>
                    <DirectionsBusIcon sx={{ color: '#a855f7', fontSize: isTablet ? 18 : 22 }} />
                    <Typography variant={isTablet ? "subtitle2" : "body2"} fontWeight={700} sx={{ color: 'white' }}>Live Buses ({busLocations.length})</Typography>
                  </Box>
                  <Stack spacing={1}>
                    {busLocations.slice(0, 3).map((bus) => (
                      <Box key={bus.bus_id} sx={{ p: 1, borderRadius: 1.5, bgcolor: 'rgba(0,0,0,0.2)', fontSize: '0.75rem' }}>
                        <Typography variant="caption" fontWeight={700} sx={{ color: '#a855f7' }}>Bus {bus.bus_id}</Typography>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', display: 'block' }}>
                          Route {bus.route} • {bus.speed} km/h
                        </Typography>
                      </Box>
                    ))}
                  </Stack>
                </Paper>
              )}
            </Stack>
          </Box>
        )}

        {/* MAP - FULL WIDTH ON MOBILE, SHARED ON TABLET/DESKTOP */}
        <Box sx={{ flex: 1, height: '100%', position: 'relative', minWidth: 0, background: '#0a0e27', display: 'flex', flexDirection: 'column' }}>
          {locationError && (
            <Box sx={{ 
              position: 'absolute', 
              top: 10, 
              left: 10, 
              zIndex: 1000, 
              bgcolor: '#ef4444', 
              color: 'white', 
              p: 2, 
              borderRadius: 2,
              fontSize: '0.9rem',
              fontWeight: 600,
              maxWidth: '300px'
            }}>
              📍 Location access denied or unavailable
            </Box>
          )}
          
          {userLocation ? (
            <MapContainer center={userLocation} zoom={15} style={{ height: "100%", width: "100%" }} zoomControl={!isXSmall}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap' />
              <RecenterMap center={userLocation} />
              
              {/* User Location */}
              <Marker position={userLocation} icon={userIcon}>
                <Popup>
                  <Box sx={{ p: 1 }}>
                    <Typography variant="subtitle2" fontWeight={700}>📍 Your Location</Typography>
                    <Divider sx={{ my: 1 }} />
                    <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>{userLocation[0].toFixed(4)}, {userLocation[1].toFixed(4)}</Typography>
                  </Box>
                </Popup>
              </Marker>

              {/* All Bus Stops */}
              {allStops.map((stop) => (
                <Marker key={stop.stop_id} position={[stop.latitude, stop.longitude]} icon={L.icon({
                  iconUrl: 'https://cdn-icons-png.flaticon.com/512/1524/1524822.png',
                  iconSize: [35, 35],
                })}>
                  <Popup>
                    <Box sx={{ p: 1, minWidth: '150px' }}>
                      <Typography variant="subtitle2" fontWeight={700}>{stop.name}</Typography>
                      <Divider sx={{ my: 0.5 }} />
                      <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
                        Routes: {stop.routes.join(', ')}
                      </Typography>
                    </Box>
                  </Popup>
                </Marker>
              ))}

              {/* Live Buses */}
              {busLocations.map((bus) => (
                <Marker key={bus.bus_id} position={[bus.latitude, bus.longitude]} icon={busIcon}>
                  <Popup>
                    <Box sx={{ p: 1 }}>
                      <Typography variant="subtitle2" fontWeight={700}>🚌 Bus {bus.bus_id}</Typography>
                      <Divider sx={{ my: 1 }} />
                      <Typography variant="caption" sx={{ display: 'block' }}>
                        Route: {bus.route}
                      </Typography>
                      <Typography variant="caption" sx={{ display: 'block' }}>
                        Speed: {bus.speed} km/h
                      </Typography>
                    </Box>
                  </Popup>
                </Marker>
              ))}

              {/* Service Radius Circles */}
              {allStops.map((stop) => (
                <Circle 
                  key={`circle-${stop.stop_id}`}
                  center={[stop.latitude, stop.longitude]} 
                  radius={200} 
                  pathOptions={{ color: 'rgba(99, 102, 241, 0.3)', weight: 2, fillOpacity: 0.1 }} 
                />
              ))}

              {/* Connection Lines */}
              {busLocations.length > 0 && <Polyline 
                positions={busLocations.map(bus => [bus.latitude, bus.longitude])} 
                pathOptions={{ color: '#a855f7', weight: 1, opacity: 0.4, dashArray: '5, 5' }} 
              />}
            </MapContainer>
          ) : (
            <Box sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              height: '100%',
              flexDirection: 'column',
              gap: 2
            }}>
              <CircularProgress sx={{ color: '#6366f1' }} />
              <Typography sx={{ color: 'rgba(255,255,255,0.7)' }}>
                Requesting your location...
              </Typography>
            </Box>
          )}

          {/* MOBILE BOTTOM SHEET */}
          {isXSmall && (
            <SwipeableDrawer
              anchor="bottom"
              open={true}
              onOpen={() => {}}
              onClose={() => {}}
              sx={{ '& .MuiDrawer-paper': { background: 'linear-gradient(180deg, #1e293b 0%, #0f172a 100%)', borderTop: '1px solid rgba(99, 102, 241, 0.2)', borderRadius: '16px 16px 0 0', height: 'auto', maxHeight: '60vh', position: 'absolute', bottom: 0 } }}
            >
              <Box sx={{ p: 2, width: '100%', maxHeight: '60vh', overflowY: 'auto', '&::-webkit-scrollbar': { width: '6px' }, '&::-webkit-scrollbar-track': { background: 'rgba(0,0,0,0.1)' }, '&::-webkit-scrollbar-thumb': { background: 'rgba(99, 102, 241, 0.5)', borderRadius: '3px' } }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="body2" fontWeight={700} sx={{ color: 'white' }}>Prediction</Typography>
                  <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel sx={{ color: 'rgba(255,255,255,0.7)' }}>Stop</InputLabel>
                    <Select value={selectedStop} label="Stop" onChange={handleStopChange} sx={{ borderRadius: 1, color: 'white', '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(99, 102, 241, 0.3)' }, '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(99, 102, 241, 0.5)' }, '& .MuiSvgIcon-root': { color: 'white' } }}>
                      {allStops.map((stop) => (
                        <MenuItem key={stop.stop_id} value={stop.stop_id}>🚏 {stop.name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Box>
                <PredictionCard compact={true} />
              </Box>
            </SwipeableDrawer>
          )}
        </Box>
      </Box>

      <style>
        {`
          @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
          .pulse-icon { animation: pulse 2s infinite; }
          @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
          * { box-sizing: border-box; }
        `}
      </style>
    </Box>
  );
}

export default App;
