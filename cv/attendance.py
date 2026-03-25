"""
=============================================================
 ATTENDANCE MANAGER - Quản lý điểm danh + Debounce
=============================================================
 Ghi log điểm danh, chống lặp (debounce), xuất CSV.
=============================================================
"""

import os
import csv
import time
from datetime import datetime


class AttendanceRecord:
    """1 bản ghi điểm danh."""

    def __init__(self, user_id, ho_ten, mssv, timestamp=None):
        self.user_id = user_id
        self.ho_ten = ho_ten
        self.mssv = mssv
        self.timestamp = timestamp or datetime.now()

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'ho_ten': self.ho_ten,
            'mssv': self.mssv,
            'timestamp': self.timestamp.isoformat(),
            'date': self.timestamp.strftime('%Y-%m-%d'),
            'time': self.timestamp.strftime('%H:%M:%S'),
        }

    def __repr__(self):
        t = self.timestamp.strftime('%H:%M:%S')
        return f"[{t}] {self.ho_ten} ({self.mssv})"


class AttendanceManager:
    """
    Quản lý điểm danh với debounce.

    Sử dụng:
        att = AttendanceManager(debounce_seconds=30)

        # Khi nhận diện được 1 người
        if att.check_and_log(user_id, "Quoc Anh", "123456"):
            print("Điểm danh thành công!")  # Lần đầu
        else:
            print("Đã điểm danh rồi!")     # Trong 30s
    """

    def __init__(self, debounce_seconds=30, log_dir="attendance_logs"):
        """
        Args:
            debounce_seconds: Thời gian chờ giữa 2 lần điểm danh
                              cùng 1 người (giây)
            log_dir: Thư mục lưu file log CSV
        """
        self.debounce_seconds = debounce_seconds
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # Debounce tracker: {user_id: last_timestamp}
        self._last_attendance = {}

        # Records hôm nay
        self.today_records = []

        print(f"[Attendance] Debounce: {debounce_seconds}s | "
              f"Logs: {log_dir}/")

    def check_and_log(self, user_id, ho_ten, mssv):
        """
        Kiểm tra debounce và ghi log điểm danh.

        Returns:
            True  → Điểm danh thành công (lần mới)
            False → Bị debounce (đã điểm danh gần đây)
        """
        now = time.time()

        # Check debounce
        if user_id in self._last_attendance:
            elapsed = now - self._last_attendance[user_id]
            if elapsed < self.debounce_seconds:
                remaining = int(self.debounce_seconds - elapsed)
                return False

        # Ghi log
        record = AttendanceRecord(user_id, ho_ten, mssv)
        self.today_records.append(record)
        self._last_attendance[user_id] = now

        # In ra Serial (console)
        self._print_log(record)

        # Ghi vào file CSV
        self._write_csv(record)

        return True

    def get_remaining_debounce(self, user_id):
        """Lấy thời gian debounce còn lại (giây). 0 = sẵn sàng."""
        if user_id not in self._last_attendance:
            return 0
        elapsed = time.time() - self._last_attendance[user_id]
        remaining = self.debounce_seconds - elapsed
        return max(0, int(remaining))

    def _print_log(self, record):
        """In log ra console."""
        print(f"\n{'=' * 45}")
        print(f"  ✅ ĐIỂM DANH THÀNH CÔNG")
        print(f"  Họ tên: {record.ho_ten}")
        print(f"  MSSV:   {record.mssv}")
        print(f"  Thời gian: {record.timestamp.strftime('%H:%M:%S %d/%m/%Y')}")
        print(f"{'=' * 45}\n")

    def _write_csv(self, record):
        """Ghi 1 record vào file CSV (theo ngày)."""
        date_str = record.timestamp.strftime('%Y-%m-%d')
        csv_path = os.path.join(self.log_dir, f"attendance_{date_str}.csv")

        file_exists = os.path.exists(csv_path)

        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ['STT', 'Họ tên', 'MSSV', 'Thời gian', 'User ID']
                )

            # Đếm số dòng đã có trong CSV (trừ header) để STT không bị reset
            if file_exists:
                try:
                    with open(csv_path, 'r', encoding='utf-8') as rf:
                        existing_lines = sum(1 for line in rf if line.strip()) - 1
                    stt = max(existing_lines, 0) + 1
                except Exception:
                    stt = len(self.today_records)
            else:
                stt = 1
            writer.writerow([
                stt,
                record.ho_ten,
                record.mssv,
                record.timestamp.strftime('%H:%M:%S'),
                record.user_id
            ])

    def get_today_records(self):
        """Lấy danh sách điểm danh hôm nay."""
        return self.today_records

    def get_today_count(self):
        """Số người đã điểm danh hôm nay."""
        unique_ids = set(r.user_id for r in self.today_records)
        return len(unique_ids)

    def reset_debounce(self, user_id=None):
        """Reset debounce cho 1 user hoặc tất cả."""
        if user_id is not None:
            self._last_attendance.pop(user_id, None)
        else:
            self._last_attendance.clear()

    def print_today(self):
        """In danh sách điểm danh hôm nay."""
        print(f"\n{'=' * 50}")
        print(f"  📋 DANH SÁCH ĐIỂM DANH HÔM NAY")
        print(f"  Ngày: {datetime.now().strftime('%d/%m/%Y')}")
        print(f"-" * 50)
        print(f"  {'STT':>3} | {'Họ tên':<20} | {'MSSV':<10} | {'Giờ'}")
        print(f"-" * 50)
        for i, r in enumerate(self.today_records, 1):
            t = r.timestamp.strftime('%H:%M:%S')
            print(f"  {i:>3} | {r.ho_ten:<20} | {r.mssv:<10} | {t}")
        print(f"{'=' * 50}")
        print(f"  Tổng: {self.get_today_count()} người\n")
