"""
=============================================================
 FACE SERVICE - AI Face Recognition (FaceNet 512-d)
=============================================================
 Tái sử dụng pipeline từ cv/face_processor.py:
   YOLOv8 detect → FaceNet 512-d embedding → cosine similarity
 Loại bỏ MediaPipe mesh (không cần cho web backend).
=============================================================
"""

import os
import sys
import cv2
import numpy as np
import torch
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from ultralytics import YOLO


class FaceService:
    """
    Service nhận diện khuôn mặt cho web backend.
    Singleton pattern — chỉ load models 1 lần.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.device = torch.device(
            'cuda' if torch.cuda.is_available() else 'cpu'
        )
        self.recognition_threshold = 0.80

        print(f"[FaceService] Initializing on {self.device}...")

        # ===== YOLOv8 Face Detection =====
        # Tìm model file ở thư mục hiện tại hoặc cv/
        cv_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "cv"
        )
        yolo_path = self._find_model(
            ["yolov8n-face.pt", "yolov8n.pt"],
            [os.getcwd(), cv_dir]
        )
        self.yolo = YOLO(yolo_path)
        self._yolo_is_face = "face" in yolo_path
        print(f"[FaceService] ✅ YOLO: {os.path.basename(yolo_path)}")

        # ===== FaceNet Embedding (512-d) =====
        self.mtcnn = MTCNN(
            image_size=160, margin=20, min_face_size=40,
            thresholds=[0.5, 0.6, 0.6], post_process=True,
            keep_all=True, device=self.device
        )
        self.facenet = InceptionResnetV1(
            pretrained='vggface2'
        ).eval().to(self.device)
        print("[FaceService] ✅ FaceNet loaded (512-d)")

        # Embedding cache
        self._mean_embeddings = {}  # {user_id: np.ndarray}
        self._cache_dirty = True

        print("[FaceService] ✅ Ready!")

    @staticmethod
    def _find_model(names, search_dirs):
        """Tìm model file trong nhiều thư mục."""
        for name in names:
            for d in search_dirs:
                path = os.path.join(d, name)
                if os.path.exists(path):
                    return path
        # Fallback: sẽ tự download
        return names[-1]

    # ========================================
    # DETECTION
    # ========================================

    def detect_faces(self, frame_bgr):
        """
        Detect faces bằng YOLOv8.
        Returns: list of (x1, y1, x2, y2, confidence)
        """
        results = self.yolo(frame_bgr, verbose=False, conf=0.5)

        faces = []
        if not results or results[0].boxes is None:
            return faces

        boxes = results[0].boxes
        for i in range(len(boxes)):
            if not self._yolo_is_face and int(boxes.cls[i]) != 0:
                continue

            conf = float(boxes.conf[i])
            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
            h, w = frame_bgr.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 - x1 > 30 and y2 - y1 > 30:
                faces.append((x1, y1, x2, y2, conf))

        return faces

    # ========================================
    # EMBEDDING
    # ========================================

    def extract_embedding(self, frame_bgr, box=None):
        """
        Trích xuất FaceNet 512-d embedding.
        Returns: np.ndarray (512,) hoặc None
        """
        try:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)

            if box is not None:
                x1, y1, x2, y2 = box[:4]
                pil_img = pil_img.crop((
                    max(0, x1), max(0, y1),
                    min(frame_bgr.shape[1], x2),
                    min(frame_bgr.shape[0], y2)
                ))

            face_tensor = self.mtcnn(pil_img)
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
        except Exception:
            # MTCNN torch.cat() lỗi khi face ở rìa ảnh
            return None

    # ========================================
    # RECOGNITION
    # ========================================

    def update_cache(self, users_embeddings):
        """
        Cập nhật cache mean embeddings.
        Args:
            users_embeddings: dict {user_id: list[np.ndarray]}
        """
        self._mean_embeddings = {}
        for uid, embs in users_embeddings.items():
            if embs:
                mean = np.mean(embs, axis=0)
                norm = np.linalg.norm(mean)
                if norm > 0:
                    mean = mean / norm
                self._mean_embeddings[uid] = mean
        self._cache_dirty = False
        print(f"[FaceService] Cache updated: {len(self._mean_embeddings)} users")

    def invalidate_cache(self):
        self._cache_dirty = True

    @property
    def cache_dirty(self):
        return self._cache_dirty

    def recognize(self, embedding):
        """
        So sánh embedding với cache.
        Returns: (user_id, confidence) hoặc (-1, best_sim)
        """
        if not self._mean_embeddings:
            return -1, 0.0

        best_uid, best_sim = -1, -1.0

        for uid, mean in self._mean_embeddings.items():
            sim = float(np.dot(embedding, mean))
            l2 = float(np.linalg.norm(embedding - mean))
            combined = 0.7 * sim + 0.3 * max(0, 1.0 - l2 / 2.0)
            if combined > best_sim:
                best_sim = combined
                best_uid = uid

        if best_sim >= self.recognition_threshold:
            return best_uid, float(best_sim)

        return -1, float(max(0, best_sim))

    def detect_and_recognize(self, frame_bgr):
        """
        Full pipeline: detect → embed → recognize.
        Returns: list of dict {box, user_id, confidence, embedding}
        """
        faces = self.detect_faces(frame_bgr)
        results = []

        for face in faces:
            x1, y1, x2, y2, det_conf = face
            emb = self.extract_embedding(frame_bgr, (x1, y1, x2, y2))

            if emb is None:
                results.append({
                    "box": [x1, y1, x2, y2],
                    "user_id": -1,
                    "confidence": 0.0,
                    "detection_conf": det_conf,
                    "embedding": None
                })
                continue

            user_id, rec_conf = self.recognize(emb)
            results.append({
                "box": [x1, y1, x2, y2],
                "user_id": user_id,
                "confidence": rec_conf,
                "detection_conf": det_conf,
                "embedding": emb
            })

        return results
