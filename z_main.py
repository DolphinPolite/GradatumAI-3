"""
Main.py - Pipeline Runner with Data Export
"""

import os
import cv2
import numpy as np

# Registry and Pipeline
from z_pipeline import create_pipeline_from_config
from z_registry import save_default_config
from z_export import create_exporter  # ✅ YENİ

# Existing utilities
from Modules.IDrecognition.player import Player
from Modules.IDrecognition.player_detection import FeetDetector, hsv2bgr, COLORS
from Modules.BallTracker.ball_detect_track import BallDetectTrack
from Modules.Match2D.rectify_court import *


def setup_court() -> tuple:
    """Setup court and panorama"""
    TOPCUT = 320
    
    if os.path.exists('resources/pano.png'):
        pano = cv2.imread("resources/pano.png")
    else:
        raise FileNotFoundError("resources/pano.png not found!")
    
    if os.path.exists('resources/pano_enhanced.png'):
        pano_enhanced = cv2.imread("resources/pano_enhanced.png")
    else:
        pano_enhanced = pano
    
    pano_enhanced = np.vstack((
        pano_enhanced,
        np.zeros((100, pano_enhanced.shape[1], pano_enhanced.shape[2]), dtype=pano.dtype)
    ))
    
    img = binarize_erode_dilate(pano_enhanced, plot=False)
    simplified_court, corners = rectangularize_court(img, plot=False)
    rectified = rectify(pano_enhanced, corners, plot=False)
    
    map_2d = cv2.imread("resources/2d_map.png")
    scale = rectified.shape[0] / map_2d.shape[0]
    map_2d = cv2.resize(map_2d, (int(scale * map_2d.shape[1]), int(scale * map_2d.shape[0])))
    map_2d = cv2.resize(map_2d, (rectified.shape[1], rectified.shape[0]))
    
    M1 = np.load("Rectify1.npy")
    
    return pano_enhanced, M1, map_2d


def setup_homography(pano_enhanced):
    """Setup SIFT homography matcher"""
    sift = cv2.xfeatures2d.SIFT_create()
    kp1, des1 = sift.compute(pano_enhanced, sift.detect(pano_enhanced))
    
    FLANN_INDEX_KDTREE = 1
    flann = cv2.FlannBasedMatcher(
        dict(algorithm=FLANN_INDEX_KDTREE, trees=5),
        dict(checks=50)
    )
    
    def get_homography(frame):
        kp2 = sift.detect(frame)
        kp2, des2 = sift.compute(frame, kp2)
        matches = flann.knnMatch(des1, des2, k=2)
        good = [m for m, n in matches if m.distance < 0.7 * n.distance]
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        M, _ = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
        return M
    
    return get_homography


def main():
    """Main runner with data export"""
    print("🏀 Basketball Analytics - Config-Driven Pipeline with Export")
    print("="*70)
    
    TOPCUT = 320
    VERBOSE = True
    MAX_FRAMES = 230
    EXPORT_DATA = True  # ✅ Export kontrolü
    
    # === SETUP ===
    pano_enhanced, M1, map_2d = setup_court()
    get_homography = setup_homography(pano_enhanced)
    
    # Players
    players = []
    for i in range(1, 6):
        players.append(Player(i, 'green', hsv2bgr(COLORS['green'][2])))
        players.append(Player(i, 'white', hsv2bgr(COLORS['white'][2])))
    players.append(Player(0, 'referee', hsv2bgr(COLORS['referee'][2])))
    
    # Detectors
    feet_detector = FeetDetector(players)
    ball_detector = BallDetectTrack(players)
    
    # Analyzers
    try:
        from Modules.SpeedAcceleration.velocity_analyzer import VelocityAnalyzer
        velocity_analyzer = VelocityAnalyzer(fps=30)
    except ImportError:
        velocity_analyzer = None
        print("⚠️  VelocityAnalyzer not found")
    
    try:
        from Modules.PlayerDistance.distance_analyzer import DistanceAnalyzer
        distance_analyzer = DistanceAnalyzer(pixel_to_meter=0.1)
    except ImportError:
        distance_analyzer = None
        print("⚠️  DistanceAnalyzer not found")
    
    # === CONFIG ===
    if not os.path.exists('pipeline_config.yaml'):
        print("\n📝 Creating default config...")
        save_default_config()
    
    # === PIPELINE ===
    pipeline = create_pipeline_from_config(
        config_path='pipeline_config.yaml',
        verbose=VERBOSE,
        feet_detector=feet_detector,
        ball_detector=ball_detector,
        velocity_analyzer=velocity_analyzer,
        distance_analyzer=distance_analyzer,
        player_list=players
    )
    
    print(f"\n📋 Pipeline Configuration:")
    print(f"   Modules: {len(pipeline.modules)}")
    for i, name in enumerate(pipeline.get_module_order(), 1):
        print(f"      {i}. {name}")
    
    is_valid, errors = pipeline.validate_pipeline()
    if not is_valid:
        print(f"\n❌ Pipeline validation failed:")
        for error in errors:
            print(f"   - {error}")
        return
    
    print(f"\n✅ Pipeline validated successfully")
    
    # === DATA EXPORTER ===
    exporter = None
    if EXPORT_DATA:
        exporter = create_exporter(output_dir="output")
        print(f"📊 Data export enabled")
    
    # === VIDEO PROCESSING ===
    video = cv2.VideoCapture("resources/Short4Mosaicing.mp4")
    if not video.isOpened():
        print("❌ Video not found!")
        return
    
    print(f"\n🎬 Processing video (0-{MAX_FRAMES} frames)...")
    if not VERBOSE:
        print("(Set VERBOSE=True for detailed logs)\n")
    
    frame_id = 0
    
    while video.isOpened() and frame_id <= MAX_FRAMES:
        ret, frame = video.read()
        if not ret:
            break
        
        if not VERBOSE and frame_id % 10 == 0:
            progress = int(100 * frame_id / MAX_FRAMES)
            print(f"\rProgress: {progress}% ({frame_id}/{MAX_FRAMES})", 
                  end='', flush=True)
        
        frame_cropped = frame[TOPCUT:, :]
        M = get_homography(frame_cropped)
        
        # Pipeline process
        frame_data = {
            'frame_id': frame_id,
            'timestamp': frame_id,
            'frame': frame_cropped.copy(),
            'map_2d': map_2d.copy(),
            'M': M,
            'M1': M1
        }
        
        result = pipeline.process_frame(frame_data)
        
        # ✅ COLLECT DATA FOR EXPORT
        if exporter:
            exporter.collect_frame(result)
        
        # Visualization
        if 'map_2d_text' in result:
            map_viz = result['map_2d_text']
        else:
            map_viz = result['map_2d']
        
        map_resized = cv2.resize(map_viz, 
                                 (result['frame'].shape[1], 
                                  result['frame'].shape[1]//2))
        vis = np.vstack((result['frame'], map_resized))
        
        cv2.imshow("Basketball Analytics", vis)
        if cv2.waitKey(1) & 0xff == 27:
            break
        
        frame_id += 1
    
    video.release()
    cv2.destroyAllWindows()
    
    # === STATISTICS ===
    pipeline.print_statistics()
    
    # ✅ EXPORT DATA
    if exporter:
        print("\n" + "="*70)
        exporter.print_summary()
        
        print("\n📊 Exporting data...")
        files = exporter.export_all()
        
        print(f"\n📁 Exported files:")
        print(f"   JSON: {files['json']}")
        print(f"   CSV: {len(files['csv'])} files")
        print(f"   Excel: {files['excel']}")
    
    print("\n✅ Processing complete!")


if __name__ == '__main__':
    main()
