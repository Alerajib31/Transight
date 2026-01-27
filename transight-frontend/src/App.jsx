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
  const [selectedStop, setSelectedStop] = useState("BST-001");
  const [userLocation] = useState([51.4496, -2.5811]);
  const [busLocation, setBusLocation] = useState([51.4545, -2.5879]);
  const [refreshing, setRefreshing] = useState(false);

  const theme = useTheme();
  const isXSmall = useMediaQuery(theme.breakpoints.down('sm'));
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.between('sm', 'lg'));

  const API_BASE_URL = "http://127.0.0.1:8000/predict";

  const fetchPrediction = async () => {
    setRefreshing(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/${selectedStop}`);
      setData(response.data);
      if (response.data.bus_lat && response.data.bus_lon) {
        setBusLocation([response.data.bus_lat, response.data.bus_lon]);
      }
      setLoading(false);
    } catch (error) {
      console.error("Error:", error);
      setLoading(false);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchPrediction();
  }, [selectedStop]);

  const handleStopChange = (event) => {
    setSelectedStop(event.target.value);
    setLoading(true);
  };

  const getETATime = () => {
    if (!data) return '';
    const now = new Date();
    now.setMinutes(now.getMinutes() + Math.round(data.total_time_min));
    return now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  const PredictionCard = ({ compact = false }) => (
    loading && !data ? (
      <Box display="flex" justifyContent="center" py={compact ? 2 : 4}>
        <CircularProgress size={compact ? 40 : 60} sx={{ color: '#6366f1' }} />
      </Box>
    ) : data ? (
      <Slide direction="up" in={true}>
        <Paper elevation={0} sx={{ borderRadius: compact ? 2 : 3, overflow: 'hidden', background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)', border: '1px solid rgba(255,255,255,0.1)', position: 'relative' }}>
          <Box className="orb" sx={{ position: 'absolute', top: '-50px', right: '-50px', width: '200px', height: '200px', background: 'radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%)', borderRadius: '50%', filter: 'blur(40px)' }} />
          <CardContent sx={{ p: compact ? 2 : 3, position: 'relative', zIndex: 1 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={compact ? 1 : 2}>
              <Box>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', letterSpacing: '1px' }}>LIVE PREDICTION</Typography>
                <Typography variant={compact ? "body2" : "h6"} fontWeight={800} sx={{ color: 'white', mt: 0.5 }}>Stop {data.stop_id}</Typography>
              </Box>
              <NotificationsActiveIcon className="pulse-icon" sx={{ color: 'white', fontSize: compact ? 20 : 24 }} />
            </Box>

            <Paper elevation={0} sx={{ background: 'rgba(255,255,255,0.95)', p: compact ? 1.5 : 2.5, borderRadius: 2, textAlign: 'center', mb: compact ? 1.5 : 2, boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
              <Typography sx={{ fontWeight: 900, fontSize: compact ? '2rem' : '3.5rem', background: data.total_time_min > 10 ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)' : 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', lineHeight: 1, mb: 0.5 }}>
                {Math.round(data.total_time_min)}
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
                <Typography variant={compact ? "caption" : "body2"} fontWeight={700} sx={{ color: 'white' }}>Bus Delays</Typography>
              </Box>
              <Grid container spacing={compact ? 0.5 : 1}>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', bgcolor: 'rgba(0,0,0,0.2)', p: compact ? 0.8 : 1, borderRadius: 1.5 }}>
                    <TrafficIcon sx={{ color: '#f87171', fontSize: compact ? 14 : 18 }} />
                    <Typography variant={compact ? "caption" : "body2"} fontWeight={800} sx={{ color: 'white', display: 'block' }}>{Math.round(data.traffic_delay || 0)} min</Typography>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontSize: compact ? '0.6rem' : '0.7rem' }}>Traffic</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', bgcolor: 'rgba(0,0,0,0.2)', p: compact ? 0.8 : 1, borderRadius: 1.5 }}>
                    <ScheduleIcon sx={{ color: '#60a5fa', fontSize: compact ? 14 : 18 }} />
                    <Typography variant={compact ? "caption" : "body2"} fontWeight={800} sx={{ color: 'white', display: 'block' }}>{Math.round(data.dwell_delay || 0)} min</Typography>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontSize: compact ? '0.6rem' : '0.7rem' }}>Boarding</Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>

            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', bgcolor: 'rgba(255,255,255,0.1)', p: compact ? 1 : 1.5, borderRadius: 2, backdropFilter: 'blur(10px)' }}>
              <Typography variant={compact ? "caption" : "body2"} sx={{ color: 'white', fontWeight: 600 }}>Crowd</Typography>
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
              {!isXSmall && <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', display: 'block' }}>Route 72</Typography>}
            </Box>
          </Box>
          <IconButton onClick={fetchPrediction} size={isXSmall ? "small" : "medium"} sx={{ bgcolor: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.3)', '&:hover': { bgcolor: 'rgba(99, 102, 241, 0.2)' }, flexShrink: 0 }}>
            <RefreshIcon sx={{ color: '#6366f1', animation: refreshing ? 'rotate 1s linear infinite' : 'none', '@keyframes rotate': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } } }} />
          </IconButton>
        </Toolbar>
        {refreshing && <LinearProgress sx={{ bgcolor: 'rgba(99, 102, 241, 0.1)', height: 2 }} />}
      </AppBar>

      {/* MAIN CONTENT */}
      <Box sx={{ display: 'flex', flex: 1, width: '100%', gap: 0, overflow: 'hidden' }}>
        
        {/* DESKTOP/TABLET SIDEBAR - HIDDEN ON XSMALL MOBILE */}
        {!isMobile && (
          <Box sx={{ width: isTablet ? '45%' : '420px', height: '100%', overflowY: 'auto', background: 'linear-gradient(180deg, #0f172a 0%, #1e293b 100%)', borderRight: '1px solid rgba(99, 102, 241, 0.2)', p: isTablet ? 2 : 3, '&::-webkit-scrollbar': { width: '8px' }, '&::-webkit-scrollbar-track': { background: 'rgba(0,0,0,0.1)' }, '&::-webkit-scrollbar-thumb': { background: 'rgba(99, 102, 241, 0.5)', borderRadius: '4px' }, flexShrink: 0 }}>
            <Stack spacing={isTablet ? 2 : 2.5}>
              {/* STOP SELECTOR */}
              <Paper elevation={0} sx={{ p: isTablet ? 1.5 : 2, borderRadius: 2, background: 'rgba(30, 41, 59, 0.8)', border: '1px solid rgba(99, 102, 241, 0.2)', backdropFilter: 'blur(10px)' }}>
                <FormControl fullWidth size={isTablet ? "small" : "medium"}>
                  <InputLabel sx={{ color: 'rgba(255,255,255,0.7)' }}>Bus Stop</InputLabel>
                  <Select value={selectedStop} label="Bus Stop" onChange={handleStopChange} sx={{ borderRadius: 2, color: 'white', '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(99, 102, 241, 0.3)' }, '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(99, 102, 241, 0.5)' }, '& .MuiSvgIcon-root': { color: 'white' } }}>
                    <MenuItem value="BST-001">🚏 Temple Meads Station</MenuItem>
                    <MenuItem value="BST-002">🚏 Cabot Circus</MenuItem>
                  </Select>
                </FormControl>
              </Paper>

              {/* LOCATION INFO */}
              <Paper elevation={0} sx={{ p: isTablet ? 1.5 : 2, borderRadius: 2, background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(16, 185, 129, 0.1) 100%)', border: '1px solid rgba(34, 197, 94, 0.3)', backdropFilter: 'blur(10px)' }}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <NavigationIcon sx={{ color: '#22c55e', fontSize: isTablet ? 18 : 22 }} />
                  <Typography variant={isTablet ? "subtitle2" : "body2"} fontWeight={700} sx={{ color: 'white' }}>Your Location</Typography>
                </Box>
                <Box sx={{ fontFamily: 'monospace', fontSize: isTablet ? '0.7rem' : '0.8rem', color: 'rgba(255,255,255,0.8)', bgcolor: 'rgba(0,0,0,0.2)', p: isTablet ? 1 : 1.5, borderRadius: 2, mb: 1 }}>
                  <Box>📍 Temple Meads Station</Box>
                  <Box>Lat: {userLocation[0].toFixed(4)}</Box>
                  <Box>Lng: {userLocation[1].toFixed(4)}</Box>
                </Box>
                <Chip label="📍 Fixed Location" size="small" sx={{ bgcolor: 'rgba(0,0,0,0.3)', color: 'white', fontWeight: 600, fontSize: '0.65rem' }}/>
              </Paper>

              {/* PREDICTION CARD */}
              <PredictionCard compact={isTablet} />
            </Stack>
          </Box>
        )}

        {/* MAP - FULL WIDTH ON MOBILE, SHARED ON TABLET/DESKTOP */}
        <Box sx={{ flex: 1, height: '100%', position: 'relative', minWidth: 0, background: '#0a0e27', display: 'flex', flexDirection: 'column' }}>
          <MapContainer center={userLocation} zoom={15} style={{ height: "100%", width: "100%" }} zoomControl={!isXSmall}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap' />
            <RecenterMap center={userLocation} />
            <Marker position={userLocation} icon={userIcon}>
              <Popup>
                <Box sx={{ p: 1 }}>
                  <Typography variant="subtitle2" fontWeight={700}>📍 Temple Meads</Typography>
                  <Divider sx={{ my: 1 }} />
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>{userLocation[0].toFixed(4)}, {userLocation[1].toFixed(4)}</Typography>
                </Box>
              </Popup>
            </Marker>
            {busLocation && <Marker position={busLocation} icon={busIcon}>
              <Popup>
                <Box sx={{ p: 1 }}>
                  <Typography variant="subtitle2" fontWeight={700}>🚌 Bus 72</Typography>
                  <Divider sx={{ my: 1 }} />
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>{busLocation[0].toFixed(4)}, {busLocation[1].toFixed(4)}</Typography>
                </Box>
              </Popup>
            </Marker>}
            <Circle center={userLocation} radius={500} pathOptions={{ color: 'rgba(34, 197, 94, 0.3)', weight: 2, fillOpacity: 0.1 }} />
            {busLocation && <Circle center={busLocation} radius={300} pathOptions={{ color: 'rgba(99, 102, 241, 0.3)', weight: 2, fillOpacity: 0.1 }} />}
            {busLocation && <Polyline positions={[userLocation, busLocation]} pathOptions={{ color: '#6366f1', weight: 2, opacity: 0.6, dashArray: '5, 5' }} />}
          </MapContainer>

          {/* MOBILE BOTTOM SHEET - XSMALL ONLY */}
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
                  <Typography variant="body2" fontWeight={700} sx={{ color: 'white' }}>Prediction Details</Typography>
                  <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel sx={{ color: 'rgba(255,255,255,0.7)' }}>Stop</InputLabel>
                    <Select value={selectedStop} label="Stop" onChange={handleStopChange} sx={{ borderRadius: 1, color: 'white', '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(99, 102, 241, 0.3)' }, '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(99, 102, 241, 0.5)' }, '& .MuiSvgIcon-root': { color: 'white' } }}>
                      <MenuItem value="BST-001">🚏 Temple Meads</MenuItem>
                      <MenuItem value="BST-002">🚏 Cabot Circus</MenuItem>
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
