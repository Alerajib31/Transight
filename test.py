"""
Transight — Standalone YOLOv8 Test Script
Run: python test.py

Displays YOLOv8 person detection on the bus_queue.mp4 video file.
Press ESC to exit.
"""

import os
import cv2
from ultralytics import YOLO

# Load YOLOv8 model (person detection) - downloads ~6MB on first run
model = YOLO("yolov8n.pt")

# Path to video file (project root)
VIDEO_PATH = os.path.join(os.path.dirname(__file__), "bus_queue.mp4")

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

    # Detect people (class 0 = person)
    results = model(frame, verbose=False)
    
    # Count and draw detections
    person_count = 0
    for r in results:
        for box in r.boxes:
            if int(box.cls[0]) == 0:  # class 0 = person
                person_count += 1
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

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
