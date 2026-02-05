# --- CONFIGURATION ---
SENSOR_ID = "BST-001"  # Unique ID for this sensor (e.g., Temple Meads)
SERVER_URL = "http://localhost:8000/update-sensor-data"

import sys
import time
from pathlib import Path

import cv2  # type: ignore
from ultralytics import YOLO  # type: ignore

# Try to import requests, but continue without it for debugging
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("⚠ Warning: 'requests' library not installed. Backend integration disabled.")
    print("  Install with: pip install requests")

# Video configuration
VIDEO_QUIET = "crowd_quiet.mp4"
VIDEO_BUSY = "crowd_busy.mp4"

# Backend settings
UPDATE_INTERVAL = 5  # Send data to backend every 5 seconds
FRAME_SKIP = 2  # Process every Nth frame (reduces lag)
DISPLAY_WIDTH = 800  # Resize for display (doesn't affect detection)

# 1. Load the YOLOv8 Model
print("Loading AI Model...")
model = YOLO('yolov8n.pt')


def resolve_video_path(video_name: str) -> Path:
    """Return the first existing candidate path for the video."""
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / "videos" / video_name,  # expected location
        base_dir / video_name,              # same folder as script
        Path.cwd() / video_name,            # current working directory
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Video '{video_name}' not found. Checked: " + ", ".join(str(c) for c in candidates)
    )


def is_in_waiting_area(box, frame_height, frame_width):
    """
    Filter out people on the bus (bus driver).
    Assumes waiting area is the LEFT/BOTTOM portion of frame.
    """
    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    
    # Exclude right 40% of frame (where bus would be)
    if center_x > frame_width * 0.6:
        return False
    
    return True


def send_to_backend(stop_id: str, crowd_count: int):
    """Send sensor data to FastAPI backend."""
    if not HAS_REQUESTS:
        return
    
    try:
        payload = {
            "stop_id": stop_id,
            "crowd_count": crowd_count
        }
        response = requests.post(SERVER_URL, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Sent to backend: Stop {stop_id} | Count: {crowd_count} | Prediction: {data.get('predicted_delay_min', 'N/A')}min")
        else:
            print(f"⚠ Backend error: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"✗ Backend connection failed: {e}")


def main():
    # Start with quiet video
    current_video = VIDEO_QUIET
    video_path = resolve_video_path(current_video)
    
    print(f"📹 Sensor ID: {SENSOR_ID}")
    print(f"🎬 Starting with video: {current_video}")
    print("🔑 Press '1' for quiet scene, '2' for busy scene, 'q' to quit")
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: Could not open video at {video_path}")
        sys.exit(1)

    last_update_time = time.time()
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            # Loop video for continuous monitoring
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame_count += 1
        
        # Skip frames to reduce lag
        if frame_count % FRAME_SKIP != 0:
            continue

        frame_height, frame_width = frame.shape[:2]

        # Run YOLO detection (person class only)
        results = model.track(frame, classes=[0], persist=True, verbose=False)

        # Count people in waiting area (exclude bus driver)
        detected_boxes = results[0].boxes
        waiting_people = 0
        
        for box in detected_boxes:
            if is_in_waiting_area(box, frame_height, frame_width):
                waiting_people += 1

        # Send to backend every UPDATE_INTERVAL seconds
        current_time = time.time()
        if current_time - last_update_time >= UPDATE_INTERVAL:
            send_to_backend(SENSOR_ID, waiting_people)
            last_update_time = current_time

        # Visualize results
        annotated_frame = results[0].plot()

        # Draw ROI boundary
        roi_x = int(frame_width * 0.6)
        cv2.line(annotated_frame, (roi_x, 0), (roi_x, frame_height), (0, 0, 255), 2)
        cv2.putText(annotated_frame, "BUS AREA", (roi_x + 10, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Overlay counter and sensor info
        cv2.rectangle(annotated_frame, (20, 20), (450, 140), (0, 0, 0), -1)
        cv2.putText(annotated_frame, f"Sensor: {SENSOR_ID}", (30, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(annotated_frame, f"Video: {current_video}", (30, 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(annotated_frame, f"WAITING: {waiting_people}", (30, 120), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)

        # Instructions
        cv2.putText(annotated_frame, "[1]Quiet [2]Busy [Q]Quit", (frame_width - 300, frame_height - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # Resize for display
        display_height = int(DISPLAY_WIDTH * frame_height / frame_width)
        display_frame = cv2.resize(annotated_frame, (DISPLAY_WIDTH, display_height))

        # Show the video
        cv2.imshow(f"Transight Vision Node - {SENSOR_ID}", display_frame)

        # Handle key presses
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('1'):
            if current_video != VIDEO_QUIET:
                current_video = VIDEO_QUIET
                cap.release()
                video_path = resolve_video_path(current_video)
                cap = cv2.VideoCapture(str(video_path))
                print(f"🎬 Switched to: {current_video}")
        elif key == ord('2'):
            if current_video != VIDEO_BUSY:
                current_video = VIDEO_BUSY
                cap.release()
                video_path = resolve_video_path(current_video)
                cap = cv2.VideoCapture(str(video_path))
                print(f"🎬 Switched to: {current_video}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
