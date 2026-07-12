"""
Transight — Standalone YOLOv8 Test Script
Run: python test.py

Displays YOLOv8 bus-aware passenger detection on the bus_queue.mp4 video
file. Bus boxes are drawn blue, counted people green, excluded (in-bus)
people red. Press ESC to exit.
"""

import os
import cv2
from ultralytics import YOLO

BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "server", "yolov8n.pt")

# Path to video file (project root)
VIDEO_PATH = os.path.join(BASE_DIR, "bus_queue.mp4")

# Bus-aware exclusion constants mirror server/app.py (BUS_CONTAINMENT_MIN,
# BUS_INTERIOR_Y_FRACTION). Kept as a local copy so this demo stays
# standalone. Frame is resized to 1020x600 below, so boxes are measured
# against those resized dimensions.
BUS_CONTAINMENT_MIN = 0.85
BUS_INTERIOR_Y_FRACTION = 0.7


def overlap_frac(p, b):
    """Local copy of server/app.py::_person_overlap_fraction for the demo."""
    px1, py1, px2, py2 = p
    bx1, by1, bx2, by2 = b
    ix = max(0, min(px2, bx2) - max(px1, bx1))
    iy = max(0, min(py2, by2) - max(py1, by1))
    pa = max(1, (px2 - px1) * (py2 - py1))
    return (ix * iy) / pa


def inside_bus(p, buses):
    """Local copy of server/app.py::_is_inside_bus for the demo."""
    for b in buses:
        if overlap_frac(p, b) >= BUS_CONTAINMENT_MIN:
            interior_line = b[1] + BUS_INTERIOR_Y_FRACTION * (b[3] - b[1])
            if p[3] < interior_line:
                return True
    return False


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

    # Detect people (class 0) and buses (class 5) in one pass.
    results = model(frame, verbose=False)

    persons = []
    bus_boxes = []
    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            xy = tuple(map(int, box.xyxy[0]))
            if cls == 0:  # class 0 = person
                persons.append(xy)
            elif cls == 5:  # class 5 = bus
                bus_boxes.append(xy)

    # Draw every bus box in blue.
    for bx1, by1, bx2, by2 in bus_boxes:
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), (255, 0, 0), 2)

    # Count and draw people: green = counted waiting passenger,
    # red = excluded (contained in a bus box, above the interior line).
    person_count = 0
    for x1, y1, x2, y2 in persons:
        if not inside_bus((x1, y1, x2, y2), bus_boxes):
            person_count += 1
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        else:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

    # Display count (counted only).
    cv2.putText(frame, f"Persons: {person_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("YOLOv8 Person Detection", frame)

    # Exit on ESC (wait 1ms for smooth playback)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
print(f"Test completed. Total frames processed: {frame_count}")
