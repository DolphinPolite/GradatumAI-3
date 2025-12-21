import math


def dynamic_iou_threshold(prev_bb, det_bb, last_pos=None, curr_pos=None, base=0.2, max_speed_px=50):
    """Compute an adaptive IoU threshold based on apparent motion and size change.

    - If object moved quickly (large pixel distance), lower the threshold (allow smaller overlap).
    - If bbox areas differ a lot, scale threshold accordingly.
    Returns a threshold in (0.05, 1.0).
    """
    try:
        # area ratio
        a_prev = max(1.0, float((prev_bb[2] - prev_bb[0] + 1) * (prev_bb[3] - prev_bb[1] + 1)))
        a_det = max(1.0, float((det_bb[2] - det_bb[0] + 1) * (det_bb[3] - det_bb[1] + 1)))
        area_ratio = math.sqrt(a_det / a_prev)
    except Exception:
        area_ratio = 1.0

    # speed factor
    speed = 0.0
    if last_pos is not None and curr_pos is not None:
        try:
            speed = math.hypot(curr_pos[0] - last_pos[0], curr_pos[1] - last_pos[1])
        except Exception:
            speed = 0.0

    speed_ratio = min(1.0, speed / float(max_speed_px))

    # area_scale: if area grows, allow slightly higher threshold; if shrinks, lower
    area_scale = max(0.6, min(1.4, area_ratio))

    # speed_scale: faster -> reduce threshold down to 40%
    speed_scale = 1.0 - (0.6 * speed_ratio)

    th = base * area_scale * speed_scale
    th = max(0.05, min(1.0, th))
    return th


def test_iou_threshold_reduces_with_speed():
    prev_bb = (0, 0, 100, 50)
    det_bb = (2, 1, 102, 51)
    last_pos = (10, 10)
    curr_pos_slow = (12, 11)
    curr_pos_fast = (60, 50)

    th_slow = dynamic_iou_threshold(prev_bb, det_bb, last_pos, curr_pos_slow, base=0.2, max_speed_px=50)
    th_fast = dynamic_iou_threshold(prev_bb, det_bb, last_pos, curr_pos_fast, base=0.2, max_speed_px=50)

    assert th_fast < th_slow
