"""
=============================================================
 NOTIFIER - Gửi cảnh báo qua Telegram Bot API
=============================================================
 Gửi tin nhắn text về điện thoại khi có sự kiện an ninh.
 Không cần cài thêm thư viện (dùng requests có sẵn).
=============================================================
"""

import threading
import requests
from datetime import datetime


class TelegramNotifier:
    """
    Gửi tin nhắn cảnh báo qua Telegram Bot API.

    Cách tạo bot:
        1. Chat với @BotFather trên Telegram → /newbot
        2. Lấy bot token
        3. Chat với bot, rồi mở:
           https://api.telegram.org/bot<TOKEN>/getUpdates
           → Lấy chat_id từ kết quả JSON

    Sử dụng:
        notifier = TelegramNotifier("BOT_TOKEN", "CHAT_ID")
        notifier.send_alert("Cảnh báo: Có người lạ!")
    """

    TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token, chat_id):
        """
        Args:
            bot_token: Token của Telegram Bot (từ @BotFather)
            chat_id: ID chat nhận tin nhắn (cá nhân hoặc nhóm)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._enabled = self._validate_config()

        if self._enabled:
            print(f"[NOTIFY] ✅ Telegram notifier ready")
        else:
            print(f"[NOTIFY] ⚠️ Telegram chưa cấu hình (token/chat_id mặc định)")

    def _validate_config(self):
        """Kiểm tra token và chat_id đã được cấu hình chưa."""
        if not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN_HERE":
            return False
        if not self.chat_id or self.chat_id == "YOUR_CHAT_ID_HERE":
            return False
        return True

    @property
    def is_enabled(self):
        return self._enabled

    def send_alert(self, message):
        """
        Gửi tin nhắn cảnh báo qua Telegram (async, không block).

        Args:
            message: Nội dung tin nhắn
        """
        if not self._enabled:
            print(f"[NOTIFY] ⚠️ Telegram chưa cấu hình, skip gửi.")
            print(f"[NOTIFY] Nội dung: {message}")
            return

        thread = threading.Thread(
            target=self._send_sync,
            args=(message,),
            daemon=True
        )
        thread.start()

    def _send_sync(self, message):
        """Gửi tin nhắn đồng bộ (chạy trong thread riêng)."""
        try:
            url = self.TELEGRAM_API.format(token=self.bot_token)
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, json=payload, timeout=10)

            if resp.status_code == 200:
                print(f"[NOTIFY] ✅ Đã gửi Telegram thành công")
            else:
                print(f"[NOTIFY] ❌ Telegram lỗi: {resp.status_code} - {resp.text}")

        except requests.exceptions.RequestException as e:
            print(f"[NOTIFY] ❌ Gửi Telegram thất bại: {type(e).__name__}: {e}")

    def send_security_alert(self, deny_count, is_night, mode_name=""):
        """
        Gửi cảnh báo an ninh có format sẵn.

        Args:
            deny_count: Số lần bị deny liên tiếp
            is_night: True nếu đang ban đêm
            mode_name: Tên chế độ (DAY/NIGHT)
        """
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S %d/%m/%Y")

        period = "🌙 BAN ĐÊM" if is_night else "☀️ BAN NGÀY"
        alarm_status = "🔔 BUZZER ALARM ĐANG KÊU" if is_night else ""

        message = (
            f"🚨 <b>CẢNH BÁO AN NINH</b> 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Smart Attendance System\n"
            f"⏰ {time_str}\n"
            f"🔒 Chế độ: {period}\n"
            f"❌ Số lần Access Deny: <b>{deny_count}</b>\n"
            f"{alarm_status}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Có người không xác định đang cố truy cập!"
        )

        self.send_alert(message)
