"""
## Modülün Amacı
Bu modül futbol maçı analizi için oyuncu takibi yapıyor. Temel mantık:
Video → Output:

Video frame'lerinden oyuncuları segmente ediyor (Detectron2 kullanarak)
Oyuncuların forma renklerine göre takımlarını belirliyor (yeşil=Nijerya, beyaz=ABD, siyah=hakem)
Oyuncuların ayak pozisyonlarını tespit edip 2D sahaya (kuşbakışı görünüm) projeksiyon yapıyor
Her oyuncuyu zaman içinde takip ediyor (IoU bazlı tracking)

Sınırlamalar:

Sadece renk bazlı takım tespiti (benzer renk giyen takımlarda sorun çıkar)
Statik renk eşikleri (ışık değişimlerine duyarlı)
IoU threshold'a bağımlı tracking (hızlı hareketlerde kayıp olabilir)
7 frame görünmezse oyuncu kayboluyor
Referansları takip ediyor ama kullanmıyor


## Input / Output Contract
Input:

M, M1: Homografi matrisleri (perspektif → 2D saha dönüşümü için)
frame: OpenCV BGR formatında video frame (numpy array)
timestamp: Frame numarası/zaman damgası (int)
map_2d: 2D saha görüntüsü (numpy array, BGR)
self.players: Player objeleri listesi (her oyuncunun ID, team, color, positions, previous_bb özellikleri var)

Output:
Tuple olarak 3 eleman döndürüyor:

frame: Üzerine oyuncu işaretleri çizilmiş orijinal frame
map_2d: Oyuncu pozisyonlarıyla güncellenmiş 2D saha
map_2d_text: Oyuncu ID'leri yazılmış 2D saha versiyonu

Veri Formatları:

bbox: (top, left, bottom, right) tuple
positions: Dict {timestamp: (x, y)}
color: BGR tuple (B, G, R)
team: String key ('green', 'white', 'referee')


## Veri Flow'u Çıkarımı
Pipeline'daki Yeri:
Bu modül tracker görevi görüyor:

Öncesinde: Video frame'leri ve homografi matrisleri hazır olmalı
Sonrasında: Player pozisyonları başka modüllere gidiyor (muhtemelen top takibi, hız analizi, ısı haritası vb.)

Alınan Veriler:

Homografi matrisleri (başka bir modülden - muhtemelen saha tespiti modülü)
Video frame'leri (ana video processing pipeline'dan)
Player objeleri (merkezi bir koordinatör tarafından başlatılmış olmalı)

Sağlanan Veriler:

Player.positions güncelleniyor → Muhtemelen analytics/visualization modüllerine gidiyor
Annotated frame'ler → Video output veya canlı görselleştirme için
2D saha haritaları → Taktik analiz veya overlay için


## Eksikler ve Açık Noktalar
Hataya Açık Noktalar:

Renk tespiti kırılgan: Işık değişiminde, gölgelerde, benzer renklerde başarısız olur
7 frame kayıp = oyuncu sıfırlanıyor: Kısa occlusion'larda bile ID kaybı
IoU threshold sabit (0.2): Farklı senaryolar için adaptif olmalı
Çakışan oyuncularda sorun: Segmentasyon çakışmayı çözemez
Hakem tracking gereksiz: Takip ediliyor ama kullanılmıyor

İyileştirmeler:

Renk tespiti → Deep learning: Forma tanıma modeli kullanılabilir
IoU → DeepSORT/ByteTrack: Daha robust tracking algoritmaları
Occlusion handling: Kalman filter ile pozisyon tahmini
Adaptive thresholds: Maç durumuna göre parametreler değişebilir
Re-identification: Kayıp oyuncuyu yeniden bulma mekanizması

Dışarıdan Eklenebilecek Modüller:

YOLOv8/YOLOX: Daha hızlı person detection
DeepSORT/StrongSORT: ID koruyucu tracking
ByteTrack: Occlusion-robust tracking
ResNet classifier: Forma renk sınıflandırma
Kalman Filter: Pozisyon tahmini


## Fonksiyon Özeti
__init__(self, players)
Yaptığı iş: Detectron2 segmentasyon modelini başlatır
Parametreler: players (Player objelerinin listesi)
Döndürdüğü değer: None

count_non_black(image) [static]
Yaptığı iş: Maskede sıfır olmayan piksel sayısını sayar (renk yoğunluğu ölçümü)
Parametreler: image (numpy array, genelde HSV mask)
Döndürdüğü değer: int (colored piksel sayısı)

bb_intersection_over_union(boxA, boxB) [static]
Yaptığı iş: İki bounding box arasındaki IoU değerini hesaplar (tracking için)
Parametreler:

boxA, boxB: (top, left, bottom, right) formatında bbox'lar
Döndürdüğü değer: float (0-1 arası IoU skoru)


get_players_pos(self, M, M1, frame, timestamp, map_2d)
Yaptığı iş: Ana fonksiyon - oyuncuları tespit edip pozisyonlarını günceller
Parametreler:

M, M1: Homografi matrisleri (3x3 numpy)
frame: Video frame (BGR numpy array)
timestamp: Frame numarası (int)
map_2d: 2D saha görüntüsü (BGR numpy array)

Döndürdüğü değer: (frame, map_2d, map_2d_text) tuple
İç Mantık:

Detectron2 ile insan segmentasyonu
Morphological erosion (gürültü azaltma)
Her oyuncu için:

Üst %30'u kesip forma bölgesini al
HSV'de renk maskeleme
En çok eşleşen rengi takım olarak ata
Baş-ayak keypoint'lerini bul
Homografi ile 2D sahaya projeksiyon


IoU ile mevcut player objelerine match et
7 frame göremezsen player'ı sıfırla
Sonuçları frame ve map'lere çiz


hsv2bgr(color_hsv) [global function]
Yaptığı iş: HSV rengi BGR'ye çevirir (OpenCV için)
Parametreler: color_hsv (H, S, V tuple)
Döndürdüğü değer: BGR tuple (B, G, R)
"""

