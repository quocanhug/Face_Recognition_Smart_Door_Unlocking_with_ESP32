"""
=============================================================
 FACE PROCESSOR v3 - Hybrid Model (YOLOv8 + MediaPipe + FaceNet)
=============================================================
 Kiến trúc:
   1. YOLOv8       → Face Detection (bbox vàng)
   2. MediaPipe    → Face Mesh 468 landmarks (lưới xanh)
   3. FaceNet      → 512-D Embedding (nhận diện)

 Cải tiến:
   - Frontal face check (MediaPipe landmarks)
   - Face Quality Check (blur, brightness, size)
   - Multi-face tracking (IoU-based)
   - Temporal Smoothing (Recognition Buffer)
   - Threading-safe design
=============================================================
"""

import os
import cv2
import numpy as np
import torch
import time
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode
)
from collections import defaultdict, deque
from facenet_pytorch import MTCNN, InceptionResnetV1
from ultralytics import YOLO
from PIL import Image


# ============================================
# Face Mesh Tesselation Connections
# (Subset quan trọng nhất cho vẽ lưới mặt)
# ============================================
# Đây là danh sách connections chính của Face Mesh tessellation
# để vẽ lưới tam giác phủ toàn bộ khuôn mặt.
# Full set có ~460 connections, đây là subset hiệu quả.
FACE_OVAL = [
    (10, 338), (338, 297), (297, 332), (332, 284), (284, 251), (251, 389),
    (389, 356), (356, 454), (454, 323), (323, 361), (361, 288), (288, 397),
    (397, 365), (365, 379), (379, 378), (378, 400), (400, 377), (377, 152),
    (152, 148), (148, 176), (176, 149), (149, 150), (150, 136), (136, 172),
    (172, 58), (58, 132), (132, 93), (93, 234), (234, 127), (127, 162),
    (162, 21), (21, 54), (54, 103), (103, 67), (67, 109), (109, 10)
]

LEFT_EYE = [
    (263, 249), (249, 390), (390, 373), (373, 374), (374, 380), (380, 381),
    (381, 382), (382, 362), (362, 263), (263, 466), (466, 388), (388, 387),
    (387, 386), (386, 385), (385, 384), (384, 398), (398, 362)
]

RIGHT_EYE = [
    (33, 7), (7, 163), (163, 144), (144, 145), (145, 153), (153, 154),
    (154, 155), (155, 133), (133, 33), (33, 246), (246, 161), (161, 160),
    (160, 159), (159, 158), (158, 157), (157, 173), (173, 133)
]

LIPS = [
    (61, 146), (146, 91), (91, 181), (181, 84), (84, 17), (17, 314),
    (314, 405), (405, 321), (321, 375), (375, 291), (291, 61),
    (61, 185), (185, 40), (40, 39), (39, 37), (37, 0), (0, 267),
    (267, 269), (269, 270), (270, 409), (409, 291),
    (78, 95), (95, 88), (88, 178), (178, 87), (87, 14), (14, 317),
    (317, 402), (402, 318), (318, 324), (324, 308), (308, 78)
]

NOSE = [
    (168, 6), (6, 197), (197, 195), (195, 5), (5, 4),
    (4, 1), (1, 19), (19, 94), (94, 2), (2, 164),
    (1, 44), (44, 45), (45, 51), (51, 3),
    (1, 274), (274, 275), (275, 281), (281, 248), (248, 3)
]

FOREHEAD_CONNECT = [
    (10, 67), (10, 297), (67, 109), (109, 10), (297, 338), (338, 10),
    (54, 103), (103, 67), (67, 10), (284, 332), (332, 297), (297, 10),
    (21, 162), (162, 127), (127, 234), (251, 389), (389, 356),
    (136, 150), (150, 149), (149, 176), (176, 148), (148, 152),
]

# Kết hợp tất cả connections
ALL_FACE_CONNECTIONS = (
    FACE_OVAL + LEFT_EYE + RIGHT_EYE + LIPS + NOSE + FOREHEAD_CONNECT
)


