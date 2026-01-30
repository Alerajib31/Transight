"""
Transight Multi-Camera Launcher
Runs multiple CV counter instances simultaneously for different bus stops.
"""
import subprocess
import sys
from pathlib import Path

# Configuration: Map video files to bus stop IDs
CAMERA_CONFIGS = [
    {"stop_id": "STOP_001", "video": "1.mp4"},
    {"stop_id": "STOP_002", "video": "2.mp4"},
]

def main():
    print("🚀 Starting Transight Multi-Camera System...")
    print(f"📹 Monitoring {len(CAMERA_CONFIGS)} bus stops\n")
    
    processes = []
    script_path = Path(__file__).parent / "cv_counter.py"
    
    for config in CAMERA_CONFIGS:
        stop_id = config["stop_id"]
        video = config["video"]
        
        print(f"🟢 Launching camera for {stop_id} (Video: {video})")
        
        # Launch cv_counter.py as separate process
        cmd = [
            sys.executable,  # Python executable
            str(script_path),
            "--stop-id", stop_id,
            "--video", video
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            processes.append({
                "process": process,
                "stop_id": stop_id,
                "video": video
            })
        except Exception as e:
            print(f"❌ Failed to start {stop_id}: {e}")
    
    if not processes:
        print("❌ No camera processes started!")
        return
    
    print(f"\n✅ All {len(processes)} cameras running!")
    print("Press Ctrl+C to stop all cameras\n")
    
    try:
        # Monitor processes
        while True:
            for p_info in processes:
                process = p_info["process"]
                # Check if process has output
                if process.poll() is not None:
                    print(f"⚠ Camera {p_info['stop_id']} stopped unexpectedly")
                    stdout, stderr = process.communicate()
                    if stderr:
                        print(f"Error: {stderr}")
            
            import time
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping all cameras...")
        for p_info in processes:
            p_info["process"].terminate()
        
        print("✅ All cameras stopped. Goodbye!")


if __name__ == "__main__":
    main()
