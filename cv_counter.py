import sys
from pathlib import Path

import cv2 # type: ignore
from ultralytics import YOLO # type: ignore

# 1. Load the YOLOv8 Model (It will download 'yolov8n.pt' automatically first time)
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


# 2. Open the Video File
VIDEO_NAME = "2.mp4"
video_path = resolve_video_path(VIDEO_NAME)
print(f"Opening video: {video_path}")
cap = cv2.VideoCapture(str(video_path))

if not cap.isOpened():
    print(f"Error: Could not open video at {video_path}")
    sys.exit(1)

print("Starting Detection. Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break  # End of video

    # 3. Run YOLO detection on the frame
    # classes=0 tells YOLO to only look for 'person' (Class ID 0)
    results = model.track(frame, classes=[0], persist=True, verbose=False)

    # 4. Count people
    # The 'results' object contains all detection boxes
    detected_boxes = results[0].boxes
    people_count = len(detected_boxes)

    # 5. Draw the Count on the Video
    # Visual Polish: Draw a black box with white text
    cv2.rectangle(frame, (20, 20), (350, 80), (0, 0, 0), -1)
    cv2.putText(frame, f"WAITING: {people_count}", (30, 65), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

    # 6. Visualize results (Draws the green boxes around people)
    annotated_frame = results[0].plot()

    # Overlay our counter on top of the annotated frame
    cv2.rectangle(annotated_frame, (20, 20), (350, 80), (0, 0, 0), -1)
    cv2.putText(annotated_frame, f"WAITING: {people_count}", (30, 65), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

    # Show the video
    cv2.imshow("Transight - CV Module (Prototype)", annotated_frame)

    # Press 'q' to exit
    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()