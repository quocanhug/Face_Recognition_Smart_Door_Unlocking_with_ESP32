"""
=============================================================
 ESP32 CONTROLLER - Giao tiếp với ESP32-S3
=============================================================
 Điều khiển ESP32-S3 qua HTTP (cải thiện kết nối v3):
   - Lấy ảnh từ camera (snapshot hoặc MJPEG stream)
   - Điều khiển LCD1602 I2C
   - Điều khiển Relay (mở khóa cửa)
   - Điều khiển Buzzer

 Cải thiện kết nối v3 — FIX CONNECTION LOSS:
   - MỌI request (LCD/Buzzer/Relay) đều qua background queue
     → Đảm bảo chỉ 1 request tại 1 thời điểm tới ESP32
   - Relay dùng threading.Event để chờ kết quả (vẫn sync từ caller)
   - Session riêng cho capture (main thread) vs control (bg thread)
   - Delay 200ms giữa các request liên tiếp tránh flood ESP32
   - Timeout ngắn hơn cho non-critical (3s)
=============================================================
"""

import cv2
import time
import numpy as np
import requests
import threading
import queue
import unicodedata
from requests.adapters import HTTPAdapter


class ESP32Controller:
    """
    Giao tiếp với ESP32-S3 qua HTTP (Robust Connection v3).

    FIX: Mọi request control (LCD/Relay/Buzzer) đều serialize qua 1 queue
    → tránh flood ESP32 → không bị mất kết nối sau người đầu tiên.

    ESP32-S3 cần chạy firmware web server với các endpoint:
        GET  /capture          → Chụp ảnh JPEG
        GET  /stream           → MJPEG stream
        POST /lcd              → Điều khiển LCD
        POST /relay            → Điều khiển relay
        POST /buzzer           → Điều khiển buzzer
        GET  /status           → Trạng thái hệ thống

    Sử dụng:
        esp = ESP32Controller("192.168.1.100")
        frame = esp.capture()
        esp.lcd_display("Quoc Anh", "MSSV: 123456")
        esp.relay_open(duration=3)
    """

    def __init__(self, ip_address, port=80, stream_port=81, timeout=5):
        """
        Args:
            ip_address: IP của ESP32-S3 (vd: "192.168.1.100")
            port: Port web server (mặc định 80)
            stream_port: Port MJPEG stream (mặc định 81)
            timeout: Timeout cho HTTP requests (giây)
        """
        self.base_url = f"http://{ip_address}:{port}"
        self.stream_url = f"http://{ip_address}:{stream_port}"
        self.timeout = timeout
        self._connected = False

        # ===== Session cho CAPTURE (main thread only) =====
        self._capture_session = self._create_session()

        # ===== Session cho CONTROL (background thread only) =====
        self._control_session = self._create_session()

        # ===== Session cho check_connection (main thread) =====
        self._check_session = self._create_session()

        # ===== Background queue — MỌI control request qua đây =====
        # Đảm bảo chỉ 1 request tại 1 thời điểm tới ESP32
        self._bg_queue = queue.Queue(maxsize=50)
        self._bg_thread = threading.Thread(
            target=self._bg_worker, daemon=True
        )
        self._bg_thread.start()

        # ===== Rate limiting =====
        self._last_request_time = {}       # endpoint → timestamp
        self._min_interval = {
            "/lcd": 0.8,        # LCD cập nhật tối đa ~1 lần/s
            "/buzzer": 0.8,     # Buzzer cách nhau 0.8s
            "/relay": 1.0,      # Relay cách nhau 1s
            "/capture": 0.05,   # Capture nhanh ~20fps
        }

        # ===== Delay giữa các request liên tiếp =====
        self._inter_request_delay = 0.25   # 250ms giữa mỗi request

        # ===== Alarm timer (auto-stop sau N giây) =====
        self._alarm_timer = None

        print(f"[ESP32] Target: {self.base_url}")
        print(f"[ESP32] Stream: {self.stream_url}")
        print(f"[ESP32] Connection: close, serialized queue")

    @staticmethod
    def _create_session():
        """Tạo requests.Session với Connection: close cho ESP32."""
        session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=0,
            pool_connections=1,
            pool_maxsize=1,
            pool_block=False,
        )
        session.mount("http://", adapter)
        session.headers.update({
            "Connection": "close",
        })
        return session

    # ========================================
    # BACKGROUND WORKER — SERIALIZED REQUESTS
    # ========================================

    def _bg_worker(self):
        """
        Thread xử lý TẤT CẢ control requests (LCD/Buzzer/Relay).
        Chỉ 1 request tại 1 thời điểm → tránh flood ESP32.
        """
        while True:
            try:
                task = self._bg_queue.get(timeout=1)
                if task is None:
                    break  # Shutdown signal

                method, url, kwargs, result_event, result_holder = task

                try:
                    if method == "POST":
                        resp = self._control_session.post(url, **kwargs)
                    else:
                        resp = self._control_session.get(url, **kwargs)
                    resp.close()

                    success = resp.status_code == 200
                    if not success:
                        print(f"[ESP32-BG] {url} error: {resp.status_code}")

                    # Trả kết quả nếu caller đang chờ
                    if result_holder is not None:
                        result_holder[0] = success

                except requests.exceptions.RequestException as e:
                    print(f"[ESP32-BG] {url} failed (skip): "
                          f"{type(e).__name__}")
                    if result_holder is not None:
                        result_holder[0] = False

                finally:
                    # Signal cho caller đang chờ (nếu có)
                    if result_event is not None:
                        result_event.set()
                    self._bg_queue.task_done()

                # === DELAY giữa các request ===
                # Cho ESP32 thời gian đóng socket + xử lý
                time.sleep(self._inter_request_delay)

            except queue.Empty:
                continue
            except Exception:
                continue

    def _send_bg(self, method, endpoint, wait=False, **kwargs):
        """
        Gửi request qua background queue.

        Args:
            method: "POST" hoặc "GET"
            endpoint: "/lcd", "/relay", "/buzzer"
            wait: True = chờ kết quả (cho relay), False = fire-and-forget
            **kwargs: requests kwargs (json, timeout, ...)

        Returns:
            True/False nếu wait=True, luôn True nếu wait=False
        """
        url = f"{self.base_url}{endpoint}"

        # Rate limiting (chỉ cho non-wait requests)
        if not wait:
            now = time.time()
            min_interval = self._min_interval.get(endpoint, 0.1)
            last = self._last_request_time.get(endpoint, 0)
            if now - last < min_interval:
                return True  # Skip, quá nhanh
            self._last_request_time[endpoint] = now

        # Set timeout mặc định
        if "timeout" not in kwargs:
            kwargs["timeout"] = 3.0 if not wait else self.timeout

        # Tạo event + result holder cho sync wait
        result_event = threading.Event() if wait else None
        result_holder = [False] if wait else None

        try:
            # Xóa request CŨ cùng endpoint nếu queue có nhiều
            # (chỉ cho non-wait, tránh xóa relay)
            if not wait and self._bg_queue.qsize() > 5:
                self._flush_queue_for_endpoint(endpoint)

            self._bg_queue.put_nowait(
                (method, url, kwargs, result_event, result_holder)
            )
        except queue.Full:
            if wait:
                # Relay quan trọng → chờ queue trống
                try:
                    self._bg_queue.put(
                        (method, url, kwargs, result_event, result_holder),
                        timeout=3
                    )
                except queue.Full:
                    return False
            else:
                return True  # Drop non-critical

        if wait:
            # Chờ kết quả từ background worker
            result_event.wait(timeout=self.timeout + 2)
            return result_holder[0]

        return True

    def _flush_queue_for_endpoint(self, endpoint):
        """Xóa các request cũ cho cùng endpoint (giữ lại mới nhất)."""
        items = []
        try:
            while True:
                items.append(self._bg_queue.get_nowait())
                self._bg_queue.task_done()
        except queue.Empty:
            pass

        # Giữ lại tất cả trừ request cũ cùng endpoint
        for item in items:
            _, url, _, _, _ = item
            if endpoint not in url:
                try:
                    self._bg_queue.put_nowait(item)
                except queue.Full:
                    break

    # ========================================
    # KẾT NỐI
    # ========================================

    def check_connection(self):
        """Kiểm tra kết nối ESP32-S3."""
        try:
            resp = self._check_session.get(
                f"{self.base_url}/status",
                timeout=5.0
            )
            resp.close()
            if resp.status_code == 200:
                self._connected = True
                print(f"[ESP32] ✅ Kết nối OK!")
                return True
        except requests.exceptions.RequestException:
            pass

        # Thử endpoint capture
        try:
            resp = self._check_session.get(
                f"{self.base_url}/capture",
                timeout=3
            )
            resp.close()
            if resp.status_code == 200:
                self._connected = True
                print(f"[ESP32] ✅ Kết nối OK (qua /capture)")
                return True
        except requests.exceptions.RequestException:
            pass

        self._connected = False
        print(f"[ESP32] ❌ Không kết nối được: {self.base_url}")
        return False

    @property
    def is_connected(self):
        return self._connected

    # ========================================
    # CAMERA (dùng _capture_session riêng)
    # ========================================

    def capture(self):
        """
        Chụp 1 frame từ ESP32-S3 camera.
        Dùng session riêng, không conflict với control requests.

        Returns:
            frame: numpy array BGR (OpenCV format), None nếu lỗi
        """
        try:
            resp = self._capture_session.get(
                f"{self.base_url}/capture",
                timeout=self.timeout
            )

            if resp.status_code != 200:
                return None

            # Decode JPEG → OpenCV BGR
            img_array = np.array(bytearray(resp.content), dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            resp.close()
            return frame

        except requests.exceptions.RequestException:
            return None

    def open_stream(self):
        """
        Mở MJPEG stream từ ESP32-S3.

        Returns:
            Generator yield frame BGR mỗi lần đọc.
        """
        stream_url = f"{self.stream_url}/stream"
        try:
            resp = self._capture_session.get(
                stream_url, stream=True, timeout=10
            )
            if resp.status_code != 200:
                print(f"[ESP32] Stream error: {resp.status_code}")
                return

            bytes_buffer = b''
            for chunk in resp.iter_content(chunk_size=4096):
                bytes_buffer += chunk

                # Tìm JPEG markers
                start = bytes_buffer.find(b'\xff\xd8')  # SOI
                end = bytes_buffer.find(b'\xff\xd9')    # EOI

                if start != -1 and end != -1 and end > start:
                    jpg_data = bytes_buffer[start:end + 2]
                    bytes_buffer = bytes_buffer[end + 2:]

                    img_array = np.array(
                        bytearray(jpg_data), dtype=np.uint8
                    )
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                    if frame is not None:
                        yield frame

        except requests.exceptions.RequestException as e:
            print(f"[ESP32] Stream disconnected: {e}")

    # ========================================
    # LCD1602 I2C (qua queue — serialized)
    # ========================================

    @staticmethod
    def _normalize_text(text):
        """Xóa dấu tiếng Việt, chuyển charset về ASCII cho LCD1602."""
        if not text:
            return ""
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        text = text.replace('đ', 'd').replace('Đ', 'D')
        return text

    def lcd_display(self, line1="", line2=""):
        """
        Hiển thị text lên LCD1602 (qua queue, không block main loop).

        Args:
            line1: Dòng 1 (tối đa 16 ký tự)
            line2: Dòng 2 (tối đa 16 ký tự)
        """
        line1 = self._normalize_text(line1)[:16]
        line2 = self._normalize_text(line2)[:16]
        self._send_bg(
            "POST", "/lcd",
            json={"line1": line1, "line2": line2},
            timeout=3.0
        )
        return True

    def lcd_display_sync(self, line1="", line2=""):
        """
        Hiển thị text lên LCD (đồng bộ, chờ response).
        Dùng khi cần chắc chắn LCD đã cập nhật.
        """
        line1 = self._normalize_text(line1)[:16]
        line2 = self._normalize_text(line2)[:16]
        return self._send_bg(
            "POST", "/lcd",
            wait=True,
            json={"line1": line1, "line2": line2},
            timeout=5.0
        )

    def lcd_idle(self):
        """Đưa LCD về trạng thái chờ."""
        self.lcd_display("SMART ATTEND", "Scan face...")

    def lcd_recognized(self, name, mssv):
        """Hiển thị khi nhận diện đúng."""
        name = self._normalize_text(name)
        mssv = self._normalize_text(mssv)
        self.lcd_display(name[:16], mssv[:16])

    def lcd_unknown(self):
        """Hiển thị khi không nhận diện được."""
        self.lcd_display("UNKNOWN", "ACCESS DENY")

    def lcd_already(self):
        """Hiển thị khi đã điểm danh rồi."""
        self.lcd_display("DA DIEM DANH", "Vui long cho...")

    # ========================================
    # RELAY (qua queue — serialized, nhưng chờ kết quả)
    # ========================================

    def relay_open(self, duration=3):
        """
        Mở relay (mở khóa cửa) trong duration giây.
        Gửi qua queue (serialized) nhưng chờ kết quả.

        Args:
            duration: Thời gian mở (giây)
        """
        for attempt in range(3):
            success = self._send_bg(
                "POST", "/relay",
                wait=True,
                json={"action": "open", "duration": duration},
                timeout=self.timeout
            )
            if success:
                print(f"[ESP32] 🔓 Relay OPEN ({duration}s)")
                return True
            else:
                print(f"[ESP32] Relay attempt {attempt+1}/3 failed")
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))

        print(f"[ESP32] ❌ Relay FAILED after 3 attempts")
        return False

    def relay_close(self):
        """Đóng relay (khóa cửa)."""
        return self._send_bg(
            "POST", "/relay",
            wait=True,
            json={"action": "close"},
            timeout=self.timeout
        )

    # ========================================
    # BUZZER (qua queue — serialized)
    # ========================================

    def buzzer_beep(self, pattern="ok"):
        """
        Kích buzzer (qua queue, không block main loop).

        Args:
            pattern: "ok" (beep ngắn), "error" (beep dài),
                     "enroll" (2 beep ngắn)
        """
        self._send_bg(
            "POST", "/buzzer",
            json={"pattern": pattern},
            timeout=3.0
        )
        return True

    def buzzer_alarm(self):
        """
        Kích buzzer alarm liên tục.
        Buzzer sẽ kêu cho đến khi gọi buzzer_stop().
        """
        self._send_bg(
            "POST", "/buzzer",
            json={"pattern": "alarm"},
            timeout=3.0
        )
        return True

    def buzzer_alarm_timed(self, duration=30):
        """
        Kích buzzer alarm, tự tắt sau duration giây.
        Nếu access granted trước khi hết thời gian → cancel timer.
        """
        # Cancel timer cũ nếu có
        if self._alarm_timer and self._alarm_timer.is_alive():
            self._alarm_timer.cancel()

        # Bật alarm
        self.buzzer_alarm()

        # Đặt timer tự tắt sau duration giây
        self._alarm_timer = threading.Timer(duration, self._auto_stop_alarm)
        self._alarm_timer.daemon = True
        self._alarm_timer.start()
        print(f"[ESP32] 🔔 Alarm sẽ tự tắt sau {duration}s")
        return True

    def _auto_stop_alarm(self):
        """Callback timer: tự tắt alarm sau thời gian."""
        print(f"[ESP32] ⏰ Alarm timeout → tự tắt")
        self.buzzer_stop()

    def buzzer_stop(self):
        """Tắt buzzer alarm + cancel timer nếu có."""
        # Cancel timer nếu đang chạy
        if self._alarm_timer and self._alarm_timer.is_alive():
            self._alarm_timer.cancel()
            self._alarm_timer = None

        self._send_bg(
            "POST", "/buzzer",
            json={"pattern": "stop"},
            timeout=3.0
        )
        return True

    def release(self):
        """Đóng HTTP session và background thread."""
        # Shutdown background worker
        try:
            self._bg_queue.put_nowait(None)
        except queue.Full:
            pass

        if self._bg_thread.is_alive():
            self._bg_thread.join(timeout=2)

        for session in [self._capture_session,
                        self._control_session,
                        self._check_session]:
            if session:
                session.close()

        print("[ESP32] Released all connections")


