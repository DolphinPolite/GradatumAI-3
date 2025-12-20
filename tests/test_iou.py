from Modules.IDrecognition.player_detection import dynamic_iou_threshold


def test_iou_threshold_reduces_with_speed():
    prev_bb = (0, 0, 100, 50)
    det_bb = (2, 1, 102, 51)
    last_pos = (10, 10)
    curr_pos_slow = (12, 11)
    curr_pos_fast = (60, 50)

    th_slow = dynamic_iou_threshold(prev_bb, det_bb, last_pos, curr_pos_slow, base=0.2, max_speed_px=50)
    th_fast = dynamic_iou_threshold(prev_bb, det_bb, last_pos, curr_pos_fast, base=0.2, max_speed_px=50)

    assert th_fast < th_slow
