# GradatumAI - Basketball Digital Twin System

[![Status](https://img.shields.io/badge/Status-Complete-brightgreen)](https://github.com/yourusername/GradatumAI)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)

## 🏀 Sistem Açıklaması

GradatumAI, basketbol oyunlarının **gerçek zamanlı takibi ve analizi** için gelişmiş bir bilgisayar görüş sistemidir. Oyuncu konumları, top hareketleri, oyun olayları ve performans metriklerini otomatik olarak tespit eder ve analiz eder.

## ✨ Öne Çıkan Özellikler

### 🎯 Temel Yetenekler
- **Oyuncu Tespiti** - Detectron2 ile gerçek zamanlı instance segmentation
- **Top Takibi** - Template matching ve Hough circles ile hassas takip
- **Saha Kalibrasyonu** - SIFT feature matching ile otomatik homography
- **Hız Analizi** - Oyuncu hızı ve ivmesi hesaplama

### 📊 Analiz Modülleri (Yeni!)
- **Ball Control** - Top kontrol ve sahipliği analizi
- **Dribbling Detection** - Dribling tespiti ve analizi
- **Event Recognition** - Pas, atış, rebound, turnover tespiti
- **Shot Analysis** - Atış türü ve zorluk derecesi
- **Distance Analysis** - Oyuncu mesafeleri ve yakınlığı
- **Sequence Recording** - Frame-by-frame veri kaydı ve export

## 🚀 Hızlı Başlangıç

### Kurulum

```bash
# 1. Repoyu klonla
git clone https://github.com/yourusername/GradatumAI.git
cd GradatumAI

# 2. Bağımlılıkları yükle
pip install -r requirements.txt

# 3. Detectron2'yi indir (İlk çalışmada otomatik)
# Veya manuel: https://github.com/facebookresearch/detectron2
```

### Temel Kullanım

```python
from integration_example import ComprehensiveBasketballAnalyzer

# Sistemi başlat
analyzer = ComprehensiveBasketballAnalyzer(
    config_path='config/main_config.yaml'
)

# Video'yu işle
import cv2
cap = cv2.VideoCapture('resources/VideoProject.mp4')

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    # Analiz yap
    analyzer.process_frame(
        frame, frame_number, 
        homography_matrix, M1_matrix,
        timestamp
    )

cap.release()

# Sonuçları al ve export et
summary = analyzer.get_analysis_summary()
analyzer.export_results('results/')
```

## 📁 Proje Yapısı

```
GradatumAI-3-main/
├── config/                          # Konfigürasyon
│   ├── main_config.yaml            # TÜM parametreler
│   └── config_loader.py            # Config yükleme
│
├── Modules/                         # Analiz modülleri
│   ├── IDrecognition/              # Oyuncu tespiti (Detectron2)
│   ├── BallTracker/                # Top takibi
│   ├── Match2D/                    # Saha homography
│   ├── SpeedAcceleration/          # Hız analizi
│   ├── BallControl/                # ✨ Ball control analizi
│   ├── DriblingDetector/           # ✨ Dribling tespiti
│   ├── EventRecognition/           # ✨ Oyun olayları
│   ├── ShotAttemp/                 # ✨ Atış analizi
│   ├── SequenceParser/             # ✨ Veri kaydı
│   └── PlayerDistance/             # ✨ Oyuncu mesafeleri
│
├── tests/                           # Unit testler
│   ├── test_config.py
│   ├── test_player.py
│   └── test_modules_integration.py ✨ Entegrasyon testleri
│
├── resources/                       # Veri dosyaları
│   ├── VideoProject.mp4            # Giriş video
│   ├── ball/                       # Top şablonları
│   └── snapshots/                  # Referans görüntüler
│
├── video_handler.py                # Ana pipeline orkestratörü
├── main.py                         # Entry point
├── integration_example.py          # ✨ Tam örnek
├── MODULES_COMPLETE.md             # ✨ Modül dokümantasyonu
└── requirements.txt                # Bağımlılıklar
```

## 📋 Modüller

### 1. Ball Control Analyzer
Oyuncu-top etkileşimini analiz eder.

```python
from Modules.BallControl import BallControlAnalyzer

analyzer = BallControlAnalyzer()
possession = analyzer.analyze_possession(
    ball_position=(10.5, 7.2),
    players={1: {'team': 'green', 'position': (10.8, 7.3)}, ...},
    frame=150,
    timestamp=5.0
)

print(f"Possessor: {possession.possessor_id}")
print(f"Type: {possession.possession_type.value}")
print(f"Confidence: {possession.possession_confidence:.2f}")
```

### 2. Dribbling Detector
Dribling eylemlerini tespit eder.

```python
from Modules.DriblingDetector import DribblingDetector

detector = DribblingDetector()
event = detector.detect_dribble(
    player_id=1,
    ball_positions=[...],
    ball_heights=[0.5, 0.8, 0.4, 0.7, ...],  # Zıplama
    frame_indices=[100, 101, 102, ...],
    timestamps=[...]
)

if event:
    print(f"Bounces: {event.num_bounces}")
    print(f"Duration: {event.duration_seconds:.2f}s")
```

### 3. Event Recognizer
Pas, atış, rebound gibi olayları tanır.

```python
from Modules.EventRecognition import EventRecognizer

recognizer = EventRecognizer()

# Pas tespiti
pass_event = recognizer.detect_pass(
    passer_id=1, passer_team='green',
    passer_pos=(10.0, 7.0),
    receiver_pos=(13.0, 6.5),
    receiver_id=2,
    ball_positions=[...],
    frame=150, timestamp=5.0
)

# Atış tespiti
shot_event = recognizer.detect_shot(
    player_id=3, team='green',
    ball_height_trajectory=[0.5, 1.0, 1.5, 2.0, 2.2, 2.0],
    ball_positions=[...],
    frame=200, timestamp=6.67
)

# İstatistikler
stats = recognizer.get_event_statistics()
# {'total_events': 42, 'passes': 25, 'shots': 8, ...}
```

### 4. Shot Analyzer
Atış detaylarını analiz eder (tür, zorluk, yörünge).

```python
from Modules.ShotAttemp import ShotAnalyzer

analyzer = ShotAnalyzer()
shot = analyzer.analyze_shot(
    player_id=4, team='green',
    ball_trajectory=[(x, y, z), ...],  # 3D yörünge
    frame=250, timestamp=8.33
)

if shot:
    print(f"Type: {shot.shot_type.value}")
    print(f"Difficulty: {shot.difficulty_rating:.2f}")
    print(f"Arc angle: {shot.arc_angle:.1f}°")
```

### 5. Distance Analyzer
Oyuncu mesafelerini ve yakınlığını hesaplar.

```python
from Modules.PlayerDistance import DistanceAnalyzer

analyzer = DistanceAnalyzer()
proximity = analyzer.analyze_proximity(
    player_id=1, player_team='green',
    player_position=(10.5, 7.2),
    all_players={...},
    frame_number=150
)

print(f"Closest teammate: {proximity.closest_teammate}")
print(f"Distance: {proximity.closest_teammate_distance:.2f}m")
```

### 6. Sequence Parser
Frame-by-frame veriyi kaydeder ve dışa aktarır.

```python
from Modules.SequenceParser import SequenceRecorder, SequenceParser

# Kaydı başlat
recorder = SequenceRecorder(fps=30)

for frame_num in range(num_frames):
    recorder.record_frame(
        frame_number=frame_num,
        timestamp=frame_num / 30.0,
        players={...},
        ball_position=(10.8, 7.1),
        ball_possessor_id=1,
        game_state='play'
    )

# Dışa aktar
parser = SequenceParser()
parser.export_to_csv(recorder.records, 'game.csv')
parser.export_to_json(recorder.records, 'game.json')
parser.export_to_numpy(recorder.records, 'game.npy')
```

## 🔧 Konfigürasyon

Tüm parametreler `config/main_config.yaml` dosyasında merkezi olarak yönetilir:

```yaml
# Ball Control
ball_control:
  proximity_threshold: 1.5
  ball_player_distance_threshold: 2.0

# Dribbling
dribbling:
  min_possession_frames: 5
  speed_threshold: 1.0
  height_variance_threshold: 5.0

# Event Recognition
event_recognition:
  pass_detection:
    min_pass_distance: 2.0
    max_pass_frames: 120

# Shot Analysis
shot_attempt:
  three_point_line_distance: 7.24
  hoop_position: [14.0, 7.5]

# Sequence Parser
sequence_parser:
  recording:
    storage_format: "csv"  # csv, json, numpy
    include_timestamps: true
    include_teams: true
```

Parametreleri kod değiştirmeden ayarla!

## 📊 Çıktılar

### CSV Export
```csv
frame_number,timestamp,player_1_team,player_1_x,player_1_y,...,ball_x,ball_y,ball_possessor_id,game_state
0,0.0,green,10.5,7.2,...,10.8,7.1,1,play
1,0.033,green,10.6,7.3,...,10.9,7.2,1,play
...
```

### JSON Export
```json
{
  "metadata": {
    "export_date": "2024-12-16",
    "total_frames": 1200,
    "format_version": "1.0"
  },
  "frames": [
    {
      "frame_number": 0,
      "timestamp": 0.0,
      "players": {
        "1": {"team": "green", "x": 10.5, "y": 7.2},
        "2": {"team": "white", "x": 12.0, "y": 8.0}
      },
      "ball": {"x": 10.8, "y": 7.1, "possessor_id": 1},
      "game_state": "play"
    }
  ]
}
```

### İstatistikler
```python
{
    'player_distance': {...},
    'dribbling': {
        'total_dribbles': 15,
        'avg_duration': 3.5,
        'avg_bounces': 6.2
    },
    'events': {
        'total_events': 42,
        'passes': 25,
        'shots': 8,
        'rebounds': 5
    },
    'shots': {
        'total_shots': 8,
        'fg_percentage': 37.5,
        'avg_difficulty': 0.65
    },
    'ball_control': {
        'total_possessions': 15,
        'avg_possession_duration': 3.5
    }
}
```

## 🧪 Testler

```bash
# Tüm testleri çalıştır
pytest tests/ -v

# Belirli modülü test et
pytest tests/test_modules_integration.py -v

# Coverage raporu
pytest tests/ --cov=Modules --cov-report=html
```

## 📈 Performans

| Modül | CPU | GPU | Açıklama |
|-------|-----|-----|---------|
| Player Detection | 5 FPS | 25 FPS | Detectron2 |
| Ball Tracking | 60 FPS | 60 FPS | Lightweight |
| Homography | 30 FPS | 30 FPS | SIFT matching |
| Analysis | 60+ FPS | 60+ FPS | Vektörizasyon |

**Not:** Gerçek FPS, video çözünürlüğüne ve donanıma bağlıdır.

## 💾 Sistem Gereksinimleri

- **Python:** 3.8+
- **RAM:** Minimum 8GB
- **GPU:** CUDA desteği opsiyonel (Detectron2 için)
- **İşlemci:** Multi-core önerilir

## 📦 Gerekenler

```
opencv-python>=4.5.0
detectron2  # PyTorch-based, CUDA önerilir
numpy>=1.19
scipy>=1.5
pandas>=1.1
pyyaml>=5.3
scikit-video>=1.1
```

## 📚 Dokümantasyon

- [MODULES_COMPLETE.md](MODULES_COMPLETE.md) - Detaylı modül dokümantasyonu
- [MODULES_COMPLETE_VISUAL.txt](MODULES_COMPLETE_VISUAL.txt) - Visual özet
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Uygulama özeti
- [integration_example.py](integration_example.py) - Çalışan örnek
- [TESTING.md](TESTING.md) - Test rehberi

## 🎯 Kullanım Örnekleri

### Örnek 1: Basit Analiz
```python
from integration_example import ComprehensiveBasketballAnalyzer

analyzer = ComprehensiveBasketballAnalyzer()
# ... frame processing ...
summary = analyzer.get_analysis_summary()
print(summary)
```

### Örnek 2: Özel Modül Kullanımı
```python
from Modules.EventRecognition import EventRecognizer

recognizer = EventRecognizer(min_pass_distance=3.0)
pass_events = recognizer.get_events_by_type(EventType.PASS)
print(f"Toplam pas: {len(pass_events)}")
```

### Örnek 3: Veri Export
```python
from Modules.SequenceParser import SequenceRecorder, SequenceParser

recorder = SequenceRecorder()
# ... recording ...

parser = SequenceParser()
parser.export_to_csv(recorder.records, 'game_data.csv')
parser.export_to_json(recorder.records, 'game_data.json')

stats = parser.get_sequence_statistics(recorder.records)
print(f"Toplam frame: {stats['total_frames']}")
print(f"Süre: {stats['duration_seconds']:.1f}s")
```

## 🐛 Sorun Giderme

### CUDA/GPU Sorunları
```python
# CPU'da çalıştır
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
```

### Detectron2 Download
```bash
# Manuel download
python -c "import detectron2; detectron2.model_zoo.get_checkpoint_url('COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml')"
```

### Video Okuma Sorunları
```bash
# Codec desteği kontrol et
ffprobe resources/VideoProject.mp4
```

## 🚀 İleri Konular

### Custom Thresholds
```python
analyzer = BallControlAnalyzer(
    proximity_threshold=2.0,  # Default: 1.5
    ball_player_distance_threshold=2.5  # Default: 2.0
)
```

### Batch Processing
```python
# Birden fazla video işle
videos = ['game1.mp4', 'game2.mp4', 'game3.mp4']
for video in videos:
    analyzer = ComprehensiveBasketballAnalyzer()
    # Process video
    analyzer.export_results(f'results/{video.stem}/')
```

### Custom Metrics
```python
from Modules.PlayerDistance import DistanceAnalyzer

analyzer = DistanceAnalyzer()
stats = analyzer.get_distance_statistics()

# Özel metrikler
avg_distance = np.mean([p[2] for p in analyzer.pairs])
print(f"Ort. oyuncu mesafesi: {avg_distance:.2f}m")
```


## 👨‍💻 Katkıda Bulun

1. Fork edin
2. Feature branch oluşturun (`git checkout -b feature/AmazingFeature`)
3. Değişiklikleri commit edin (`git commit -m 'Add AmazingFeature'`)
4. Branch'ı push edin (`git push origin feature/AmazingFeature`)
5. Pull Request açın

## 📞 İletişim

- **Email:** info@gradatum.ai
- **Web:** https://gradatum.ai
- **GitHub Issues:** https://github.com/yourusername/GradatumAI/issues

## 🙏 Teşekkürler

- Detectron2 - Facebook AI
- OpenCV - Intel
- SciPy ecosystem - Scientific computing

## 📊 Proje İstatistikleri

- **Toplam Modül:** 6 yeni + 4 temel = 10 tam
- **Kod Satırı:** ~2000 yeni
- **Sınıf:** 15+
- **Fonksiyon:** 40+
- **Test:** 28+ unit test
- **Dokümantasyon:** 100% coverage

---

**Status:** ✅ Production Ready  
**Last Updated:** 16 Aralık 2025  
**Version:** 3.0 (Complete)
