# Ball Tracker Wrapper Mimarisi - Dosya Yapısı

## 📁 Genel Yapı

```
ball_tracking/
├── ball_detect_track.py          # ORİJİNAL KOD (DEĞİŞMEZ)
├── wrappers/
│   ├── __init__.py
│   ├── robust_ball_tracker.py    # ANA WRAPPER
│   ├── validation_layer.py       # GİRİŞ/ÇIKIŞ DOĞRULAMA
│   ├── tracker_manager.py        # TRACKER YÖNETİMİ
│   ├── detection_enhancer.py     # TESPİT İYİLEŞTİRME
│   └── motion_predictor.py       # HAREKET TAHMİNİ
├── config/
│   └── tracker_config.yaml       # PARAMETRELERİN MERKEZİ
└── utils/
    ├── metrics.py                # PERFORMANS METRIKLERI
    └── logger.py                 # STRUCTURED LOGGING
```

---

## 🎯 1. `robust_ball_tracker.py` - Ana Wrapper
**Görev:** Orijinal sınıfı sarmalayıp tüm iyileştirmeleri orkestra eder

### Ne Yapar:
- `BallDetectTrack` sınıfını içerir ve metodlarını override eder
- Tüm alt modülleri koordine eder
- Hata yönetimini merkezi olarak ele alır
- Logging ve metrik toplama yapar

### Temel Yapı:
```python
class RobustBallTracker:
    def __init__(self, players, config_path='config/tracker_config.yaml'):
        self.original_tracker = BallDetectTrack(players)
        self.validator = ValidationLayer(config)
        self.tracker_manager = TrackerManager(config)
        self.detector = DetectionEnhancer(config)
        self.predictor = MotionPredictor(config)
        
    def ball_tracker(self, M, M1, frame, map_2d, map_2d_text, timestamp):
        # 1. Input validation
        # 2. Multi-tracker management
        # 3. Motion prediction for occlusion
        # 4. Fallback strategies
        # 5. Output validation
        # 6. Metrics logging
```

### Özellikler:
- ✅ Girdi doğrulama (None, boyut, tip kontrolü)
- ✅ Çoklu tracker yedekleme
- ✅ Oklüzyon sırasında hareket tahmini
- ✅ Otomatik parametre ayarlama
- ✅ Detaylı hata raporlama

---

## 🔍 2. `validation_layer.py` - Girdi/Çıktı Doğrulama
**Görev:** Tüm veri giriş/çıkışlarını kontrol eder, hatalı veriyi yakalar

### Ne Yapar:
```python
class ValidationLayer:
    @staticmethod
    def validate_frame(frame):
        """Frame: None değil, 3 kanal, min boyut kontrolü"""
        
    @staticmethod
    def validate_bbox(bbox, frame_shape):
        """Bbox: pozitif, frame içinde, mantıklı boyut"""
        
    @staticmethod
    def validate_homography(M):
        """Homografi: 3x3, singüler değil, determinant kontrolü"""
        
    @staticmethod
    def validate_players(players, timestamp):
        """Player: gerekli alanlar mevcut, timestamp var mı"""
        
    @staticmethod
    def sanitize_bbox(bbox, frame_shape):
        """Bbox'u frame sınırları içine kırp"""
```

### Yakaladığı Hatalar:
- ❌ Negatif veya sınır dışı bbox koordinatları
- ❌ None homografi matrisleri
- ❌ Boş veya bozuk frame'ler
- ❌ Eksik player pozisyonları
- ❌ Division by zero (bbox[2]=0, bbox[3]=0)

---

## 🎮 3. `tracker_manager.py` - Tracker Yönetimi
**Görev:** Çoklu tracker stratejisi, başarısızlıkta yedek tracker'a geçiş

### Ne Yapar:
```python
class TrackerManager:
    def __init__(self, config):
        self.trackers = {
            'primary': cv2.TrackerCSRT_create(),
            'backup1': cv2.TrackerKCF_create(),    # Hızlı hareketler için
            'backup2': cv2.TrackerMOSSE_create()   # Çok hızlı, düşük doğruluk
        }
        self.active_tracker = 'primary'
        self.failure_counts = defaultdict(int)
        
    def update(self, frame, last_bbox):
        """Aktif tracker başarısız olursa yedege geç"""
        
    def reinit_with_fallback(self, frame, bbox):
        """Tüm tracker'ları yeniden başlat"""
        
    def get_consensus(self, frame):
        """Çoklu tracker'dan konsensüs al (voting)"""
```

