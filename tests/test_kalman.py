from Modules.IDrecognition.kalman import KalmanTracker


def test_kalman_linear_motion():
    # Simulate a player moving +1 in x each step starting at (0,0)
    k = KalmanTracker(initial_pos=(0.0, 0.0), dt=1.0)

    measurements = [(1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
    predictions = []

    for m in measurements:
        k.predict()
        pos = k.update(m)
        predictions.append(pos)

    # After consecutive linear measurements, state should track near measurements
    assert abs(predictions[-1][0] - 3.0) < 0.5
    assert abs(predictions[-1][1] - 0.0) < 0.5
