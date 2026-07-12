"""Test crowd left-ROI + ground-line filter (no Fusion Engine, no database).

Verifies:
  1. CROWD_ROI_X_FRACTION is a sane fraction of frame width.
  2. _center_in_left_roi correctly includes/excludes detections by
     horizontal center position, and fails open when frame_width is unknown.
  3. count_passengers gracefully returns 0 for a missing video file.
  4. (optional) count_passengers returns a non-negative int on the real
     VIDEO_PATH/model if both are present on this machine; otherwise skips.
  5. CROWD_ROI_Y_MIN_FRACTION and _is_waiting_passenger correctly exclude
     in-bus (window-level) detections while keeping pavement detections,
     and fail open per-dimension when frame_width/frame_height is unknown.
"""
from app import (
    CROWD_ROI_X_FRACTION,
    CROWD_ROI_Y_MIN_FRACTION,
    MODEL_PATH,
    VIDEO_PATH,
    _center_in_left_roi,
    _is_waiting_passenger,
    count_passengers,
)
import os

FRAME_WIDTH = 1000
boundary_x = FRAME_WIDTH * CROWD_ROI_X_FRACTION

# 1. Constant sanity
assert 0 < CROWD_ROI_X_FRACTION <= 1.0, (
    f"CROWD_ROI_X_FRACTION out of range: {CROWD_ROI_X_FRACTION}"
)
print(f"OK: CROWD_ROI_X_FRACTION={CROWD_ROI_X_FRACTION} (boundary x={boundary_x:.1f}px of {FRAME_WIDTH}px)")

# 2. Deterministic ROI-filter logic (no YOLO/video needed)
# Box centered at ~10% width -> inside left ROI (counted).
assert _center_in_left_roi(80, 120, FRAME_WIDTH) is True, "Left-side box should be counted"
print("OK: left-side box (center ~10%) is counted")

# Box centered at ~90% width -> outside left ROI (excluded), unless the
# fraction has been overridden to be very permissive.
right_center = (880 + 920) / 2.0
expected_right = right_center <= boundary_x
assert _center_in_left_roi(880, 920, FRAME_WIDTH) is expected_right, "Right-side box result mismatch"
print(f"OK: right-side box (center ~90%) -> {expected_right} (matches CROWD_ROI_X_FRACTION)")

# Box straddling the boundary but centered just left of it.
straddle_center = (400 + 560) / 2.0  # 480
expected_straddle = straddle_center <= boundary_x
assert _center_in_left_roi(400, 560, FRAME_WIDTH) is expected_straddle, "Straddling box result mismatch"
print(f"OK: straddling box (center=480) -> {expected_straddle} (matches CROWD_ROI_X_FRACTION)")

# frame_width <= 0 -> fail open (True), preserves count when width unknown.
assert _center_in_left_roi(0, 100, 0) is True, "Unknown frame width should fail open (True)"
assert _center_in_left_roi(0, 100, -1) is True, "Negative frame width should fail open (True)"
print("OK: unknown/invalid frame_width fails open (count preserved)")

# 3. Fallback path: missing video returns 0, no YOLO model load required.
result = count_passengers("does_not_exist_xyz.mp4")
assert result == 0, f"Missing video should return 0, got {result}"
print("OK: count_passengers('does_not_exist_xyz.mp4') == 0")

# 4. Optional live path — only runs if the real video and YOLO model exist.
if os.path.exists(VIDEO_PATH) and os.path.exists(MODEL_PATH):
    try:
        live_count = count_passengers(VIDEO_PATH)
        assert isinstance(live_count, int) and live_count >= 0, (
            f"count_passengers should return a non-negative int, got {live_count!r}"
        )
        print(f"OK: live count_passengers(VIDEO_PATH) returned {live_count}")
    except (ImportError, OSError) as exc:
        print(f"SKIP: live video/model present but call raised {type(exc).__name__}: {exc}")
else:
    print(f"SKIP: live video/model not both present (VIDEO_PATH={VIDEO_PATH}, MODEL_PATH={MODEL_PATH})")

# 5. Ground-line vertical filter (_is_waiting_passenger). Uses FRAME_WIDTH=1020,
# FRAME_HEIGHT=600 to match test.py's resized frame dimensions.
GL_FRAME_WIDTH = 1020
GL_FRAME_HEIGHT = 600

# 5a. Constant sanity
assert 0.0 <= CROWD_ROI_Y_MIN_FRACTION <= 0.95, (
    f"CROWD_ROI_Y_MIN_FRACTION out of range: {CROWD_ROI_Y_MIN_FRACTION}"
)
print(f"OK: CROWD_ROI_Y_MIN_FRACTION={CROWD_ROI_Y_MIN_FRACTION} (ground line y={GL_FRAME_HEIGHT * CROWD_ROI_Y_MIN_FRACTION:.1f}px of {GL_FRAME_HEIGHT}px)")

# 5b. In-bus-style detection: center in left ROI but box bottom (y2) cut off
# at the window sill (~0.46 of height) -> excluded.
assert _is_waiting_passenger(150, 200, 240, 276, GL_FRAME_WIDTH, GL_FRAME_HEIGHT) is False, (
    "In-bus detection (window-level y2) should be excluded"
)
print("OK: in-bus detection (left ROI, y2~0.46 height) is excluded")

# 5c. Pavement detection: center in left ROI, box bottom (y2) reaches the
# ground line (~0.8 of height) -> counted.
assert _is_waiting_passenger(150, 300, 240, 480, GL_FRAME_WIDTH, GL_FRAME_HEIGHT) is True, (
    "Pavement detection (left ROI, y2~0.8 height) should be counted"
)
print("OK: pavement detection (left ROI, y2~0.8 height) is counted")

# 5d. Right-side pavement detection: fails the x-check regardless of y2.
assert _is_waiting_passenger(900, 300, 990, 480, GL_FRAME_WIDTH, GL_FRAME_HEIGHT) is False, (
    "Right-side detection should be excluded by the x-check"
)
print("OK: right-side pavement detection (center ~90% width) is excluded by x-check")

# 5e. Fail-open on unknown height: left-ROI center, height unknown -> y-check
# skipped, so the detection is counted regardless of y2.
assert _is_waiting_passenger(150, 0, 240, 10, GL_FRAME_WIDTH, 0) is True, (
    "Unknown frame_height should fail open (y-check skipped)"
)
print("OK: unknown frame_height fails open (y-check skipped, count preserved)")

# 5f. Fail-open on unknown width: width unknown -> x-check skipped; y2=590
# still passes the ground line, so the combined result is True.
assert _is_waiting_passenger(0, 0, 10, 590, 0, GL_FRAME_HEIGHT) is True, (
    "Unknown frame_width should fail open (x-check skipped)"
)
print("OK: unknown frame_width fails open (x-check skipped, count preserved)")

print("ALL CROWD-ROI CHECKS PASSED")
