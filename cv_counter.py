import sys
import argparse
import time
from pathlib import Path

import cv2 # type: ignore
from ultralytics import YOLO # type: ignore

# Try to import requests, but continue without it for debugging
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("⚠ Warning: 'requests' library not installed. Backend integration disabled.")
    print("  Install with: pip install requests")

# 1. Load the YOLOv8 Model
print("Loading AI Model...")
model = YOLO('yolov8n.pt')

# Backend API Configuration
BACKEND_URL = "http://localhost:8000/update-sensor-data"
UPDATE_INTERVAL = 5  # Send data to backend every 5 seconds
FRAME_SKIP = 2  # Process every Nth frame (reduces lag)
DISPLAY_WIDTH = 800  # Resize for display (doesn't affect detection)


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
    Adjust these thresholds based on your camera angle.
    """
    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    
    # Example ROI: Exclude right 40% of frame (where bus would be)
    # Adjust these values based on your actual video layout
    if center_x > frame_width * 0.6:  # Too far right (on bus)
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
        response = requests.post(BACKEND_URL, json=payload, timeout=2)
        if response.status_code == 200:
            print(f"✓ Sent to backend: Stop {stop_id} | Count: {crowd_count}")
        else:
            print(f"⚠ Backend error: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"✗ Backend connection failed: {e}")


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Transight CV Counter - Bus Stop Monitoring')
    parser.add_argument('--stop-id', required=True, help='Bus Stop ID (BODS atco_code, e.g., 01000053220')
    parser.add_argument('--video', required=True, help='Video filename (e.g., 1.mp4)')
    args = parser.parse_args()

    stop_id = args.stop_id
    video_name = args.video

    # Open the Video File
    video_path = resolve_video_path(video_name)
    print(f"📹 Opening video: {video_path}")
    print(f"🚏 Monitoring Bus Stop: {stop_id}")
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print(f"Error: Could not open video at {video_path}")
        sys.exit(1)

    print("Starting Detection. Press 'q' to quit.")

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
            send_to_backend(stop_id, waiting_people)
            last_update_time = current_time

        # Visualize results
        annotated_frame = results[0].plot()

        # Draw ROI boundary (optional - helps visualize the waiting area)
        roi_x = int(frame_width * 0.6)
        cv2.line(annotated_frame, (roi_x, 0), (roi_x, frame_height), (0, 0, 255), 2)
        cv2.putText(annotated_frame, "BUS AREA", (roi_x + 10, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Overlay counter and stop info
        cv2.rectangle(annotated_frame, (20, 20), (400, 120), (0, 0, 0), -1)
        cv2.putText(annotated_frame, f"Stop: {stop_id}", (30, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(annotated_frame, f"WAITING: {waiting_people}", (30, 95), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

        # Resize for display (doesn't affect detection)
        display_height = int(DISPLAY_WIDTH * frame_height / frame_width)
        display_frame = cv2.resize(annotated_frame, (DISPLAY_WIDTH, display_height))

        # Show the video
        cv2.imshow(f"Transight - {stop_id}", display_frame)

        # Press 'q' to exit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()