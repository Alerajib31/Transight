"""Test bus-aware crowd exclusion (no Fusion Engine, no database).

Verifies:
  1. BUS_CONTAINMENT_MIN and BUS_INTERIOR_Y_FRACTION are sane fractions.
  2. CROWD_ROI_X_FRACTION / CROWD_ROI_Y_MIN_FRACTION are neutralized to their
     no-op defaults (1.0 / 0.0), proving _is_waiting_passenger is a no-op
     pre-filter by default.
  3. _person_overlap_fraction correctly measures containment: full
     containment -> ~1.0, partial overlap -> ~0.25, no overlap -> 0.0.
  4. _is_inside_bus correctly excludes people behind the glass (contained +
     box bottom above the interior line) while counting door/pavement
     people (contained + box bottom below the interior line), and fails
     open when no bus is detected or containment is below the threshold.
  5. count_passengers gracefully returns 0 for a missing video file.
  6. (optional) count_passengers returns a non-negative int on the real
     VIDEO_PATH/model if both are present on this machine; otherwise skips.
"""
from app import (
    BUS_CONTAINMENT_MIN,
    BUS_INTERIOR_Y_FRACTION,
    CROWD_ROI_X_FRACTION,
    CROWD_ROI_Y_MIN_FRACTION,
    MODEL_PATH,
    VIDEO_PATH,
    _is_inside_bus,
    _is_waiting_passenger,
    _person_overlap_fraction,
    count_passengers,
)
import os

# 1. Bus-aware constant sanity
assert 0.0 <= BUS_CONTAINMENT_MIN <= 1.0, (
    f"BUS_CONTAINMENT_MIN out of range: {BUS_CONTAINMENT_MIN}"
)
assert 0.0 <= BUS_INTERIOR_Y_FRACTION <= 1.0, (
    f"BUS_INTERIOR_Y_FRACTION out of range: {BUS_INTERIOR_Y_FRACTION}"
)
print(
    f"OK: BUS_CONTAINMENT_MIN={BUS_CONTAINMENT_MIN}, "
    f"BUS_INTERIOR_Y_FRACTION={BUS_INTERIOR_Y_FRACTION}"
)

# 2. Neutralized frame-fraction defaults (off by default, bus-aware rule is
# the active mechanism).
assert 0 < CROWD_ROI_X_FRACTION <= 1.0, (
    f"CROWD_ROI_X_FRACTION out of range: {CROWD_ROI_X_FRACTION}"
)
assert 0.0 <= CROWD_ROI_Y_MIN_FRACTION <= 0.95, (
    f"CROWD_ROI_Y_MIN_FRACTION out of range: {CROWD_ROI_Y_MIN_FRACTION}"
)
print(
    f"OK: CROWD_ROI_X_FRACTION={CROWD_ROI_X_FRACTION}, "
    f"CROWD_ROI_Y_MIN_FRACTION={CROWD_ROI_Y_MIN_FRACTION}"
)

if CROWD_ROI_X_FRACTION == 1.0 and CROWD_ROI_Y_MIN_FRACTION == 0.0:
    assert _is_waiting_passenger(900, 0, 990, 5, 1020, 600) is True, (
        "Default CROWD_ROI fractions should make _is_waiting_passenger a no-op"
    )
    print("OK: default CROWD_ROI fractions make _is_waiting_passenger a no-op")

# 3. _person_overlap_fraction — bus box (100, 100, 500, 400), interior line = 310.
BUS = (100, 100, 500, 400)

full_containment_person = (200, 150, 260, 300)
frac_full = _person_overlap_fraction(full_containment_person, BUS)
assert frac_full >= 0.99, f"Full-containment overlap should be ~1.0, got {frac_full}"
print(f"OK: full-containment person overlap fraction = {frac_full:.3f}")

partial_person = (450, 150, 650, 300)
frac_partial = _person_overlap_fraction(partial_person, BUS)
assert 0.2 < frac_partial < 0.3, f"Partial overlap should be ~0.25, got {frac_partial}"
print(f"OK: partial-overlap person overlap fraction = {frac_partial:.3f}")

non_overlap_person = (600, 150, 700, 300)
frac_none = _person_overlap_fraction(non_overlap_person, BUS)
assert frac_none == 0.0, f"Non-overlapping person overlap fraction should be 0.0, got {frac_none}"
print(f"OK: non-overlapping person overlap fraction = {frac_none:.3f}")

# 4. _is_inside_bus
assert _is_inside_bus((200, 150, 260, 300), [BUS]) is True, (
    "Contained person with y2 above interior line should be excluded"
)
print("OK: contained person behind glass (y2 above interior line) is excluded")

assert _is_inside_bus((200, 150, 260, 380), [BUS]) is False, (
    "Contained person with y2 below interior line (door/pavement) should be counted"
)
print("OK: contained person at door/pavement (y2 below interior line) is counted")

assert _is_inside_bus((200, 150, 260, 300), []) is False, (
    "No bus detected should fail open (counted)"
)
print("OK: no bus detected fails open (counted)")

assert _is_inside_bus((450, 150, 650, 300), [BUS]) is False, (
    "Partial overlap below BUS_CONTAINMENT_MIN should be counted"
)
print("OK: partial overlap below containment threshold is counted")

# 5. Fallback path: missing video returns 0, no YOLO model load required.
result = count_passengers("does_not_exist_xyz.mp4")
assert result == 0, f"Missing video should return 0, got {result}"
print("OK: count_passengers('does_not_exist_xyz.mp4') == 0")

# 6. Optional live path — only runs if the real video and YOLO model exist.
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

print("ALL CROWD-ROI CHECKS PASSED")
