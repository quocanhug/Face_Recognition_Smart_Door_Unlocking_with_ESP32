# 🎓 Smart Attendance System v2.0

Hệ thống điểm danh thông minh sử dụng **nhận diện khuôn mặt AI** kết hợp **IoT (ESP32-S3)**, quản lý qua **Web Dashboard** real-time.

---

## 📋 Tổng Quan

| Thành phần | Công nghệ |
|---|---|
| **AI Engine** | YOLOv8 (Face Detection) + FaceNet 512-d (Recognition) |
| **Backend** | FastAPI + SQLAlchemy + WebSocket |
| **Frontend** | HTML/CSS/JS (Dark Theme, Single-Page App) |
| **IoT** | ESP32-S3 (Camera + LCD1602 + Relay + Buzzer) |
| **Database** | SQLite (có thể đổi PostgreSQL) |
| **Notification** | Telegram Bot API |

---

## 🏗️ Kiến Trúc Hệ Thống

```
┌─────────────────────────────────────────────────┐
│                  Web Browser                    │
│   Dashboard │ Lịch sử │ Quản lý Users           │
│   WebSocket (real-time) + REST API              │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│               FastAPI Web Server                 │
│  ┌───────────┐ ┌───────────┐ ┌─────────────────┐ │
│  │FaceService│ │SecuritySvc│ │ ESP32 Service   │ │
│  │YOLOv8     │ │Day/Night  │ │ HTTP → ESP32    │ │
│  │FaceNet    │ │AutoLock   │ │ Camera/LCD/     │ │
│  │Cosine Sim │ │Telegram   │ │ Relay/Buzzer    │ │
│  └───────────┘ └───────────┘ └─────────────────┘ │
│            SQLite (users, embeddings, logs)      │
└──────────────────────┬───────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────┐
│              ESP32-S3 (Firmware)                │
│  OV2640 Camera │ LCD1602 │ Relay │ Buzzer       │
└─────────────────────────────────────────────────┘
```

---

## 📁 Cấu Trúc Thư Mục

```
pro (4)/
├── web/                        # Web Application
│   ├── backend/
│   │   ├── main.py             # FastAPI server + Recognition loop
│   │   ├── face_service.py     # AI: YOLOv8 + FaceNet 512-d
│   │   ├── esp32_service.py    # ESP32 HTTP client + Simulator
│   │   ├── security_service.py # Day/Night, Auto-lock, Telegram
│   │   ├── database.py         # SQLAlchemy engine/session
│   │   ├── models.py           # DB schema (User, FaceEmbedding, Log)
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── migrate_pkl.py      # Migration tool (pkl → SQLite)
│   │   └── requirements.txt    # Python dependencies
│   └── frontend/
│       ├── index.html           # Dashboard SPA
│       ├── css/style.css        # Dark theme UI
│       └── js/app.js            # WebSocket + REST client
├── firmware/
│   ├── firmware.ino             # ESP32-S3 Arduino firmware
│   ├── camera_pins.h            # Pin definitions
│   └── requirements.txt         # PlatformIO libraries
├── cv/                          # CV module (standalone)
│   ├── main.py                  # Standalone CV application
│   ├── face_processor.py        # Face detection/recognition
│   ├── esp32_controller.py      # ESP32 controller (sync)
│   ├── security_manager.py      # Security manager (sync)
│   ├── notifier.py              # Telegram notifier
│   ├── user_database.py         # User DB (pkl format)
│   └── yolov8n.pt               # YOLO model file
├── .gitignore
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt

### 1. Clone & Cài dependencies

```bash
cd web/backend
pip install -r requirements.txt
```

### 2. Chạy server

**Với webcam (không cần ESP32):**
```bash
cd web/backend
python main.py
```

**Với ESP32:**
```bash
ESP32_IP=192.168.1.xxx python main.py
```

**Chọn webcam khác:**
```bash
CAMERA_INDEX=1 python main.py
```

### 3. Mở Dashboard

```
http://localhost:8000
```

---

## 🎯 Tính Năng

### 📹 Nhận Diện Khuôn Mặt
- **YOLOv8** phát hiện khuôn mặt real-time
- **FaceNet 512-d** trích xuất embedding vector
- **Cosine similarity** + L2 distance (weighted 70%-30%)
- Ngưỡng nhận diện: **80%** confidence
- Debounce: **30 giây** giữa 2 lần điểm danh cùng người
- Cooldown stranger: **5 giây** giữa các cảnh báo unknown

### 🌐 Web Dashboard
- **Live Camera** với face bounding box overlay (tên - MSSV + confidence%)
- **Điểm danh real-time** qua WebSocket
- **Thống kê**: Users, Hôm nay, Security Mode, Uptime
- **Lịch sử điểm danh**: lọc theo 1/3/7/14/30 ngày
- **Quản lý Users**: Thêm / Sửa (✏️) / Xóa / Enroll face (📸)
- **Dark theme** responsive

### 🔒 Bảo Mật
- **Day/Night mode** tự động theo giờ cấu hình
- **Auto-lock ban đêm**: phòng tự khóa khi vào chế độ đêm
  - Người quen đến → LCD hiện giờ + "Quay lai ngay mai"
  - Khóa thủ công → LCD hiện "PHONG DA KHOA" + "Quay lai hom sau"
- **Khóa phòng từ xa** qua nút trên dashboard
- **Deny counter**: sau N lần denied → cảnh báo Telegram + buzzer alarm 30s
- **Telegram alerts**: gửi cảnh báo khi có người lạ xâm nhập

### 🔌 ESP32-S3 IoT
- **OV2640 Camera**: chụp ảnh + MJPEG stream
- **LCD1602 I2C**: hiển thị trạng thái, tên người, giờ
- **Relay**: mở khóa cửa 3 giây khi nhận diện thành công
- **Buzzer**: beep OK / error / alarm patterns
- **HTTP API**: `/capture`, `/lcd`, `/relay`, `/buzzer`, `/status`

---

## ⚙️ Cấu Hình

### Security Config (`security_service.py`)

```python
{
    "night_start_hour": 17,      # Bắt đầu chế độ đêm
    "night_end_hour": 6,         # Kết thúc chế độ đêm
    "deny_threshold": 2,         # Số lần deny → cảnh báo
    "auto_lock_night": True,     # Tự khóa phòng ban đêm
    "telegram_bot_token": "",    # Telegram Bot Token
    "telegram_chat_id": "",      # Telegram Chat ID
    "enable_notification": True, # Bật/tắt Telegram
    "enable_night_alarm": True   # Bật/tắt alarm ban đêm
}
```

Có thể tạo file `cv/security_config.json` để override config mặc định.

### Environment Variables

| Biến | Mô tả | Mặc định |
|---|---|---|
| `ESP32_IP` | IP của ESP32-S3 | `""` (dùng webcam simulator) |
| `CAMERA_INDEX` | Index webcam (simulator mode) | `0` |

---

## 🔗 API Endpoints

### Users
| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/api/users` | Danh sách users |
| `POST` | `/api/users` | Tạo user mới |
| `PUT` | `/api/users/{id}` | Sửa thông tin user (giữ face data) |
| `DELETE` | `/api/users/{id}` | Xóa user |
| `POST` | `/api/users/{id}/enroll` | Enroll face (chụp ảnh) |

