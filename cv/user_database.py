"""
=============================================================
 USER DATABASE - Quản lý người dùng (Tên, MSSV, Face)
=============================================================
 Lưu trữ thông tin người dùng và face embeddings.
 Dữ liệu được lưu vào file .pkl để dùng offline.
=============================================================
"""

import os
import pickle
import numpy as np
from datetime import datetime


class UserInfo:
    """Thông tin 1 người dùng."""

    def __init__(self, user_id: int, ho_ten: str, mssv: str):
        self.user_id = user_id
        self.ho_ten = ho_ten
        self.mssv = mssv
        self.embeddings = []  # List[np.ndarray] - nhiều embedding cho 1 người
        self.created_at = datetime.now().isoformat()

    def add_embedding(self, embedding: np.ndarray):
        """Thêm 1 face embedding cho người này."""
        self.embeddings.append(embedding)

    def get_mean_embedding(self) -> np.ndarray:
        """Lấy embedding trung bình (đại diện)."""
        if not self.embeddings:
            return None
        return np.mean(self.embeddings, axis=0)

    def __repr__(self):
        return f"User({self.user_id}, '{self.ho_ten}', '{self.mssv}', {len(self.embeddings)} faces)"


class UserDatabase:
    """
    Database người dùng với face embeddings.
    Hỗ trợ:
    - Thêm/xóa người dùng
    - Enroll khuôn mặt (thêm embedding)
    - Tra cứu theo face_id
    - Lưu/load từ file
    """

    def __init__(self, db_path: str = "user_database.pkl"):
        self.db_path = db_path
        self.users = {}          # {user_id: UserInfo}
        self.next_id = 1
        self._load()

    # ========================================
    # QUẢN LÝ NGƯỜI DÙNG
    # ========================================

    def add_user(self, ho_ten: str, mssv: str) -> int:
        """
        Thêm người dùng mới.
        Returns: user_id
        """
        user_id = self.next_id
        self.users[user_id] = UserInfo(user_id, ho_ten, mssv)
        self.next_id += 1
        self._save()
        print(f"[DB] Đã thêm: {ho_ten} (MSSV: {mssv}) → ID={user_id}")
        return user_id

    def remove_user(self, user_id: int) -> bool:
        """Xóa người dùng theo ID."""
        if user_id in self.users:
            user = self.users.pop(user_id)
            self._save()
            print(f"[DB] Đã xóa: {user.ho_ten} (ID={user_id})")
            return True
        print(f"[DB] Không tìm thấy user ID={user_id}")
        return False

    def get_user(self, user_id: int) -> UserInfo:
        """Lấy thông tin người dùng theo ID."""
        return self.users.get(user_id)

    def get_all_users(self) -> list:
        """Lấy danh sách tất cả người dùng."""
        return list(self.users.values())

    def find_by_mssv(self, mssv: str) -> UserInfo:
        """Tìm người dùng theo MSSV."""
        for user in self.users.values():
            if user.mssv == mssv:
                return user
        return None

    # ========================================
    # QUẢN LÝ FACE EMBEDDINGS
    # ========================================

    def enroll_face(self, user_id: int, embedding: np.ndarray) -> bool:
        """
        Enroll 1 face embedding cho người dùng.
        Mỗi người nên có 5-20 embeddings để nhận diện tốt.
        """
        if user_id not in self.users:
            print(f"[DB] User ID={user_id} không tồn tại!")
            return False

        self.users[user_id].add_embedding(embedding)
        self._save()
        user = self.users[user_id]
        print(f"[DB] Enrolled face cho {user.ho_ten}: "
              f"{len(user.embeddings)} embeddings")
        return True

    def get_all_embeddings(self):
        """
        Lấy tất cả embeddings đã enroll.
        Returns:
            embeddings: np.ndarray shape (N, 512)
            user_ids: list[int] - user_id tương ứng
            names: list[str] - tên tương ứng
        """
        all_embeddings = []
        all_user_ids = []
        all_names = []

        for user_id, user in self.users.items():
            for emb in user.embeddings:
                all_embeddings.append(emb)
                all_user_ids.append(user_id)
                all_names.append(user.ho_ten)

        if not all_embeddings:
            return np.array([]), [], []

        return np.array(all_embeddings), all_user_ids, all_names

    def get_enrolled_count(self) -> int:
        """Tổng số embeddings đã enroll."""
        return sum(len(u.embeddings) for u in self.users.values())

    # ========================================
    # LƯU / LOAD FILE
    # ========================================

    def _save(self):
        """Lưu database vào file."""
        data = {
            'users': self.users,
            'next_id': self.next_id
        }
        with open(self.db_path, 'wb') as f:
            pickle.dump(data, f)

    def _load(self):
        """Load database từ file."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'rb') as f:
                    data = pickle.load(f)
                self.users = data.get('users', {})
                self.next_id = data.get('next_id', 1)
                print(f"[DB] Loaded {len(self.users)} users, "
                      f"{self.get_enrolled_count()} embeddings")
            except Exception as e:
                print(f"[DB] Lỗi load database: {e}")
                self.users = {}
                self.next_id = 1
        else:
            print(f"[DB] Database mới: {self.db_path}")

    # ========================================
    # HIỂN THỊ
    # ========================================

    def print_users(self):
        """In danh sách người dùng."""
        print("\n" + "=" * 55)
        print(f" {'ID':>3} | {'Họ tên':<20} | {'MSSV':<12} | {'Faces':>5}")
        print("-" * 55)
        for user in self.users.values():
            print(f" {user.user_id:>3} | {user.ho_ten:<20} | "
                  f"{user.mssv:<12} | {len(user.embeddings):>5}")
        print("=" * 55)
        print(f" Tổng: {len(self.users)} users, "
              f"{self.get_enrolled_count()} embeddings\n")
