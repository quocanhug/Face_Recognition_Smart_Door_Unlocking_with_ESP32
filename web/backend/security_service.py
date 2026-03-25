"""
=============================================================
 SECURITY SERVICE - Security + Remote Lock + Telegram Alerts
=============================================================
 Async version of security_manager.py + notifier.py
 - Telegram mỗi lần deny >= threshold
 - Buzzer alarm 30s tự tắt
 - Remote Lock: khóa phòng từ xa
============================================================="""

import json
import os
import httpx
from datetime import datetime


class SecurityService:
    """
    Quản lý an ninh: day/night mode, deny counter, Telegram alerts.
    """

    def __init__(self, config_path=None):
        self.config = {
            "night_start_hour": 9,
            "night_end_hour": 17,
            "deny_threshold": 2,
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "enable_notification": True,
            "enable_night_alarm": True
        }
        self.config_path = config_path
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

        self._deny_count = 0
        self._alarm_active = False
        self._room_locked = False  # Remote Lock
        self._http_client = httpx.AsyncClient(timeout=10.0)

        print(f"[Security] Night: {self.config['night_start_hour']}:00 → "
              f"{self.config['night_end_hour']}:00 | "
              f"Threshold: {self.config['deny_threshold']}")

    def _load_config(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            self.config.update(loaded)
            print(f"[Security] ✅ Config loaded from {path}")
        except Exception as e:
            print(f"[Security] ⚠️ Config error: {e}")

    def update_config(self, new_config: dict):
        """Cập nhật config và lưu file."""
        self.config.update(new_config)
        if self.config_path:
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=4, ensure_ascii=False)
            except IOError:
                pass

    def is_night_mode(self) -> bool:
        now_hour = datetime.now().hour
        start = int(self.config["night_start_hour"])
        end = int(self.config["night_end_hour"])
        if start > end:
            return now_hour >= start or now_hour < end
        else:
            return start <= now_hour < end

    @property
    def mode_name(self) -> str:
        return "NIGHT" if self.is_night_mode() else "DAY"

    @property
    def deny_count(self) -> int:
        return self._deny_count

    @property
    def is_alarm_active(self) -> bool:
        return self._alarm_active

    # ========================================
    # ROOM LOCK (Khóa phòng từ xa + tự động ban đêm)
    # ========================================

    @property
    def is_room_locked(self) -> bool:
        """Phòng bị khóa nếu: khóa thủ công HOẶC ban đêm (auto)."""
        if self._room_locked:
            return True
        if self.config.get("auto_lock_night", True) and self.is_night_mode():
            return True
        return False

    @property
    def lock_reason(self) -> str:
        """Trả về lý do khóa: 'manual', 'night', hoặc '' nếu không khóa."""
        if self._room_locked:
            return "manual"
        if self.config.get("auto_lock_night", True) and self.is_night_mode():
            return "night"
        return ""

    def lock_room(self):
        self._room_locked = True
        print("[Security] 🔒 PHÒNG ĐÃ KHÓA (thủ công)")

    def unlock_room(self):
        self._room_locked = False
        print("[Security] 🔓 PHÒNG ĐÃ MỞ KHÓA")

    # ========================================
    # ACCESS EVENTS
    # ========================================

    async def on_access_deny(self, esp32):
        """
        Xử lý khi access deny.
        Từ lần deny >= threshold: gửi Telegram MỖI LẦN + buzzer 30s.
        """
        self._deny_count += 1
        threshold = int(self.config["deny_threshold"])
        is_night = self.is_night_mode()

        if self._deny_count < threshold:
            return {"action": "counting", "count": self._deny_count}

        # === ĐẠT NGƯỠNG → GỬI TELEGRAM MỖI LẦN ===
        if self.config["enable_notification"]:
            await self._send_telegram(self._deny_count, is_night)

        # === BUZZER ALARM 30s (chỉ khi chưa đang kêu) ===
        if not self._alarm_active:
            self._alarm_active = True
            await esp32.buzzer_alarm_timed(30)
            return {"action": "alarm_started", "count": self._deny_count}

        return {"action": "notification_sent", "count": self._deny_count}

    async def on_access_granted(self, esp32):
        """Reset counter + tắt alarm khi nhận diện thành công."""
        was_alarm = self._alarm_active
        if self._alarm_active:
            self._alarm_active = False
            await esp32.buzzer_stop()

        self._deny_count = 0

        return {"alarm_stopped": was_alarm}

    async def _send_telegram(self, deny_count, is_night):
        """Gửi cảnh báo qua Telegram Bot API."""
        token = self.config.get("telegram_bot_token", "")
        chat_id = self.config.get("telegram_chat_id", "")

        if not token or token == "YOUR_BOT_TOKEN_HERE":
            print("[Security] ⚠️ Telegram not configured")
            return

        now = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        period = "🌙 BAN ĐÊM" if is_night else "☀️ BAN NGÀY"
        alarm = "\n🔔 BUZZER ALARM ĐANG KÊU" if is_night else ""

        message = (
            f"🚨 <b>CẢNH BÁO AN NINH</b> 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Smart Attendance System\n"
            f"⏰ {now}\n"
            f"🔒 Chế độ: {period}\n"
            f"❌ Access Deny: <b>{deny_count}</b> lần"
            f"{alarm}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Có người lạ đang cố truy cập!"
        )

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            resp = await self._http_client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
            )
            if resp.status_code == 200:
                print("[Security] ✅ Telegram sent!")
            else:
                print(f"[Security] ❌ Telegram error: {resp.status_code}")
        except httpx.RequestError as e:
            print(f"[Security] ❌ Telegram failed: {e}")

    async def close(self):
        await self._http_client.aclose()