### Stratejiler:
- 🔄 **Primary-Backup Cascade:** CSRT → KCF → MOSSE
- 🗳️ **Voting System:** 3 tracker çalışır, ortanca bbox seçilir
- ⏱️ **Adaptive Timeout:** Başarısız tracker 10 frame sonra tekrar dener
- 🔁 **Auto-Reset:** Her 50 frame'de primary tracker'a dön

---

## 🎨 4. `detection_enhancer.py` - Tespit İyileştirme
**Görev:** Orijinal ball_detection'ı güçlendirir

### Ne Yapar:
```python
class DetectionEnhancer:
    def __init__(self, config):
        self.adaptive_threshold = AdaptiveThreshold()
        self.color_filter = ColorBasedFilter()
        self.size_validator = BallSizeValidator()
        
    def enhanced_detection(self, frame, context=None):
        """
        1. Dinamik threshold ayarlama
        2. Renk tabanlı ön filtreleme (beyaz top)
        3. Boyut tutarlılığı kontrolü
        4. Multi-scale detection
        """
        
    def filter_candidates(self, circles, frame):
        """Circle detection sonuçlarını filtrele"""
        # - Çok küçük/büyük daireleri at
        # - Renk histogramı ile top olmayan nesneleri ele
        # - Kenar bölgelerindeki tespit edilen nesneleri azalt
```

### İyileştirmeler:
- 📊 **Adaptive Threshold:** Video kalitesine göre 0.7-0.98 arası dinamik
- 🎨 **HSV Color Filter:** Beyaz top için HSV aralığı (0-180, 0-30, 180-255)
- 📏 **Size Consistency:** Önceki frame'e göre %50'den fazla boyut değişimi reddet
- 🔍 **Multi-Scale:** 3 farklı ölçekte circle detection (radius: 3-10, 8-15, 12-20)

---

## 🚀 5. `motion_predictor.py` - Hareket Tahmini
**Görev:** Oklüzyon sırasında top konumunu tahmin eder

### Ne Yapar:
```python
class MotionPredictor:
    def __init__(self, config):
        self.kf = KalmanFilter(dim_x=6, dim_z=2)  # x,y,vx,vy,ax,ay
        self.trajectory_buffer = deque(maxlen=30)
        
    def predict_position(self, current_bbox=None):
        """Kalman filtre ile bir sonraki pozisyonu tahmin et"""
        
    def update_trajectory(self, bbox):
        """Yeni gözlemi ekle, hız/ivme hesapla"""
        
    def validate_trajectory(self, new_bbox):
        """Yeni tespit fiziksel olarak mantıklı mı?"""
        # Max speed: 30 m/s → pixel/frame'e çevir
        # Max acceleration: 10 m/s²
        
    def get_search_region(self):
        """Tahmine dayalı arama bölgesi döndür"""
```

### Özellikler:
- 🎯 **Kalman Filter:** Pozisyon, hız, ivme tahmini
- 📈 **Trajectory Validation:** Fizik yasalarına uymayan sıçramaları reddet
- 🔎 **Adaptive Search Region:** Tahmin etrafında ROI oluştur (detection için)
- ⏮️ **Interpolation:** Kısa oklüzyonlarda (3-5 frame) pozisyonları interpolate et

---

## ⚙️ 6. `tracker_config.yaml` - Merkezi Konfigürasyon
**Görev:** Tüm parametreleri tek noktada toplar

```yaml
tracker:
  max_track_frames: 5
  ball_padding: 30
  
detection:
  template_threshold: 0.85  # Daha düşük (0.98'den)
  adaptive_threshold:
    enabled: true
    min: 0.70
    max: 0.95
  multi_scale_radii:
    - [3, 10]
    - [8, 15]
    - [12, 20]
  
validation:
  min_bbox_size: 10
  max_bbox_size: 100
  max_position_jump: 150  # pixel/frame
  max_velocity: 50.0      # pixel/frame
  
tracker_manager:
  strategy: "primary_backup"  # veya "voting"
  fallback_timeout: 10
  reset_interval: 50
  
motion_predictor:
  enabled: true
  buffer_size: 30
  max_occlusion_frames: 8
  interpolation_threshold: 5
  
logging:
  level: "INFO"
  log_metrics: true
  save_trajectories: true
```

