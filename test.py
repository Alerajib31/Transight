"""
Transight — Standalone YOLOv8 Test Script
Run: python test.py

Displays YOLOv8 person detection on the bus_queue.mp4 video file.
Press ESC to exit.
"""

import os
import cv2
from ultralytics import YOLO

BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "server", "yolov8n.pt")

# Path to video file (project root)
VIDEO_PATH = os.path.join(BASE_DIR, "bus_queue.mp4")

# Filter fractions mirror server/app.py (CROWD_ROI_X_FRACTION,
# CROWD_ROI_Y_MIN_FRACTION). Kept as a local copy so this demo stays
# standalone. Frame is resized to 1020x600 below, so fractions are
# measured against those resized dimensions.
CROWD_ROI_X_FRACTION = 0.5
CROWD_ROI_Y_MIN_FRACTION = 0.6


def is_waiting_passenger(x1, y1, x2, y2, frame_width, frame_height):
    """Local copy of server/app.py::_is_waiting_passenger for the demo."""
    if frame_width > 0:
        center_x = (x1 + x2) / 2.0
        if center_x > frame_width * CROWD_ROI_X_FRACTION:
            return False
    if frame_height > 0 and y2 < frame_height * CROWD_ROI_Y_MIN_FRACTION:
        return False
    return True


# Load the same canonical YOLOv8 model file used by the backend.
model = YOLO(MODEL_PATH)

# Open video file
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"Error: Could not open video at {VIDEO_PATH}")
    exit(1)

print("YOLOv8 Test started. Press ESC to exit.")

frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        # Loop video
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame_count += 1
    # Process every 2nd frame for performance
    if frame_count % 2 != 0:
        continue

    frame = cv2.resize(frame, (1020, 600))
    frame_height, frame_width = frame.shape[:2]

    # Detect people (class 0 = person)
    results = model(frame, verbose=False)

    # Count and draw detections: green = counted waiting passenger,
    # red = excluded (e.g. in-bus detection or right-side/bus body).
    person_count = 0
    for r in results:
        for box in r.boxes:
            if int(box.cls[0]) == 0:  # class 0 = person
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                if is_waiting_passenger(x1, y1, x2, y2, frame_width, frame_height):
                    person_count += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                else:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

    # Display count
    cv2.putText(frame, f"Persons: {person_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("YOLOv8 Person Detection", frame)

    # Exit on ESC (wait 1ms for smooth playback)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
print(f"Test completed. Total frames processed: {frame_count}")