import torch
import cv2
import numpy as np
from operator import itemgetter
import math

# optional OCR support for jersey numbers
try:
    import pytesseract
    HAS_PYTESSACT = True
except Exception:
    HAS_PYTESSACT = False

# import some common detectron2 utilities
from detectron2 import model_zoo
from detectron2.data import MetadataCatalog
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer

from tools.plot_tools import plt_plot
from scipy.optimize import linear_sum_assignment
from .kalman import KalmanTracker
import os

# optional jersey recognizer
try:
    from Modules.IDrecognition.jersey_recognizer import load_model, predict_from_bgr
    HAS_JERSEY_MODEL = True
except Exception:
    HAS_JERSEY_MODEL = False

COLORS = {  # in HSV FORMAT
    'blue': ([237, 65, 38], [265, 8, 61], [248, 69, 29]),  # NIGERIA
    'referee': ([229, 67, 72], [232, 71, 39], [229, 62, 66]),  # REFEREE
    'white': ([348, 3, 59], [30, 10, 56], [312, 7, 55])  # USA
}

#COLORS = {  # in HSV FORMAT
#    'green': ([56, 50, 50], [100, 255, 255], [72, 200, 153]),  # NIGERIA
#    'referee': ([0, 0, 0], [255, 35, 65], [120, 0, 0]),  # REFEREE
#    'white': ([0, 0, 190], [255, 26, 255], [255, 0, 255])  # USA
# }

IOU_TH = 0.2
PAD = 15
DIST_TH = 80  # pixels — threshold for proximity-based matching
W_DIST = 0.6
W_JERSEY = 0.3
W_IOU = 0.1
COST_ACCEPT_THRESHOLD = 1.0


def hsv2bgr(color_hsv):
    color_bgr = np.array(cv2.cvtColor(np.uint8([[color_hsv]]), cv2.COLOR_HSV2BGR)).ravel()
    color_bgr = (int(color_bgr[0]), int(color_bgr[1]), int(color_bgr[2]))
    return color_bgr