### Attendance
| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/api/attendance/today` | Điểm danh hôm nay |
| `GET` | `/api/attendance/history?days=7` | Lịch sử (1-90 ngày) |

### Security
| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/api/security/config` | Xem config bảo mật |
| `PUT` | `/api/security/config` | Cập nhật config |
| `POST` | `/api/security/lock` | Khóa phòng thủ công |
| `POST` | `/api/security/unlock` | Mở khóa phòng |

### System
| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/api/status` | Trạng thái hệ thống |
| `GET` | `/api/stream` | MJPEG video stream |
| `WS`  | `/ws` | WebSocket real-time events |

---

## 📡 WebSocket Events

| Event | Mô tả |
|---|---|
| `attendance` | Điểm danh thành công (GRANTED) |
| `security_alert` | Cảnh báo DENIED + deny count |
| `room_lock` | Thay đổi trạng thái khóa phòng |
| `room_lock_denied` | Người quen bị từ chối do phòng khóa |

---

## 🔧 ESP32-S3 Firmware

### Upload firmware
1. Mở `firmware/firmware.ino` trong Arduino IDE
2. Board: **ESP32-S3 Dev Module**
3. Cấu hình WiFi trong code:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   ```
4. Upload và monitor Serial

### Hardware Connections
| Pin | Component | Mô tả |
|---|---|---|
| GPIO 1 | SDA | LCD1602 I2C Data |
| GPIO 2 | SCL | LCD1602 I2C Clock |
| GPIO 42 | Relay | Khóa cửa điện từ |
| GPIO 41 | Buzzer | Còi cảnh báo |
| Camera | OV2640 | Tích hợp ESP32-S3 CAM |

---

## 📊 Database Schema

```
users (id, name, mssv, created_at)
  │
  ├── face_embeddings (id, user_id, embedding[512-d], created_at)
  │
  └── attendance_logs (id, user_id, user_name, mssv,
                       timestamp, status, confidence)
```

- `embedding`: FaceNet 512-d vector lưu dạng binary (numpy → bytes)
- `status`: `GRANTED` | `DENIED`

---

## 🔄 Migration

Nếu có dữ liệu cũ từ hệ thống CV (file `.pkl`):

```bash
cd web/backend
python migrate_pkl.py
```

Script sẽ import users + embeddings từ `cv/user_database.pkl` vào SQLite.

---

## 📝 Ghi Chú

- **Simulator mode**: Khi không có ESP32, hệ thống tự động dùng webcam máy tính
- **Model download**: YOLOv8 và FaceNet tự download lần đầu chạy
- **LCD ký tự**: LCD1602 không hỗ trợ Unicode, text tiếng Việt tự động bỏ dấu
- **Camera ratio**: Khung hình giữ tỷ lệ 4:3 (VGA) từ ESP32
- **Browser cache**: File CSS/JS có version parameter (`?v=N`) để busting cache

---

## 👥 Tác Giả

Dự án IoT - Hệ thống điểm danh thông minh bằng nhận diện khuôn mặt.
