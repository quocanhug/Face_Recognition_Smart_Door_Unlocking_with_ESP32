"""
=============================================================
 SECURITY MANAGER - Quản lý an ninh + Remote Lock
=============================================================
 Tính năng:
   - Đếm số lần access deny liên tiếp
   - Phân biệt ban ngày / ban đêm (giờ cấu hình được)
   - Deny >= N lần → gửi Telegram MỖI LẦN (từ lần 2 trở đi)
   - Buzzer alarm chỉ kêu 30 giây rồi tự tắt
   - Remote Lock: khóa phòng từ xa qua web dashboard
     (người quen đến → không mở cửa, hiển thị "Quay lại")
=============================================================
"""

import json
import os
import time
from datetime import datetime
from notifier import TelegramNotifier


class SecurityManager:
    """
    Quản lý logic an ninh cho Smart Attendance System.

    Sử dụng:
        security = SecurityManager("security_config.json")

        # Khi unknown face
        security.on_access_deny(esp)

        # Khi known face
        security.on_access_granted(esp)
    """

    def __init__(self, config_path="security_config.json"):
        """
        Args:
            config_path: Đường dẫn file cấu hình JSON
        """
        self.config_path = config_path
        self.config = self._load_config()

        # Đếm deny liên tiếp
        self._deny_count = 0
        self._alarm_active = False  # Buzzer alarm đang kêu

        # Remote Lock: khóa phòng từ xa
        self._room_locked = False

        # Khởi tạo notifier
        self.notifier = TelegramNotifier(
            bot_token=self.config.get("telegram_bot_token", ""),
            chat_id=self.config.get("telegram_chat_id", "")
        )

        # Log config
        print(f"\n{'='*50}")
        print(f"  🔒 SECURITY MANAGER")
        print(f"  Ban đêm: {self.config['night_start_hour']}:00"
              f" → {self.config['night_end_hour']}:00")
        print(f"  Ngưỡng deny: {self.config['deny_threshold']} lần")
        print(f"  Notification: {'BẬT' if self.config['enable_notification'] else 'TẮT'}")
        print(f"  Buzzer alarm: 30s tự tắt")
        print(f"  Hiện tại: {self._get_mode_name()}")
        print(f"{'='*50}\n")

    def _load_config(self):
        """Load cấu hình từ JSON file."""
        default_config = {
            "night_start_hour": 22,
            "night_end_hour": 6,
            "deny_threshold": 2,
            "telegram_bot_token": "YOUR_BOT_TOKEN_HERE",
            "telegram_chat_id": "YOUR_CHAT_ID_HERE",
            "enable_notification": True,
            "enable_night_alarm": True
        }

        if not os.path.exists(self.config_path):
            print(f"[SECURITY] ⚠️ Không tìm thấy {self.config_path}, "
                  f"dùng config mặc định")
            # Tạo file config mặc định
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            return default_config

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Merge với default (phòng trường hợp thiếu key)
            for key, value in default_config.items():
                config.setdefault(key, value)
            print(f"[SECURITY] ✅ Loaded config từ {self.config_path}")
            return config
        except (json.JSONDecodeError, IOError) as e:
            print(f"[SECURITY] ❌ Lỗi đọc config: {e}, dùng mặc định")
            return default_config

    def reload_config(self):
        """Reload config từ file (hot-reload không cần restart)."""
        self.config = self._load_config()
        self.notifier = TelegramNotifier(
            bot_token=self.config.get("telegram_bot_token", ""),
            chat_id=self.config.get("telegram_chat_id", "")
        )

    def is_night_mode(self):
        """
        Kiểm tra có đang trong khung giờ ban đêm không.

        Hỗ trợ cả trường hợp:
            - night_start > night_end: VD 22:00 → 06:00 (qua nửa đêm)
            - night_start < night_end: VD 01:00 → 05:00
        """
        now_hour = datetime.now().hour
        start = int(self.config["night_start_hour"])
        end = int(self.config["night_end_hour"])

        if start > end:
            # Qua nửa đêm: 22:00 → 06:00
            return now_hour >= start or now_hour < end
        else:
            # Cùng ngày: 01:00 → 05:00
            return start <= now_hour < end

    def _get_mode_name(self):
        """Trả về tên chế độ hiện tại."""
        return "🌙 NIGHT MODE" if self.is_night_mode() else "☀️ DAY MODE"

    @property
    def deny_count(self):
        return self._deny_count

    @property
    def is_alarm_active(self):
        return self._alarm_active

    # ========================================
    # ROOM LOCK (Khóa phòng từ xa)
    # ========================================

    @property
    def is_room_locked(self):
        """Phòng có đang bị khóa không."""
        return self._room_locked

    def lock_room(self):
        """Khóa phòng từ xa."""
        self._room_locked = True
        print(f"[SECURITY] 🔒 PHÒNG ĐÃ KHÓA (Remote Lock)")

    def unlock_room(self):
        """Mở khóa phòng."""
        self._room_locked = False
        print(f"[SECURITY] 🔓 PHÒNG ĐÃ MỞ KHÓA")

    # ========================================
    # ACCESS EVENTS
    # ========================================

    def on_access_deny(self, esp):
        """
        Gọi khi có unknown face (access deny).
        Từ lần deny >= threshold: gửi Telegram MỖI LẦN + buzzer 30s.

        Args:
            esp: ESP32Controller hoặc ESP32Simulator instance
        """
        self._deny_count += 1
        is_night = self.is_night_mode()
        threshold = int(self.config["deny_threshold"])

        print(f"[SECURITY] ❌ Access Deny #{self._deny_count} "
              f"| Mode: {self._get_mode_name()}")

        # Chưa đạt ngưỡng → chỉ log
        if self._deny_count < threshold:
            print(f"[SECURITY] Đếm: {self._deny_count}/{threshold}")
            return

        # === ĐÃ ĐẠT NGƯỠNG → GỬI TELEGRAM MỖI LẦN ===
        print(f"\n[SECURITY] 🚨 CẢNH BÁO! "
              f"(deny #{self._deny_count})")

        if self.config["enable_notification"]:
            self.notifier.send_security_alert(
                deny_count=self._deny_count,
                is_night=is_night,
                mode_name=self._get_mode_name()
            )

        # === BUZZER ALARM 30 GIÂY (chỉ khi chưa đang kêu) ===
        if not self._alarm_active:
            print(f"[SECURITY] 🔔 KÍCH BUZZER ALARM 30s")
            self._alarm_active = True
            esp.buzzer_alarm_timed(30)

    def on_access_granted(self, esp):
        """
        Gọi khi nhận diện thành công (access granted).
        Reset counter và tắt alarm nếu đang kêu.

        Args:
            esp: ESP32Controller hoặc ESP32Simulator instance
        """
        if self._alarm_active:
            print(f"[SECURITY] 🔇 TẮT ALARM - Nhận diện thành công!")
            self._alarm_active = False
            esp.buzzer_stop()

        if self._deny_count > 0:
            print(f"[SECURITY] ✅ Reset deny counter "
                  f"({self._deny_count} → 0)")
            self._deny_count = 0

    def get_status_text(self):
        """Trả về text ngắn để hiển thị trên camera overlay."""
        mode = "NIGHT" if self.is_night_mode() else "DAY"
        alarm = " [ALARM!]" if self._alarm_active else ""
        deny = f" Deny:{self._deny_count}" if self._deny_count > 0 else ""
        lock = " [LOCKED]" if self._room_locked else ""
        return f"Security: {mode}{deny}{alarm}{lock}"