class FaceResult:
    """Kết quả nhận diện 1 khuôn mặt."""

    def __init__(self, bbox, name="Unknown", user_id=-1,
                 mssv="", confidence=0.0, quality_score=1.0,
                 track_id=-1, landmarks=None, is_frontal=False):
        self.bbox = bbox
        self.name = name
        self.user_id = user_id
        self.mssv = mssv
        self.confidence = confidence
        self.quality_score = quality_score
        self.track_id = track_id
        self.landmarks = landmarks    # [(x,y), ...] 478 points
        self.is_frontal = is_frontal

    @property
    def is_known(self):
        return self.user_id >= 0

    def __repr__(self):
        return (f"FaceResult('{self.name}', id={self.user_id}, "
                f"conf={self.confidence:.2f}, track={self.track_id})")


class FaceTracker:
    """Theo dõi khuôn mặt qua nhiều frame bằng IoU."""

    def __init__(self, iou_threshold=0.3, max_lost=5):
        self.tracks = {}
        self.next_id = 0
        self.iou_threshold = iou_threshold
        self.max_lost = max_lost

    @staticmethod
    def _iou(box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter
        return inter / union if union > 0 else 0

    def update(self, boxes):
        if not boxes:
            for tid in list(self.tracks.keys()):
                self.tracks[tid]['lost'] += 1
                if self.tracks[tid]['lost'] > self.max_lost:
                    del self.tracks[tid]
            return []

        assigned = [None] * len(boxes)
        used = set()

        for i, box in enumerate(boxes):
            best_iou, best_tid = 0, None
            for tid, track in self.tracks.items():
                if tid in used:
                    continue
                iou = self._iou(box, track['bbox'])
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou, best_tid = iou, tid
            if best_tid is not None:
                assigned[i] = best_tid
                used.add(best_tid)
                self.tracks[best_tid] = {'bbox': box, 'lost': 0}

        for i in range(len(boxes)):
            if assigned[i] is None:
                tid = self.next_id
                self.next_id += 1
                assigned[i] = tid
                self.tracks[tid] = {'bbox': boxes[i], 'lost': 0}

        for tid in list(self.tracks.keys()):
            if tid not in used and tid not in assigned:
                self.tracks[tid]['lost'] += 1
                if self.tracks[tid]['lost'] > self.max_lost:
                    del self.tracks[tid]

        return assigned


class RecognitionBuffer:
    """Temporal smoothing: xác nhận sau N lần match liên tiếp."""

    def __init__(self, required_hits=3, buffer_size=5):
        self.required_hits = required_hits
        self.history = defaultdict(lambda: deque(maxlen=buffer_size))

    def update(self, track_id, user_id, confidence):
        self.history[track_id].append((user_id, confidence))
        recent = list(self.history[track_id])
        if len(recent) < self.required_hits:
            return -1, 0.0
        last_n = recent[-self.required_hits:]
        uids = [r[0] for r in last_n]
        confs = [r[1] for r in last_n]
        if all(uid == uids[0] and uid >= 0 for uid in uids):
            return uids[0], sum(confs) / len(confs)
        return -1, 0.0

    def clear_all(self):
        self.history.clear()


class FaceProcessor:
    """
    Engine xử lý khuôn mặt v3: Hybrid Model.
    Pipeline: YOLOv8 detect → MediaPipe mesh → FaceNet embed → recognize
    """

    def __init__(self, device=None, recognition_threshold=0.45,
                 detection_confidence=0.5, required_hits=2):
        if device is None:
            self.device = torch.device(
                'cuda' if torch.cuda.is_available() else 'cpu'
            )
        else:
            self.device = torch.device(device)

        self.recognition_threshold = recognition_threshold
        self.detection_confidence = detection_confidence

        print(f"[FaceProcessor v3] Khoi tao tren {self.device}...")

        # ===== MODEL 1: YOLOv8 Face Detection =====
        print("[FaceProcessor] Loading YOLOv8...")
        try:
            if os.path.exists("yolov8n-face.pt"):
                self.yolo = YOLO("yolov8n-face.pt")
                self._yolo_is_face_model = True
                print("[FaceProcessor] ✅ YOLOv8n-face loaded")
            else:
                self.yolo = YOLO("yolov8n.pt")
                self._yolo_is_face_model = False
                print("[FaceProcessor] ✅ YOLOv8n loaded (general)")
        except Exception as e:
            print(f"[FaceProcessor] ❌ YOLO error: {e}")
            raise

        # ===== MODEL 2: MediaPipe Face Landmarker (tasks API) =====
        print("[FaceProcessor] Loading MediaPipe FaceLandmarker...")
        model_path = "face_landmarker.task"
        if not os.path.exists(model_path):
            print("[FaceProcessor] Downloading face_landmarker.task...")
            import urllib.request
            url = ("https://storage.googleapis.com/mediapipe-models/"
                   "face_landmarker/face_landmarker/float16/latest/"
                   "face_landmarker.task")
            urllib.request.urlretrieve(url, model_path)

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.IMAGE,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=5,
            min_face_detection_confidence=0.4,
            min_face_presence_confidence=0.4,
            min_tracking_confidence=0.4
        )
        self.face_landmarker = FaceLandmarker.create_from_options(options)
        print("[FaceProcessor] ✅ MediaPipe FaceLandmarker loaded")

        # ===== MODEL 3: FaceNet Embedding =====
        print("[FaceProcessor] Loading FaceNet (VGGFace2)...")
        self.mtcnn_align = MTCNN(
            image_size=160, margin=20, min_face_size=40,
            thresholds=[0.5, 0.6, 0.6], post_process=True,
            keep_all=True, device=self.device
        )
        self.facenet = InceptionResnetV1(
            pretrained='vggface2'
        ).eval().to(self.device)
        print("[FaceProcessor] ✅ FaceNet loaded")

        # Database & cache
        self.db = None
        self._mean_embeddings = {}
        self._cache_dirty = True

        # Tracker & buffer
        self.tracker = FaceTracker(iou_threshold=0.3, max_lost=5)
        self.rec_buffer = RecognitionBuffer(
            required_hits=required_hits,
            buffer_size=required_hits + 2
        )

        # Quality thresholds
        self.MIN_FACE_SIZE = 50
        self.MIN_BRIGHTNESS = 40
        self.MAX_BRIGHTNESS = 220
        self.MIN_SHARPNESS = 30.0

        # Frontal thresholds
        self.FRONTAL_RATIO_MIN = 0.7
        self.FRONTAL_RATIO_MAX = 1.4

        print(f"[FaceProcessor v3] San sang! "
              f"(threshold={recognition_threshold}, hits={required_hits})")

    # ========================================
    # CẤU HÌNH
    # ========================================

    def set_database(self, user_database):
        self.db = user_database
        self._cache_dirty = True
        print(f"[FaceProcessor] Database: {len(user_database.users)} users")

    def set_threshold(self, threshold):
        self.recognition_threshold = threshold

    def invalidate_cache(self):
        self._cache_dirty = True

    def _refresh_cache(self):
        self._mean_embeddings = {}
        if self.db is None:
            return
        for uid, user in self.db.users.items():
            if user.embeddings:
                mean = np.mean(user.embeddings, axis=0)
                norm = np.linalg.norm(mean)
                if norm > 0:
                    mean = mean / norm
                self._mean_embeddings[uid] = mean
        self._cache_dirty = False
        print(f"[FaceProcessor] Cache: {len(self._mean_embeddings)} embeddings")

    # ========================================
    # FACE DETECTION (YOLOv8)
    # ========================================

    def detect_faces(self, frame_bgr):
        """Detect bằng YOLOv8. Returns: boxes, probs."""
        results = self.yolo(frame_bgr, verbose=False,
                            conf=self.detection_confidence)

        valid_boxes, valid_probs = [], []
        if not results or results[0].boxes is None:
            return [], []

        boxes = results[0].boxes
        for i in range(len(boxes)):
            if not self._yolo_is_face_model:
                if int(boxes.cls[i]) != 0:
                    continue

            conf = float(boxes.conf[i])
            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2 = min(frame_bgr.shape[1], x2)
            y2 = min(frame_bgr.shape[0], y2)

            if x2 - x1 > 20 and y2 - y1 > 20:
                valid_boxes.append([x1, y1, x2, y2])
                valid_probs.append(conf)

        return valid_boxes, valid_probs

    # ========================================
    # FACE MESH (MediaPipe Tasks API)
    # ========================================

    def get_face_mesh(self, frame_bgr, bbox=None):
        """
        Lấy Face Mesh landmarks bằng MediaPipe FaceLandmarker.
        Returns: list of (x, y) pixel coords, hoặc None
        """
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            h, w = frame_bgr.shape[:2]
            pad_x = int((x2 - x1) * 0.3)
            pad_y = int((y2 - y1) * 0.3)
            rx1 = max(0, x1 - pad_x)
            ry1 = max(0, y1 - pad_y)
            rx2 = min(w, x2 + pad_x)
            ry2 = min(h, y2 + pad_y)
            roi = frame_bgr[ry1:ry2, rx1:rx2]
        else:
            roi = frame_bgr
            rx1, ry1 = 0, 0

        rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        try:
            result = self.face_landmarker.detect(mp_image)
        except Exception:
            return None

        if not result.face_landmarks:
            return None

        face_lm = result.face_landmarks[0]
        rh, rw = roi.shape[:2]

        landmarks = []
        for lm in face_lm:
            px = int(lm.x * rw) + rx1
            py = int(lm.y * rh) + ry1
            landmarks.append((px, py))

        return landmarks

    def is_frontal_face(self, landmarks):
        """
        Kiểm tra chính diện bằng tỉ lệ khoảng cách mắt-mũi.
        Landmark indices: 1=nose, 33=right eye outer, 263=left eye outer
        """
        if not landmarks or len(landmarks) < 300:
            return False

        try:
            nose = np.array(landmarks[1])
            left_eye = np.array(landmarks[263])
            right_eye = np.array(landmarks[33])

            dist_left = np.linalg.norm(nose - left_eye)
            dist_right = np.linalg.norm(nose - right_eye)

            if dist_right < 1:
                return False

            ratio = dist_left / dist_right
            return self.FRONTAL_RATIO_MIN <= ratio <= self.FRONTAL_RATIO_MAX
        except (IndexError, ValueError):
            return False

    # ========================================
    # FACE QUALITY CHECK
    # ========================================

    def check_face_quality(self, frame_bgr, bbox):
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2 = min(frame_bgr.shape[1], x2)
        y2 = min(frame_bgr.shape[0], y2)

        face_crop = frame_bgr[y1:y2, x1:x2]
        if face_crop.size == 0:
            return 0.0, ["empty"]

        issues = []
        score = 1.0

        if x2-x1 < self.MIN_FACE_SIZE or y2-y1 < self.MIN_FACE_SIZE:
            issues.append("small")
            score *= 0.3

        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        if brightness < self.MIN_BRIGHTNESS:
            issues.append("dark")
            score *= 0.5
        elif brightness > self.MAX_BRIGHTNESS:
            issues.append("bright")
            score *= 0.5

        if cv2.Laplacian(gray, cv2.CV_64F).var() < self.MIN_SHARPNESS:
            issues.append("blurry")
            score *= 0.4

        ar = (x2-x1) / max(y2-y1, 1)
        if ar < 0.5 or ar > 2.0:
            issues.append("angle")
            score *= 0.6

        return min(1.0, score), issues

    # ========================================
    # FACE EMBEDDING (FaceNet)
    # ========================================

    def extract_embedding(self, frame_bgr, box=None):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        if box is not None:
            x1, y1, x2, y2 = box
            x1, y1 = max(0, x1), max(0, y1)
            x2 = min(frame_bgr.shape[1], x2)
            y2 = min(frame_bgr.shape[0], y2)
            pil_crop = pil_img.crop((x1, y1, x2, y2))
        else:
            pil_crop = pil_img

        face_tensor = self.mtcnn_align(pil_crop)
        if face_tensor is None:
            return None

        if face_tensor.dim() == 4:
            face_tensor = face_tensor[0]

        face_tensor = face_tensor.unsqueeze(0).to(self.device)
        with torch.no_grad():
            emb = self.facenet(face_tensor).cpu().numpy().flatten()

        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb

    # ========================================
    # RECOGNITION
    # ========================================

    @staticmethod
    def cosine_similarity(e1, e2):
        return float(np.dot(e1, e2))

    @staticmethod
    def l2_distance(e1, e2):
        return float(np.linalg.norm(e1 - e2))

    def recognize_embedding(self, embedding):
        if self.db is None:
            return -1, "Unknown", "", 0.0
        if self._cache_dirty:
            self._refresh_cache()
        if not self._mean_embeddings:
            return -1, "Unknown", "", 0.0

        best_uid, best_sim = -1, -1

        for uid, mean in self._mean_embeddings.items():
            sim = self.cosine_similarity(embedding, mean)
            l2 = self.l2_distance(embedding, mean)
            combined = 0.7 * sim + 0.3 * max(0, 1.0 - l2 / 2.0)
            if combined > best_sim:
                best_sim = combined
                best_uid = uid

        if best_sim >= self.recognition_threshold:
            user = self.db.get_user(best_uid)
            if user:
                return best_uid, user.ho_ten, user.mssv, float(best_sim)

        return -1, "Unknown", "", float(max(0, best_sim))

    # ========================================
    # PROCESS FRAME
    # ========================================

    def process_frame(self, frame_bgr, skip_mesh=False):
        """Full pipeline: YOLO → (MediaPipe mesh) → FaceNet → Recognize → Track.
        
        Args:
            frame_bgr: Input frame BGR
            skip_mesh: Nếu True, bỏ qua MediaPipe mesh (nhanh hơn ~100ms/face)
                       Mesh chỉ cần cho vẽ lưới, không ảnh hưởng nhận diện.
        """
        results = []
        boxes, probs = self.detect_faces(frame_bgr)

        if not boxes:
            self.tracker.update([])
            return results

        track_ids = self.tracker.update(boxes)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        for i, (box, prob, tid) in enumerate(zip(boxes, probs, track_ids)):
            x1, y1, x2, y2 = box

            quality, issues = self.check_face_quality(frame_bgr, box)
            
            # MediaPipe mesh: nặng (~50-100ms/face), chỉ chạy khi cần
            if skip_mesh:
                landmarks = None
                is_frontal = True  # Giả sử frontal khi skip
            else:
                landmarks = self.get_face_mesh(frame_bgr, box)
                is_frontal = self.is_frontal_face(landmarks)

            if quality < 0.3:
                results.append(FaceResult(
                    bbox=box, confidence=prob, quality_score=quality,
                    track_id=tid, landmarks=landmarks, is_frontal=is_frontal
                ))
                continue

            # FaceNet embed
            pil_crop = pil_img.crop((x1, y1, x2, y2))
            face_tensor = self.mtcnn_align(pil_crop)

            if face_tensor is None:
                results.append(FaceResult(
                    bbox=box, confidence=prob, quality_score=quality,
                    track_id=tid, landmarks=landmarks, is_frontal=is_frontal
                ))
                continue

            if face_tensor.dim() == 4:
                face_tensor = face_tensor[0]

            face_tensor = face_tensor.unsqueeze(0).to(self.device)
            with torch.no_grad():
                emb = self.facenet(face_tensor).cpu().numpy().flatten()

            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm

            raw_uid, raw_name, raw_mssv, raw_conf = \
                self.recognize_embedding(emb)

            c_uid, c_conf = self.rec_buffer.update(tid, raw_uid, raw_conf)

            if c_uid >= 0:
                user = self.db.get_user(c_uid)
                if user:
                    results.append(FaceResult(
                        bbox=box, name=user.ho_ten, user_id=c_uid,
                        mssv=user.mssv, confidence=c_conf,
                        quality_score=quality, track_id=tid,
                        landmarks=landmarks, is_frontal=is_frontal
                    ))
                    continue

            results.append(FaceResult(
                bbox=box, name="Unknown", user_id=-1, mssv="",
                confidence=raw_conf, quality_score=quality,
                track_id=tid, landmarks=landmarks, is_frontal=is_frontal
            ))

        return results

    # ========================================
    # VẼ KẾT QUẢ
    # ========================================

    @staticmethod
    def draw_face_mesh(frame, landmarks, color=(0, 255, 0), thickness=1):
        """Vẽ lưới Face Mesh lên frame."""
        if not landmarks:
            return
        pts = landmarks
        for (i1, i2) in ALL_FACE_CONNECTIONS:
            if i1 < len(pts) and i2 < len(pts):
                cv2.line(frame, pts[i1], pts[i2], color, thickness)

    @staticmethod
    def draw_results(frame, results, show_confidence=True, draw_mesh=True):
        """Vẽ bbox VÀNG + mesh XANH + label."""
        for r in results:
            x1, y1, x2, y2 = r.bbox

            if r.is_known:
                box_color = (0, 220, 255)   # Vàng
                label_bg = (0, 150, 0)
                mesh_color = (0, 255, 0)
            else:
                box_color = (0, 200, 255)   # Vàng cam
                label_bg = (0, 0, 180)
                mesh_color = (0, 180, 0)

            # Bbox vàng
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

            # Corner accents
            cl = min(20, (x2-x1)//4, (y2-y1)//4)
            for cx, cy in [(x1,y1),(x2,y1),(x1,y2),(x2,y2)]:
                dx = cl if cx == x1 else -cl
                dy = cl if cy == y1 else -cl
                cv2.line(frame, (cx,cy), (cx+dx,cy), box_color, 3)
                cv2.line(frame, (cx,cy), (cx,cy+dy), box_color, 3)

            # Face Mesh xanh
            if draw_mesh and r.landmarks:
                FaceProcessor.draw_face_mesh(frame, r.landmarks,
                                             mesh_color, 1)

            # Label
            font = cv2.FONT_HERSHEY_SIMPLEX
            if r.is_known:
                line1 = r.name
                if show_confidence:
                    line1 += f" ({r.confidence*100:.0f}%)"
            else:
                line1 = "Unknown"
                if show_confidence and r.confidence > 0:
                    line1 += f" ({r.confidence*100:.0f}%)"

            (tw, th), _ = cv2.getTextSize(line1, font, 0.55, 2)
            cv2.rectangle(frame, (x1, y1-th-12), (x1+tw+8, y1),
                          label_bg, -1)
            cv2.putText(frame, line1, (x1+4, y1-6), font, 0.55,
                        (255,255,255), 2)

            if r.is_known and r.mssv:
                line2 = f"MSSV: {r.mssv}"
                (tw2, th2), _ = cv2.getTextSize(line2, font, 0.45, 1)
                cv2.rectangle(frame, (x1, y2), (x1+tw2+8, y2+th2+8),
                              label_bg, -1)
                cv2.putText(frame, line2, (x1+4, y2+th2+4), font, 0.45,
                            (255,255,255), 1)

            if r.is_frontal:
                cv2.putText(frame, "FRONTAL", (x2-60, y1+15), font,
                            0.35, (0,255,0), 1)
            if r.quality_score < 0.7:
                y_pos = y1 + (30 if r.is_frontal else 15)
                cv2.putText(frame, "LOW Q", (x2-50, y_pos), font,
                            0.35, (0,165,255), 1)

        return frame

    @staticmethod
    def draw_enroll_ui(frame, name, count, limit):
        """Vẽ Progress bar + label cho Enroll mode."""
        h, w = frame.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX

        bar_x, bar_y = 20, h - 45
        bar_w, bar_h = w - 40, 22
        progress = min(count / max(limit, 1), 1.0)

        cv2.rectangle(frame, (bar_x, bar_y),
                      (bar_x+bar_w, bar_y+bar_h), (60,60,60), -1)
        cv2.rectangle(frame, (bar_x, bar_y),
                      (bar_x+bar_w, bar_y+bar_h), (100,100,100), 1)

        fill_w = int(bar_w * progress)
        if fill_w > 0:
            g = int(255 * (1 - progress * 0.3))
            cv2.rectangle(frame, (bar_x+1, bar_y+1),
                          (bar_x+fill_w, bar_y+bar_h-1),
                          (0, g, 0), -1)

        txt = f"{count}/{limit}"
        (tw, th), _ = cv2.getTextSize(txt, font, 0.5, 1)
        cv2.putText(frame, txt,
                    (bar_x+bar_w//2-tw//2, bar_y+bar_h//2+th//2),
                    font, 0.5, (255,255,255), 1)

        label = f"Enroll: {name}  [{count}/{limit}]"
        cv2.putText(frame, label, (bar_x, bar_y-8), font, 0.6,
                    (0,255,255), 2)

        return frame

    # ========================================
    # ENROLL
    # ========================================

    def enroll_from_frame(self, frame_bgr, user_id):
        if self.db is None:
            return False
        emb = self.extract_embedding(frame_bgr)
        if emb is None:
            return False
        self.db.enroll_face(user_id, emb)
        self._cache_dirty = True
        return True

    def enroll_from_folder(self, folder_path, user_id):
        if not os.path.exists(folder_path):
            print(f"[FaceProcessor] Khong co: {folder_path}")
            return 0

        valid_ext = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
        images = [f for f in os.listdir(folder_path)
                  if f.lower().endswith(valid_ext)]
        if not images:
            return 0

        success = 0
        for i, name in enumerate(images):
            frame = cv2.imread(os.path.join(folder_path, name))
            if frame is None:
                continue
            if self.enroll_from_frame(frame, user_id):
                success += 1
            if (i+1) % 10 == 0:
                print(f"  {i+1}/{len(images)}")

        print(f"[FaceProcessor] Enroll: {success}/{len(images)}")
        self._cache_dirty = True
        return success
