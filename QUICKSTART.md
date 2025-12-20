# GradatumAI Quick Start Guide

## 🚀 Setup (5 minutes)

### 1. Install Dependencies
```powershell
# Minimum (just config + yaml):
pip install pyyaml

# OR Full setup (recommended):
pip install -r requirements.txt
```

**Note:** Full setup requires:
- OpenCV with SIFT (`opencv-contrib-python`)
- PyTorch + Detectron2 (large download ~2GB, CUDA recommended)
- SciPy, Matplotlib, scikit-video

### 2. Verify Installation
```powershell
cd GradatumAI-3-main
python -c "from config.config_loader import load_config; print('✓ Config setup OK')"
```

---

## 📁 Project Structure

```
GradatumAI-3-main/
├── config/
│   ├── __init__.py
│   ├── main_config.yaml          ← ALL PARAMETERS HERE (edit this, not code!)
│   └── config_loader.py          ← ConfigLoader class
├── Modules/
│   ├── IDrecognition/
│   │   ├── player_detection.py   ← Detectron2 player tracking
│   │   └── player.py             ← Player data model
│   ├── BallTracker/
│   │   └── ball_detect_track.py  ← Ball detection + tracking
│   ├── Match2D/
│   │   └── rectify_court.py      ← Court homography
│   ├── SpeedAcceleration/
│   │   └── velocity_analyzer.py  ← Speed calculation
│   └── [Other modules - not implemented yet]
├── resources/
│   ├── VideoProject.mp4          ← Input video
│   ├── Short4Mosaicing.mp4       ← Processing video
│   ├── ball/                     ← Ball templates
│   ├── snapshots/                ← Reference frames
│   ├── 2d_map.png               ← Court template
│   ├── pano.png                 ← Generated panorama (cached)
│   └── pano_enhanced.png        ← Enhanced panorama (cached)
├── tools/
│   ├── extract_videoframe.py
│   └── plot_tools.py
├── video_handler.py              ← Main pipeline orchestrator
├── main.py                       ← Entry point (loads config, runs pipeline)
├── requirements.txt              ← Dependencies
├── README.md                     ← (you should update this)
└── .github/
    └── copilot-instructions.md  ← AI agent guide
```

---

## 🎬 Running the System

### Full Pipeline
```powershell
python main.py
```

**What it does:**
1. Loads `config/main_config.yaml`
2. Generates court panorama from video (cached in `resources/pano.png`)
3. Initializes Detectron2 player detector
4. Initializes ball tracker
5. Processes video frame-by-frame
6. Outputs annotated frames + 2D court map

**First run:** Takes time (Detectron2 model download ~350MB, CUDA if available)

---

## 🛠️ Customization (No Code Changes!)

All parameters are in `config/main_config.yaml`:

### Change Input Video
```yaml
paths:
  video_primary: "my_basketball_video.mp4"
```

### Adjust Player Detection Threshold
```yaml
player_detection:
  model:
    score_threshold: 0.8  # was 0.7
```

### Change Processing Frame Range
```yaml
video:
  processing_range:
    start_frame: 0
    end_frame: 500  # was 230
```

### Tune Ball Tracking
```yaml
ball_detection:
  template_threshold: 0.75  # Lower = detect more balls
  max_track_frames: 7       # was 5
```

---

## 📊 Configuration Structure

```
config/main_config.yaml
├── paths               ← File locations
├── preprocessing       ← Video preprocessing
├── feature_matching    ← SIFT/homography
├── player_detection    ← Detectron2 + tracking
├── ball_detection      ← Ball template matching
├── court               ← Court dimensions
├── video               ← Frame ranges, FPS
├── velocity_analysis   ← Speed calculations
├── visualization       ← Output settings
└── logging            ← Debug options
```

**To understand each parameter:** See comments in `main_config.yaml`

---

## ⚠️ Common Issues

### "ModuleNotFoundError: No module named 'config'"
```powershell
# Make sure you're in the right directory:
cd GradatumAI-3-main
python main.py
```

### "No module named 'detectron2'"
```powershell
pip install torch torchvision detectron2
# This is large (~2GB), CUDA recommended for speed
```

### "No module named 'yaml'"
```powershell
pip install pyyaml
```

### Slow processing (2-5 FPS)
- Using CPU → Install CUDA + PyTorch with GPU support
- Change `ball_detection.tracker_types` to `["KCF"]` (faster than CSRT)

---

## 📝 Next Steps

After setup works:

### Phase 3 Options:
1. **Unit Testing** - `pytest` setup for validation
2. **Kalman Filter** - Better player occlusion handling
3. **DriblingDetector** - Complete unfinished modules
4. **YOLOv8** - Faster ball detection

See todo list in code for progress.

---

## 🔍 Debugging

Enable detailed logging:
```yaml
logging:
  level: "DEBUG"
  verbose_plots: true
```

Check homography quality:
```
resources/pano.png → Visual inspection
```

---

## 📚 Documentation

- **Architecture:** `.github/copilot-instructions.md`
- **Improvements Log:** `DOCUMENTATION_IMPROVEMENTS.md`
- **Phase 2 Summary:** This file (you're reading it!)
- **Config Details:** `config/main_config.yaml` (inline comments)

---

## ✅ Verification Checklist

- [ ] Python installed (`python --version`)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Config loads without error (`python -c "from config import load_config"`)
- [ ] Resources folder exists with videos
- [ ] Can run `python main.py` (test on 10 frames first)

Good luck! 🚀