---

## 📊 7. `utils/metrics.py` - Performans İzleme
**Görev:** Tracker performansını ölçer

```python
class TrackerMetrics:
    def __init__(self):
        self.detection_count = 0
        self.tracking_count = 0
        self.lost_track_count = 0
        self.avg_confidence = []
        
    def log_detection(self, method, confidence):
        """Tespit kaydı tut"""
        
    def log_tracking_failure(self, reason):
        """Başarısızlık nedeni"""
        
    def get_statistics(self):
        """Özet rapor döndür"""
        
    def export_trajectory(self, filename):
        """Top yörüngesini CSV'ye kaydet"""
```

---

## 📝 8. `utils/logger.py` - Yapılandırılmış Logging
```python
class BallTrackerLogger:
    def log_warning(self, message, context):
        """Uyarı logları (bbox sınır dışı, etc.)"""
        
    def log_error(self, exception, context):
        """Hata logları (stack trace ile)"""
        
    def log_metric(self, metric_name, value, timestamp):
        """Metrik logları"""
```

---

## 🔗 Kullanım Örneği

```python
from wrappers.robust_ball_tracker import RobustBallTracker

# Orijinal kod yerine wrapper kullan
tracker = RobustBallTracker(players, config_path='config/tracker_config.yaml')

# Aynı API, ama sağlam
frame, map_2d = tracker.ball_tracker(M, M1, frame, map_2d, map_2d_text, timestamp)

# Performans raporu
stats = tracker.get_statistics()
print(f"Detection rate: {stats['detection_rate']:.2%}")
print(f"Avg track length: {stats['avg_track_length']:.1f} frames")
```

---

## ✅ Toplam Dosya Sayısı: 8

1. ✅ `robust_ball_tracker.py` - Ana orkestrasyon
2. ✅ `validation_layer.py` - Veri doğrulama
3. ✅ `tracker_manager.py` - Çoklu tracker
4. ✅ `detection_enhancer.py` - Tespit iyileştirme
5. ✅ `motion_predictor.py` - Kalman filter
6. ✅ `tracker_config.yaml` - Parametre merkezi
7. ✅ `metrics.py` - Performans izleme
8. ✅ `logger.py` - Logging sistemi

---

## 🎯 Senin Durumuna Özel Çözümler

### ❌ Sabit kamera açısı yok
**Çözüm:** `motion_predictor.py`
- Homografi yerine frame-to-frame optik akış kullan
- Kalman filter ile göreli hareket tahmin et
- SIFT/ORB keypoint matching ile kamera hareketini kompanze et

### ❌ Hızlı hareketler
**Çözüm:** `tracker_manager.py`
- KCF/MOSSE tracker'ları ekle (CSRT yavaş)
- Geniş arama bölgesi (150-200 piksel)
- Frame skipping devre dışı (her frame işle)

---

## 🚀 Minimum Başlangıç (3 dosya)

Eğer hızlı başlamak istersen:

1. **`robust_ball_tracker.py`** - Temel wrapper + error handling
2. **`validation_layer.py`** - Bbox ve frame kontrolü
3. **`tracker_config.yaml`** - Parametreleri dışarı taşı

Bu 3 dosya ile %80 sağlamlık artışı sağlarsın. Diğerleri zamanla eklenebilir.




ball_tracking/
├── 1. config/tracker_config.yaml          # [~50 satır] Parametreler
├── 2. utils/logger.py                     # [~150 satır] Logging sistemi
├── 3. utils/metrics.py                    # [~200 satır] Performans metrikleri
├── 4. wrappers/validation_layer.py        # [~250 satır] Girdi/çıktı kontrolü
├── 5. wrappers/detection_enhancer.py      # [~300 satır] Tespit iyileştirme
├── 6. wrappers/motion_predictor.py        # [~350 satır] Kalman filter + sekme
├── 7. wrappers/tracker_manager.py         # [~400 satır] Multi-tracker yönetimi
└── 8. wrappers/robust_ball_tracker.py     # [~400 satır] Ana orchestrator