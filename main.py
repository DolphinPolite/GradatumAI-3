import os

from matplotlib import pyplot as plt
plt.switch_backend('Agg')  # Headless mode - GUI olmadan çalış

from Modules.BallTracker.ball_detect_track import BallDetectTrack
from Modules.IDrecognition.player import Player
from Modules.IDrecognition.player_detection import *
from Modules.Match2D.rectify_court import *
from video_handler import *



def get_frames(video_path, central_frame, mod):
    frames = []
    cap = cv2.VideoCapture(video_path)
    index = 0

    while cap.isOpened():
        ret, frame = cap.read()

        if (index % mod) == 0:
            frames.append(frame[TOPCUT:, :])

        if not ret or frame is None:
            cap.release()
            print("Released Video Resource")
            break

        if cv2.waitKey(20) == ord('q'): break
        index += 1

    cap.release()
    cv2.destroyAllWindows()

    print(f"Number of frames : {len(frames)}")
    plt.title(f"Centrale {frames[central_frame].shape}")
    plt.imshow(frames[central_frame])
    plt.show()

    return frames


#####################################################################
if __name__ == '__main__':
    # COURT REAL SIZES
    # 28m horizontal lines
    # 15m vertical lines

    # Check if required video files exist
    video_files = [
        'resources/VideoProject.mp4',
        'resources/Short4Mosaicing.mp4'
    ]
    
    missing_videos = [v for v in video_files if not os.path.exists(v)]
    if missing_videos:
        print(f"⚠️  Missing video files: {', '.join(missing_videos)}")
        print("📝 Usage:")
        print("   1. Place video files in resources/ directory")
        print("   2. Or modify video paths in main.py")
        print("   3. Create a sample video with: python scripts/create_dummy_jersey_model.py")
        # Continue anyway for testing - comment out if you want to exit
        print("\n⏸️  Skipping panorama creation - using existing resources if available...")

    # loading already computed panoramas
    if os.path.exists('resources/pano.png'):
        pano = cv2.imread("resources/pano.png")
    else:
        central_frame = 36
        frames = get_frames('resources/VideoProject.mp4', central_frame, mod=3)
        frames_flipped = [cv2.flip(frames[i], 1) for i in range(central_frame)]
        current_mosaic1 = collage(frames[central_frame:], direction=1)
        current_mosaic2 = collage(frames_flipped, direction=-1)
        pano = collage([cv2.flip(current_mosaic2, 1)[:, :-10], current_mosaic1])

        cv2.imwrite("resources/pano.png", pano)

    if os.path.exists('resources/pano_enhanced.png'):
        pano_enhanced = cv2.imread("resources/pano_enhanced.png")
        plt_plot(pano, "Panorama")
    else:
        pano_enhanced = pano
        for file in os.listdir("resources/snapshots/"):
            frame = cv2.imread("resources/snapshots/" + file)[TOPCUT:]
            pano_enhanced = add_frame(frame, pano, pano_enhanced, plot=False)
        cv2.imwrite("resources/pano_enhanced.png", pano_enhanced)

    ###################################
    pano_enhanced = np.vstack((pano_enhanced,
                               np.zeros((100, pano_enhanced.shape[1], pano_enhanced.shape[2]), dtype=pano.dtype)))
    img = binarize_erode_dilate(pano_enhanced, plot=False)
    simplified_court, corners = (rectangularize_court(img, plot=False))
    simplified_court = 255 - np.uint8(simplified_court)

    plt_plot(simplified_court, "Corner Detection", cmap="gray", additional_points=corners)

    rectified = rectify(pano_enhanced, corners, plot=False)

    # correspondences map-pano
    map = cv2.imread("resources/2d_map.png")
    scale = rectified.shape[0] / map.shape[0]
    map = cv2.resize(map, (int(scale * map.shape[1]), int(scale * map.shape[0])))
    resized = cv2.resize(rectified, (map.shape[1], map.shape[0]))
    map = cv2.resize(map, (rectified.shape[1], rectified.shape[0]))

    video = cv2.VideoCapture("resources/Short4Mosaicing.mp4")

    players = []
    for i in range(1, 6):
        players.append(Player(i, 'blue', hsv2bgr(COLORS['blue'][2])))
        players.append(Player(i, 'white', hsv2bgr(COLORS['white'][2])))
    players.append(Player(0, 'referee', hsv2bgr(COLORS['referee'][2])))

    feet_detector = FeetDetector(players)
    ball_detect_track = BallDetectTrack(players)
    video_handler = VideoHandler(pano_enhanced, video, ball_detect_track, feet_detector, map)
    video_handler.run_detectors()