class ESP32Simulator:
    """
    Giả lập ESP32 khi không có phần cứng thật.
    Dùng webcam thay cho ESP32-CAM, in LCD/Relay ra console.
    """

    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(camera_index)
        self._connected = True
        self._lcd_line1 = "SMART ATTEND"
        self._lcd_line2 = "Scan face..."

        if not self.cap.isOpened():
            print("[SIM] ⚠️ Không mở được webcam!")
            self._connected = False
        else:
            print("[SIM] ✅ Webcam simulator ready")

    def check_connection(self):
        return self._connected

    @property
    def is_connected(self):
        return self._connected

    def capture(self):
        ret, frame = self.cap.read()
        return frame if ret else None

    @staticmethod
    def _normalize_text(text):
        if not text:
            return ""
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.replace('đ', 'd').replace('Đ', 'D')

    def lcd_display(self, line1="", line2=""):
        self._lcd_line1 = self._normalize_text(line1)[:16]
        self._lcd_line2 = self._normalize_text(line2)[:16]
        print(f"[LCD] ┌────────────────┐")
        print(f"[LCD] │{self._lcd_line1:<16}│")
        print(f"[LCD] │{self._lcd_line2:<16}│")
        print(f"[LCD] └────────────────┘")
        return True

    def lcd_idle(self):
        self.lcd_display("SMART ATTEND", "Scan face...")

    def lcd_recognized(self, name, mssv):
        name = self._normalize_text(name)
        mssv = self._normalize_text(mssv)
        self.lcd_display(name[:16], mssv[:16])

    def lcd_unknown(self):
        self.lcd_display("UNKNOWN", "ACCESS DENY")

    def lcd_already(self):
        self.lcd_display("DA DIEM DANH", "Vui long cho...")

    def relay_open(self, duration=3):
        print(f"[RELAY] 🔓 OPEN ({duration}s)")
        return True

    def relay_close(self):
        print(f"[RELAY] 🔒 CLOSED")
        return True

    def buzzer_beep(self, pattern="ok"):
        if pattern == "ok":
            print(f"[BUZZER] 🔊 Beep!")
        elif pattern == "error":
            print(f"[BUZZER] 🔊 BEEEEEP!")
        return True

    def buzzer_alarm(self):
        print(f"[BUZZER] 🚨 ALARM! (continuous until stop)")
        return True

    def buzzer_alarm_timed(self, duration=30):
        print(f"[BUZZER] 🚨 ALARM! (tự tắt sau {duration}s)")
        return True

    def buzzer_stop(self):
        print(f"[BUZZER] 🔇 ALARM STOPPED")
        return True

    def release(self):
        if self.cap:
            self.cap.release()