def dynamic_iou_threshold(prev_bb, det_bb, last_pos=None, curr_pos=None, base=IOU_TH, max_speed_px=50):
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


def extract_jersey_number(bgr_crop):
    """Attempt to read a jersey number from a BGR crop using pytesseract.
    Returns an int or None.
    If pytesseract is not installed, returns None.
    """
    if not HAS_PYTESSACT:
        return None
    try:
        gray = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        config = '--psm 7 -c tessedit_char_whitelist=0123456789'
        txt = pytesseract.image_to_string(th, config=config)
        txt = ''.join(ch for ch in txt if ch.isdigit())
        if txt == '':
            return None
        return int(txt)
    except Exception:
        return None


class FeetDetector:

    def __init__(self, players):
        # Image segmentation model from DETECTRON2
        cfg_seg = get_cfg()
        cfg_seg.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
        cfg_seg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.7  # set threshold for this model
        cfg_seg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml")
        self.predictor_seg = DefaultPredictor(cfg_seg)
        self.bbs = []
        self.players = players
        self.cfg = cfg_seg
        # attempt to load jersey model if configured
        self.jersey_model = None
        try:
            from config import load_config
            cfg = load_config('config/main_config.yaml')
            model_path = cfg.get('models.jersey_model_path')
            if model_path and os.path.exists(model_path) and HAS_JERSEY_MODEL:
                try:
                    self.jersey_model = load_model(model_path)
                except Exception:
                    self.jersey_model = None
        except Exception:
            self.jersey_model = None

    @staticmethod
    def count_non_black(image):
        colored = 0
        for color in image.flatten():
            if color > 0.0001:
                colored += 1
        return colored

    @staticmethod
    def bb_intersection_over_union(boxA, boxB):
        # sources: https://www.pyimagesearch.com/2016/11/07/intersection-over-union-iou-for-object-detection/
        # determine the (x, y)-coordinates of the intersection rectangle
        xA = max(boxA[0], boxB[0])  # horizontal tl
        yA = max(boxA[1], boxB[1])  # vertical tl
        xB = min(boxA[2], boxB[2])  # horizontal br
        yB = min(boxA[3], boxB[3])  # vertical br
        # compute the area of intersection rectangle
        interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
        # compute the area of both the prediction and ground-truth
        # rectangles
        boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
        boxBArea = (boxB[2] - boxB[0] + 1) * (boxB[3] - boxB[1] + 1)
        # compute the intersection over union by taking the intersection
        # area and dividing it by the sum of prediction + ground-truth
        # areas - the interesection area
        iou = interArea / float(boxAArea + boxBArea - interArea)
        # return the intersection over union value
        return iou

    def get_players_pos(self, M, M1, frame, timestamp, map_2d):
        warped_kpts = []
        outputs_seg = self.predictor_seg(frame)

        indices = outputs_seg["instances"].pred_classes.cpu().numpy()
        predicted_masks = outputs_seg["instances"].pred_masks.cpu().numpy()

        ppl = []

        kernel = np.array([[0, 1, 0],
                           [1, 1, 1],
                           [0, 1, 0]], np.uint8)

        for i, entry in enumerate(indices):  # picking only class 0 (people)
            if entry == 0:
                ppl.append(
                    np.array(cv2.erode(np.array(predicted_masks[i], dtype=np.uint8), kernel, iterations=4), dtype=bool))

        '''v = Visualizer(frame[:, :, ::-1], MetadataCatalog.get(self.cfg.DATASETS.TRAIN[0]), scale=1.2)
        out = v.draw_instance_predictions(outputs_seg["instances"].to("cpu"))
        plt_plot(out.get_image()[:, :, ::-1])'''

        indexes_ppl = np.array(
            [np.array(np.where(p == True)).T for p in ppl])
        # returns two np arrays per person, one for x one for y

        # calculate estimated position of players in the 2D map
        for keypoint, p in zip(indexes_ppl, ppl):

            top = min(keypoint[:, 0])
            bottom = max(keypoint[:, 0])
            left = min(keypoint[:, 1])
            right = max(keypoint[:, 1])
            bbox_person = (top - PAD, left - PAD, bottom + PAD, right + PAD)
            tmp_tensor = p.reshape((p.shape[0], p.shape[1], 1))

            # create a BGR crop (for optional OCR) and an HSV crop (for color detection)
            bgr_crop = np.where(tmp_tensor, frame, 0)
            bgr_crop = bgr_crop[top:(bottom - int(0.3 * (bottom - top))), left:right]
            if len(bgr_crop) > 0:
                crop_img = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2HSV)

                best_mask = [0, '']  # (num_non_black, color)
                for color in COLORS.keys():
                    mask = cv2.inRange(crop_img, np.
                                       array(COLORS[color][0]), np.array(COLORS[color][1]))
                    output = cv2.bitwise_and(crop_img, crop_img, mask=mask)

                    non_blacks = FeetDetector.count_non_black(output)
                    if best_mask[0] < non_blacks:
                        best_mask[0] = non_blacks
                        best_mask[1] = color

                head = int(np.argmin(keypoint[:, 0]))
                foot = int(np.argmax(keypoint[:, 0]))

                kpt = np.array([keypoint[head, 1], keypoint[foot, 0], 1])  # perspective space
                homo = M1 @ (M @ kpt.reshape((3, -1)))
                homo = np.int32(homo / homo[-1]).ravel()

                if best_mask[1] != '':
                    color = hsv2bgr(COLORS[best_mask[1]][2])
                    # include the BGR crop for optional OCR-based jersey reading
                    # if jersey_model is available, predict class name
                    jersey_label = None
                    if hasattr(self, 'jersey_model') and (self.jersey_model is not None):
                        try:
                            pred = predict_from_bgr(self.jersey_model, bgr_crop)
                            jersey_label = pred if isinstance(pred, str) else None
                        except Exception:
                            jersey_label = None
                    warped_kpts.append((homo, color, best_mask[1], bbox_person, bgr_crop, jersey_label))
                    cv2.circle(frame, (keypoint[head, 1], keypoint[foot, 0]), 2, color, 5)

        # Build detections grouped by team and pre-extract jersey numbers
        detections_by_team = {}
        for idx, kpt in enumerate(warped_kpts):
            # warped_kpts: (homo, color, color_key, bbox, bgr_crop, jersey_label)
            (homo, color, color_key, bbox, bgr_crop, jersey_label) = kpt
            jersey = extract_jersey_number(bgr_crop)
            # prefer model label if available
            if jersey_label is not None:
                jersey = jersey_label
            det = {
                'idx': idx,
                'pos': (int(homo[0]), int(homo[1])),
                'bbox': bbox,
                'bgr_crop': bgr_crop,
                'jersey': jersey
            }
            detections_by_team.setdefault(color_key, []).append(det)

        # For each team, perform optimal assignment between detections and known players
        for team, dets in detections_by_team.items():
            # candidate players of this team
            team_players = [p for p in self.players if p.team == team]
            if len(dets) == 0 or len(team_players) == 0:
                continue

            # build cost matrix: rows=detections, cols=players
            num_d = len(dets)
            num_p = len(team_players)
            cost = np.zeros((num_d, num_p), dtype=float)

            for i, det in enumerate(dets):
                for j, player in enumerate(team_players):
                    # distance cost
                    if len(player.positions) > 0:
                        last_ts = max(player.positions.keys())
                        last_pos = player.positions[last_ts]
                        d = math.hypot(det['pos'][0] - last_pos[0], det['pos'][1] - last_pos[1])
                    else:
                        d = DIST_TH * 2.0
                    dist_norm = min(d, DIST_TH) / float(DIST_TH)

                    # jersey cost
                    if (player.jersey_number is not None) and (det['jersey'] is not None):
                        jersey_cost = 0.0 if player.jersey_number == det['jersey'] else 1.0
                    else:
                        jersey_cost = 0.5

                    # iou cost (lower is better) — use dynamic threshold to normalize
                    if player.previous_bb is not None:
                        iou = self.bb_intersection_over_union(det['bbox'], player.previous_bb)
                        # determine last_pos: prefer last recorded position, fallback to kalman estimate
                        last_pos = None
                        if len(player.positions) > 0:
                            last_pos = player.positions[max(player.positions.keys())]
                        elif hasattr(player, 'kalman'):
                            last_pos = player.kalman.position

                        curr_pos = det['pos']
                        th = dynamic_iou_threshold(player.previous_bb, det['bbox'], last_pos, curr_pos)
                        effective_iou = min(1.0, iou / th) if th > 0 else 0.0
                        iou_cost = 1.0 - effective_iou
                    else:
                        iou_cost = 1.0

                    cost[i, j] = W_DIST * dist_norm + W_JERSEY * jersey_cost + W_IOU * iou_cost

            # solve assignment
            try:
                row_ind, col_ind = linear_sum_assignment(cost)
            except Exception:
                row_ind, col_ind = np.array([]), np.array([])

            assigned_players = set()
            assigned_dets = set()

            for r, c in zip(row_ind, col_ind):
                if r >= num_d or c >= num_p:
                    continue
                cval = cost[r, c]
                det = dets[r]
                player = team_players[c]
                if cval <= COST_ACCEPT_THRESHOLD:
                    player.previous_bb = det['bbox']
                    player.positions[timestamp] = det['pos']
                    # confidence: inverse normalized cost
                    max_cost = W_DIST + W_JERSEY + W_IOU
                    player.match_confidence = max(0.0, 1.0 - (cval / max_cost))
                    # update jersey if available
                    if det['jersey'] is not None and player.jersey_number is None:
                        player.jersey_number = det['jersey']
                    # initialize or update Kalman tracker for this player
                    try:
                        if hasattr(player, 'kalman'):
                            player.kalman.update(det['pos'])
                        else:
                            player.kalman = KalmanTracker(initial_pos=det['pos'], dt=1.0)
                    except Exception:
                        pass
                    assigned_players.add(player)
                    assigned_dets.add(r)

            # for unassigned detections, try to fill free player slots
            free_players = [p for p in team_players if p.previous_bb is None and p not in assigned_players]
            for i, det in enumerate(dets):
                if i in assigned_dets:
                    continue
                if len(free_players) > 0:
                    p = free_players.pop(0)
                    p.previous_bb = det['bbox']
                    p.positions[timestamp] = det['pos']
                    p.match_confidence = 0.5
                    if det['jersey'] is not None:
                        p.jersey_number = det['jersey']

        for player in self.players:
            if len(player.positions) > 0:
                if (timestamp - max(player.positions.keys())) >= 7:
                    player.positions = {}
                    player.previous_bb = None
                    player.has_ball = False

        map_2d_text = map_2d.copy()
        for p in self.players:
            if p.team != 'referee':
                try:
                    cv2.circle(map_2d, (p.positions[timestamp]), 10, p.color, 7)
                    cv2.circle(map_2d, (p.positions[timestamp]), 13, (0, 0, 0), 3)
                    cv2.circle(map_2d_text, (p.positions[timestamp]), 25, p.color, -1)
                    cv2.circle(map_2d_text, (p.positions[timestamp]), 27, (0, 0, 0), 5)
                    text_size, _ = cv2.getTextSize(str(p.ID), cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
                    text_origin = (p.positions[timestamp][0] - text_size[0] // 2,
                                   p.positions[timestamp][1] + text_size[1] // 2)
                    cv2.putText(map_2d_text, str(p.ID), text_origin,
                                cv2.FONT_HERSHEY_SIMPLEX, 1.5,
                                (0, 0, 0), 3, cv2.LINE_AA)
                except KeyError:
                    pass

        return frame, map_2d, map_2d_text


if __name__ == '__main__':
    print(torch.__version__, torch.cuda.is_available())
