# Transight AI - Installation Guide

Complete setup instructions for running the Transight AI real-time bus tracking system.

---

## 📋 Prerequisites

| Software | Version | Purpose | Download Link |
|----------|---------|---------|---------------|
| **Python** | 3.11+ | Backend runtime | [python.org](https://python.org) |
| **Node.js** | 20+ | Frontend runtime | [nodejs.org](https://nodejs.org) |
| **PostgreSQL** | 15+ | Database | [postgresql.org](https://postgresql.org) |
| **ffmpeg** | Latest | Video processing | [ffmpeg.org](https://ffmpeg.org) |

### Windows Quick Install for Prerequisites

```powershell
# Using Chocolatey (recommended)
choco install python nodejs postgresql ffmpeg

# Or download installers manually from the links above
```

### macOS Quick Install

```bash
# Using Homebrew
brew install python node postgresql ffmpeg
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3 python3-pip nodejs postgresql postgresql-contrib ffmpeg
```

---

## 🚀 Step-by-Step Installation

### 1. Clone or Extract the Project

```bash
# If using git
git clone <repository-url> Transight2
cd Transight2

# Or extract the zip and navigate to the folder
cd c:\Users\rajib\Downloads\Transight2  # Windows example
```

### 2. Backend Setup

```bash
# Navigate to server directory
cd server

# Create Python virtual environment
py -3 -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Database Setup

Make sure PostgreSQL service is running, then:

```bash
# Create the database
py -3 setup_db.py

# Seed with Bristol Route 72 data (real stops from GTFS)
py -3 seed.py
```

> **Note**: This creates a database named `transight_db` with default credentials.

### 4. Frontend Setup

Open a **new terminal** and run:

```bash
# Navigate to client directory
cd client

# Install Node.js dependencies
npm install
```

---

## ▶️ Running the System

You need **3 terminals** (or services) running simultaneously:

### Terminal 1: PostgreSQL Database

Ensure PostgreSQL is running as a service:

```bash
# Windows (Run as Administrator)
net start postgresql-x64-15

# macOS
brew services start postgresql@15

# Linux
sudo service postgresql start
```

### Terminal 2: Flask Backend

```bash
cd server

# Activate virtual environment (if not already active)
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# Start the Flask server
py -3 app.py
```

You should see:
```
 * Running on http://localhost:5000
Fusion Engine: Starting fusion thread...
Fusion Engine started. Will run every 10 seconds.
```

### Terminal 3: React Frontend

```bash
cd client

# Start the development server
npm run dev
```

You should see:
```
  VITE v7.x.x  ready in xxx ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
```

---

## 🌐 Access the Application

Open your web browser and navigate to:

**http://localhost:3000**

The dashboard will load and display:
- Interactive map of Bristol with Route 72
- Live bus locations (updated every 10 seconds)
- ETA predictions for each bus
- Stop-by-stop arrival predictions

### Windows Shortcut

From the project root you can also run:

```powershell
.\start-dev.ps1
```

This opens separate backend and frontend PowerShell windows for you.

---

## 🔧 Alternative: Nix Setup (One Command)

If you have [Nix](https://nixos.org/) installed, use the provided Nix environment:

```bash
# In the project root directory
nix-shell dev.nix
```

This automatically:
- Installs Python 3.11, Node.js 20, PostgreSQL 15, and ffmpeg
- Creates and configures the PostgreSQL database
- Installs Python and Node.js dependencies
- Seeds the database with Route 72 data
- Starts both Flask and React dev servers

---

## 📁 Required Files

Ensure these files exist in your project root:

| File | Purpose | Auto-Download? |
|------|---------|----------------|
| `bus_queue.mp4` | Simulated camera feed for crowd detection | No - must exist |
| `itm_south_west_gtfs.zip` | Bristol bus timetable data | No - must exist |
| `yolov8n.pt` | YOLOv8 ML model for crowd detection | Yes - downloads on first run (~6MB) |

---

## ⚙️ Environment Variables (Optional)

Create a `.env` file in the project root to customize. The backend now auto-loads it:

```bash
# Database URL (default)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/transight_db

# API Keys (fallbacks are hardcoded)
BODS_API_KEY=your_bods_key_here
TOMTOM_API_KEY=your_tomtom_key_here
TOMTOM_ROUTING_KEY=your_tomtom_routing_key_here

# Video path (default)
VIDEO_PATH=bus_queue.mp4

# Fusion interval in seconds (default: 10)
FUSION_INTERVAL=10
```

---

## 🐛 Troubleshooting

### Common Issues and Solutions

| Issue | Error Message | Solution |
|-------|---------------|----------|
| **Python module not found** | `ModuleNotFoundError: No module named 'flask'` | Run `pip install -r requirements.txt` in the server directory with venv activated |
| **PostgreSQL connection failed** | `psycopg2.OperationalError: connection refused` | Ensure PostgreSQL service is running on port 5432 |
| **Port 5000 already in use** | `Address already in use` | Kill the process using port 5000: `lsof -ti:5000 \| xargs kill` (Mac/Linux) or `netstat -ano \| findstr :5000` then `taskkill /PID <PID> /F` (Windows) |
| **Port 3000 already in use** | `Port 3000 is already in use` | Change port in `client/vite.config.js` or kill the process |
| **ffmpeg not found** | `cv2.error: Could not open video` | Install ffmpeg and add to system PATH |
| **YOLO model download fails** | `FileNotFoundError: yolov8n.pt` | Manually download from [Ultralytics](https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt) and place in `server/` |
| **Database permission denied** | `psycopg2.OperationalError: FATAL: password authentication failed` | Check PostgreSQL credentials in `setup_db.py` or use default `postgres/postgres` |

### Checking What's Running

```bash
# Check if PostgreSQL is running
# Windows:
netstat -ano | findstr :5432
# macOS/Linux:
lsof -i :5432

# Check if Flask is running
curl http://localhost:5000/api/routes

# Check if React is running
curl http://localhost:3000
```

### Reset Everything

```bash
# Delete and recreate database
cd server
python setup_db.py  # Creates fresh database
python seed.py      # Reseeds with Route 72 data

# Reinstall Node modules
cd client
rm -rf node_modules  # or rmdir /s /q node_modules on Windows
npm install
```

---

## 📊 Verification Checklist

After installation, verify everything works:

- [ ] PostgreSQL service is running
- [ ] Flask server starts without errors on port 5000
- [ ] React dev server starts without errors on port 3000
- [ ] Browser loads http://localhost:3000 successfully
- [ ] Map displays Bristol with Route 72 stops
- [ ] API returns data: `curl http://localhost:5000/api/routes`
- [ ] YOLO model loads (check Flask console for download message)
- [ ] Fusion Engine logs show updates every 10 seconds

---

## 📝 Quick Reference Commands

```bash
# Full setup from scratch
git clone <repo-url> Transight2
cd Transight2

# Backend setup
cd server
python -m venv venv
venv\Scripts\activate  # or source venv/bin/activate
pip install -r requirements.txt
python setup_db.py
python seed.py

# Frontend setup
cd ../client
npm install

# Running (3 terminals)
# T1: Ensure PostgreSQL is running
# T2: cd server && venv\Scripts\activate && python app.py
# T3: cd client && npm run dev

# Access app at http://localhost:3000
```

---

## 💡 Tips

1. **Keep the virtual environment activated** when running Flask
2. **Don't close the terminals** - all 3 services must stay running
3. **First YOLO run** will download ~6MB model file automatically
4. **Video loop**: The `bus_queue.mp4` plays on loop for crowd simulation
5. **Database persists** between restarts, so bus history is saved

---

Need help? Check the main documentation in `README.md` and `SYSTEM_OVERVIEW.md`.
