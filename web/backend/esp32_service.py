"""
=============================================================
 ESP32 SERVICE - Async HTTP Communication
=============================================================
 Giao tiếp với ESP32-S3 qua httpx (async).
 Thay thế requests (sync) của hệ thống cũ.
=============================================================
"""

import asyncio
import cv2
import numpy as np
import httpx
import unicodedata


class ESP32Service:
    """
    Giao tiếp async với ESP32-S3 qua HTTP.
    """

    def __init__(self, ip_address="", port=80, stream_port=81):
        self.ip_address = ip_address
        self.base_url = f"http://{ip_address}:{port}" if ip_address else ""
        self.stream_url = f"http://{ip_address}:{stream_port}" if ip_address else ""
        self._connected = False
        self._client = httpx.AsyncClient(timeout=5.0)
        self._alarm_active = False
        self._alarm_task = None  # asyncio task for timed alarm

        if ip_address:
            print(f"[ESP32] Target: {self.base_url}")

    @property
    def is_connected(self):
        return self._connected

    @property
    def is_configured(self):
        return bool(self.ip_address)

    def configure(self, ip_address, port=80, stream_port=81):
        """Cấu hình IP ESP32 (có thể gọi sau khi khởi tạo)."""
        self.ip_address = ip_address
        self.base_url = f"http://{ip_address}:{port}"
        self.stream_url = f"http://{ip_address}:{stream_port}"
        print(f"[ESP32] Configured: {self.base_url}")

    # ========================================
    # CONNECTION
    # ========================================

    async def check_connection(self):
        """Kiểm tra kết nối ESP32."""
        if not self.is_configured:
            self._connected = False
            return False

        try:
            resp = await self._client.get(f"{self.base_url}/status")
            if resp.status_code == 200:
                self._connected = True
                print("[ESP32] ✅ Connected!")
                return True
        except httpx.RequestError:
            pass

        try:
            resp = await self._client.get(
                f"{self.base_url}/capture", timeout=3.0
            )
            if resp.status_code == 200:
                self._connected = True
                return True
        except httpx.RequestError:
            pass

        self._connected = False
        print(f"[ESP32] ❌ Cannot connect: {self.base_url}")
        return False

    # ========================================
    # CAMERA
    # ========================================

    async def capture_frame(self):
        """
        Chụp 1 frame từ ESP32 camera.
        Returns: numpy BGR array hoặc None
        """
        if not self.is_configured:
            return None
        try:
            resp = await self._client.get(f"{self.base_url}/capture")
            if resp.status_code == 200:
                img_array = np.frombuffer(resp.content, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                return frame
        except httpx.RequestError:
            return None
        return None

    def get_stream_url(self):
        """URL cho MJPEG stream (proxy qua frontend)."""
        if self.is_configured:
            return f"{self.stream_url}/stream"
        return ""

    # ========================================
    # LCD
    # ========================================

    @staticmethod
    def _normalize_text(text):
        """Xóa dấu tiếng Việt cho LCD1602."""
        if not text:
            return ""
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.replace('đ', 'd').replace('Đ', 'D')

    async def lcd_display(self, line1="", line2=""):
        """Hiển thị text lên LCD."""
        if not self.is_configured:
            return
        line1 = self._normalize_text(line1)[:16]
        line2 = self._normalize_text(line2)[:16]
        try:
            await self._client.post(
                f"{self.base_url}/lcd",
                json={"line1": line1, "line2": line2},
                timeout=3.0
            )
        except httpx.RequestError:
            pass

    async def lcd_idle(self):
        await self.lcd_display("SMART ATTEND", "Scan face...")

    async def lcd_recognized(self, name, mssv):
        name = self._normalize_text(name)
        mssv = self._normalize_text(mssv)
        await self.lcd_display(name[:16], mssv[:16])

    async def lcd_unknown(self):
        await self.lcd_display("UNKNOWN", "ACCESS DENY")

    async def lcd_already(self):
        await self.lcd_display("DA DIEM DANH", "Vui long cho...")

    async def lcd_room_locked(self):
        await self.lcd_display("PHONG DA KHOA", "Comeback tomorrow")

    # ========================================
    # RELAY
    # ========================================

    async def relay_open(self, duration=3):
        """Mở relay (khóa cửa)."""
        if not self.is_configured:
            return False
        for attempt in range(3):
            try:
                resp = await self._client.post(
                    f"{self.base_url}/relay",
                    json={"action": "open", "duration": duration}
                )
                if resp.status_code == 200:
                    print(f"[ESP32] 🔓 Relay OPEN ({duration}s)")
                    return True
            except httpx.RequestError:
                pass
            if attempt < 2:
                await asyncio.sleep(0.5)

        print("[ESP32] ❌ Relay FAILED")
        return False

    # ========================================
    # BUZZER
    # ========================================

    async def buzzer_beep(self, pattern="ok"):
        """Buzzer beep."""
        if not self.is_configured:
            return
        try:
            await self._client.post(
                f"{self.base_url}/buzzer",
                json={"pattern": pattern},
                timeout=3.0
            )
        except httpx.RequestError:
            pass

    async def buzzer_alarm(self):
        """Buzzer alarm liên tục."""
        self._alarm_active = True
        await self.buzzer_beep("alarm")

    async def buzzer_alarm_timed(self, duration=30):
        """
        Buzzer alarm tự tắt sau duration giây.
        """
        # Cancel task cũ nếu có
        if self._alarm_task and not self._alarm_task.done():
            self._alarm_task.cancel()

        self._alarm_active = True
        await self.buzzer_beep("alarm")

        # Tạo task tự tắt sau duration giây
        async def _auto_stop():
            await asyncio.sleep(duration)
            if self._alarm_active:
                self._alarm_active = False
                await self.buzzer_beep("stop")
                print(f"[ESP32] ⏰ Alarm timeout {duration}s → tự tắt")

        self._alarm_task = asyncio.create_task(_auto_stop())
        print(f"[ESP32] 🔔 Alarm sẽ tự tắt sau {duration}s")

    async def buzzer_stop(self):
        """Tắt buzzer alarm + cancel timer nếu có."""
        # Cancel timed alarm task
        if self._alarm_task and not self._alarm_task.done():
            self._alarm_task.cancel()
            self._alarm_task = None

        self._alarm_active = False
        await self.buzzer_beep("stop")

    # ========================================
    # CLEANUP
    # ========================================

    async def close(self):
        await self._client.aclose()


class ESP32Simulator:
    """
    Giả lập ESP32 bằng webcam (khi không có phần cứng).
    """

    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(camera_index)
        self._connected = self.cap.isOpened()
        self._alarm_active = False
        self.ip_address = "simulator"

        if self._connected:
            print("[SIM] ✅ Webcam simulator ready")
        else:
            print("[SIM] ⚠️ Cannot open webcam!")

    @property
    def is_connected(self):
        return self._connected

    @property
    def is_configured(self):
        return True

    async def check_connection(self):
        return self._connected

    async def capture_frame(self):
        if not self._connected:
            return None
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)  # Mirror
        return frame if ret else None

    def get_stream_url(self):
        return ""  # Webcam doesn't have HTTP stream

    async def lcd_display(self, line1="", line2=""):
        print(f"[LCD] {line1} | {line2}")

    async def lcd_idle(self):
        await self.lcd_display("SMART ATTEND", "Scan face...")

    async def lcd_recognized(self, name, mssv):
        await self.lcd_display(name, mssv)

    async def lcd_unknown(self):
        await self.lcd_display("UNKNOWN", "ACCESS DENY")

    async def lcd_already(self):
        await self.lcd_display("DA DIEM DANH", "Vui long cho...")

    async def lcd_room_locked(self):
        await self.lcd_display("PHONG DA KHOA", "Comeback tomorrow")

    async def relay_open(self, duration=3):
        print(f"[RELAY] 🔓 OPEN ({duration}s)")
        return True

    async def buzzer_beep(self, pattern="ok"):
        print(f"[BUZZER] 🔊 {pattern}")

    async def buzzer_alarm(self):
        self._alarm_active = True
        print("[BUZZER] 🚨 ALARM!")

    async def buzzer_alarm_timed(self, duration=30):
        self._alarm_active = True
        print(f"[BUZZER] 🚨 ALARM! (tự tắt sau {duration}s)")

    async def buzzer_stop(self):
        self._alarm_active = False
        print("[BUZZER] 🔇 STOPPED")

    def configure(self, ip, port=80, stream_port=81):
        pass

    async def close(self):
        if self.cap:
            self.cap.release()
