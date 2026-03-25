"""
=============================================================
 SMART ATTENDANCE - FastAPI Web Server
=============================================================
 REST API + WebSocket + Background Recognition Loop.
 
 Chạy:
   cd web/backend
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   
 Hoặc:
   python main.py
=============================================================
"""

import os
import sys
import asyncio
import time
import json
import cv2
import numpy as np
from datetime import datetime, date
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from database import engine, SessionLocal, get_db
from models import Base, User, FaceEmbedding, AttendanceLog
from schemas import (
    UserCreate, UserResponse, UserListResponse,
    AttendanceLogResponse, AttendanceListResponse,
    SecurityConfigSchema, SystemStatus, WSEvent
)

# ============================================
# GLOBALS
# ============================================

# Services (initialized in lifespan)
face_service = None
esp32 = None
security = None

# State
recognition_active = False
start_time = time.time()
last_unknown_time = 0
UNKNOWN_COOLDOWN = 5.0
DEBOUNCE_SECONDS = 30
_last_attendance = {}  # {user_id: timestamp}

# Latest detection results for stream overlay
_latest_detections = []  # [{bbox, name, mssv, confidence, status}]
_latest_frame = None     # Last captured frame
_detections_timestamp = 0       # Thời điểm cập nhật detections
DETECTION_EXPIRE_SEC = 2.0      # Overlay biến mất sau 2s không có update

# WebSocket clients
ws_clients: list[WebSocket] = []


# ============================================
# LIFESPAN (startup/shutdown)
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global face_service, esp32, security, recognition_active

    # === STARTUP ===
    print("\n" + "=" * 55)
    print("  SMART ATTENDANCE - Web Server")
    print("=" * 55)

    # Create tables
    Base.metadata.create_all(bind=engine)
    print("[DB] ✅ Tables ready")

    # Init Face Service
    from face_service import FaceService
    face_service = FaceService.get_instance()

    # Load embeddings cache
    _refresh_face_cache()

    # Init ESP32
    esp32_ip = os.environ.get("ESP32_IP", "")
    if esp32_ip:
        from esp32_service import ESP32Service
        esp32 = ESP32Service(esp32_ip)
        await esp32.check_connection()
    else:
        from esp32_service import ESP32Simulator
        esp32 = ESP32Simulator(
            camera_index=int(os.environ.get("CAMERA_INDEX", "0"))
        )
        await esp32.check_connection()

    # Init Security
    from security_service import SecurityService
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "cv", "security_config.json"
    )
    security = SecurityService(config_path)

    # Start recognition loop
    recognition_active = True
    asyncio.create_task(recognition_loop())

    print(f"\n[SERVER] ✅ Ready! http://localhost:8000")
    print(f"[SERVER] ESP32: {esp32.ip_address}")
    print("=" * 55 + "\n")

    yield

    # === SHUTDOWN ===
    recognition_active = False
    if esp32:
        await esp32.close()
    if security:
        await security.close()
    print("[SERVER] Shutdown complete")


# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="Smart Attendance System",
    version="2.0",
    lifespan=lifespan
)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# ============================================
# HELPERS
# ============================================

def _refresh_face_cache():
    """Load tất cả embeddings từ DB vào cache."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        user_embs = {}
        for user in users:
            embs = [fe.get_vector() for fe in user.embeddings]
            if embs:
                user_embs[user.id] = embs
        face_service.update_cache(user_embs)
    finally:
        db.close()


async def _broadcast_ws(event: str, data: dict):
    """Gửi WebSocket event tới tất cả clients."""
    message = json.dumps({"event": event, "data": data})
    disconnected = []
    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        ws_clients.remove(ws)


# ============================================
# RECOGNITION LOOP (background task)
# ============================================

async def recognition_loop():
    """
    Vòng lặp chính: fetch frame → detect → recognize → log.
    Chạy trong asyncio task.
    """
    global last_unknown_time

    print("[LOOP] Recognition loop started")
    await asyncio.sleep(2)  # Chờ khởi tạo xong

    while recognition_active:
        try:
            # Capture frame
            frame = await esp32.capture_frame()
            if frame is None:
                await asyncio.sleep(0.2)
                continue

            global _latest_frame, _latest_detections
            _latest_frame = frame.copy()

            # Run AI (CPU-bound → run in executor)
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, face_service.detect_and_recognize, frame
            )

            if face_service.cache_dirty:
                _refresh_face_cache()

            # Build detection overlay data
            detections = []

            # Process results
            known = [r for r in results if r["user_id"] >= 0]
            unknown = [r for r in results
                       if r["user_id"] < 0 and r["embedding"] is not None]

            # === KNOWN FACES ===
            for r in known:
                user_id = r["user_id"]
                now = time.time()

                # Debounce
                if user_id in _last_attendance:
                    if now - _last_attendance[user_id] < DEBOUNCE_SECONDS:
                        # Vẫn hiển thị overlay cho user đã điểm danh
                        db_tmp = SessionLocal()
                        try:
                            user_tmp = db_tmp.get(User, user_id)
                            if user_tmp:
                                detections.append({
                                    "bbox": r.get("box", []),
                                    "name": user_tmp.name,
                                    "mssv": user_tmp.mssv,
                                    "confidence": r["confidence"],
                                    "status": "ALREADY"
                                })
                        finally:
                            db_tmp.close()

                        # Feedback: đã điểm danh rồi
                        await esp32.lcd_already()
                        await _broadcast_ws("already", {
                            "user_id": user_id,
                            "timestamp": datetime.now().isoformat()
                        })
                        continue

                # Get user info
                db = SessionLocal()
                try:
                    user = db.get(User, user_id)
                    if not user:
                        continue

                    # === KIỂM TRA ROOM LOCK ===
                    if security.is_room_locked:
                        detections.append({
                            "bbox": r.get("box", []),
                            "name": user.name,
                            "mssv": user.mssv,
                            "confidence": r["confidence"],
                            "status": "LOCKED"
                        })

                        # LCD message khác nhau tùy lý do khóa
                        if security.lock_reason == "night":
                            now_str = datetime.now().strftime("%H:%M")
                            await esp32.lcd_display(now_str, "Comeback tomorrow")
                        else:
                            await esp32.lcd_room_locked()

                        await esp32.buzzer_beep("error")
                        print(f"[🔒] {user.name} - Phòng đang khóa ({security.lock_reason})!")

                        # Broadcast WS
                        await _broadcast_ws("room_lock_denied", {
                            "user_name": user.name,
                            "mssv": user.mssv,
                            "timestamp": datetime.now().isoformat()
                        })
                        continue  # Không mở relay

                    _last_attendance[user_id] = now

                    # Store detection for overlay
                    detections.append({
                        "bbox": r.get("box", []),
                        "name": user.name,
                        "mssv": user.mssv,
                        "confidence": r["confidence"],
                        "status": "GRANTED"
                    })

                    # Log attendance
                    log = AttendanceLog(
                        user_id=user.id,
                        user_name=user.name,
                        mssv=user.mssv,
                        status="GRANTED",
                        confidence=r["confidence"]
                    )
                    db.add(log)
                    db.commit()

                    print(f"[✅] {user.name} ({user.mssv}) - "
                          f"{r['confidence']*100:.0f}%")

                    # ESP32 actions
                    await esp32.lcd_recognized(user.name, user.mssv)
                    await esp32.relay_open(3)
                    await esp32.buzzer_beep("ok")

                    # Security: access granted
                    grant_result = await security.on_access_granted(esp32)

                    # WebSocket broadcast
                    await _broadcast_ws("attendance", {
                        "user_name": user.name,
                        "mssv": user.mssv,
                        "status": "GRANTED",
                        "confidence": round(r["confidence"] * 100, 1),
                        "timestamp": datetime.now().isoformat(),
                        "alarm_stopped": grant_result.get("alarm_stopped", False)
                    })

                finally:
                    db.close()

            # === UNKNOWN FACES ===
            for u in unknown:
                detections.append({
                    "bbox": u.get("box", []),
                    "name": "Unknown",
                    "mssv": "",
                    "confidence": u.get("confidence", 0),
                    "status": "DENIED"
                })

            if unknown and not known:
                now = time.time()
                if now - last_unknown_time >= UNKNOWN_COOLDOWN:
                    last_unknown_time = now

                    await esp32.lcd_unknown()
                    await esp32.buzzer_beep("error")

                    # Security: access deny
                    deny_result = await security.on_access_deny(esp32)

                    # Log deny
                    db = SessionLocal()
                    try:
                        log = AttendanceLog(
                            status="DENIED",
                            confidence=unknown[0]["confidence"]
                        )
                        db.add(log)
                        db.commit()
                    finally:
                        db.close()

                    # WebSocket broadcast
                    await _broadcast_ws("security_alert", {
                        "status": "DENIED",
                        "deny_count": security.deny_count,
                        "mode": security.mode_name,
                        "alarm_active": security.is_alarm_active,
                        "action": deny_result.get("action", ""),
                        "timestamp": datetime.now().isoformat()
                    })

            # Update overlay detections + timestamp
            _latest_detections = detections
            _detections_timestamp = time.time()

            # Pace the loop
            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[LOOP] Error: {e}")
            await asyncio.sleep(2)

    print("[LOOP] Recognition loop stopped")


# ============================================
# ROUTES: Frontend
# ============================================

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve main dashboard."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Smart Attendance</h1><p>Frontend not found</p>")


# ============================================
# ROUTES: Users API
# ============================================

@app.get("/api/users", response_model=UserListResponse)
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    return UserListResponse(
        users=[UserResponse(
            id=u.id, name=u.name, mssv=u.mssv,
            face_count=u.face_count, created_at=u.created_at
        ) for u in users],
        total=len(users)
    )


@app.post("/api/users", response_model=UserResponse)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.mssv == data.mssv).first()
    if existing:
        raise HTTPException(400, f"MSSV {data.mssv} đã tồn tại")

    user = User(name=data.name, mssv=data.mssv)
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id, name=user.name, mssv=user.mssv,
        face_count=0, created_at=user.created_at
    )


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    db.delete(user)
    db.commit()
    face_service.invalidate_cache()

    return {"status": "ok", "message": f"Đã xóa {user.name}"}

@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: dict, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    if "name" in data and data["name"].strip():
        user.name = data["name"].strip()
    if "mssv" in data and data["mssv"].strip():
        user.mssv = data["mssv"].strip()

    db.commit()
    face_service.invalidate_cache()

    return {"status": "ok", "message": f"Đã cập nhật {user.name}", "user": {
        "id": user.id, "name": user.name, "mssv": user.mssv
    }}


@app.post("/api/users/{user_id}/enroll")
async def enroll_user(user_id: int, db: Session = Depends(get_db)):
    """Chụp ảnh từ ESP32/webcam và enroll face."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    frame = await esp32.capture_frame()
    if frame is None:
        raise HTTPException(500, "Không chụp được ảnh từ camera")

    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        None, face_service.extract_embedding, frame, None
    )

    if embedding is None:
        raise HTTPException(400, "Không phát hiện khuôn mặt trong ảnh")

    # Save embedding
    fe = FaceEmbedding(
        user_id=user.id,
        embedding=FaceEmbedding.from_vector(embedding)
    )
    db.add(fe)
    db.commit()

    face_service.invalidate_cache()

    return {
        "status": "ok",
        "message": f"Enroll thành công cho {user.name}",
        "face_count": user.face_count
    }


# ============================================
# ROUTES: Attendance API
# ============================================

@app.get("/api/attendance/today", response_model=AttendanceListResponse)
def get_today_attendance(db: Session = Depends(get_db)):
    today = date.today()
    logs = db.query(AttendanceLog).filter(
        AttendanceLog.timestamp >= datetime.combine(today, datetime.min.time())
    ).order_by(AttendanceLog.timestamp.desc()).all()

    return AttendanceListResponse(
        logs=[AttendanceLogResponse(
            id=l.id, user_name=l.user_name, mssv=l.mssv,
            timestamp=l.timestamp, status=l.status,
            confidence=l.confidence
        ) for l in logs],
        total=len(logs),
        date=today.isoformat()
    )


@app.get("/api/attendance/history")
def get_attendance_history(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    from datetime import timedelta
    since = datetime.now() - timedelta(days=days)
    logs = db.query(AttendanceLog).filter(
        AttendanceLog.timestamp >= since
    ).order_by(AttendanceLog.timestamp.desc()).limit(500).all()

    return {
        "logs": [AttendanceLogResponse(
            id=l.id, user_name=l.user_name, mssv=l.mssv,
            timestamp=l.timestamp, status=l.status,
            confidence=l.confidence
        ).model_dump() for l in logs],
        "total": len(logs),
        "since": since.isoformat()
    }


# ============================================
# ROUTES: Stream Proxy
# ============================================

def _draw_overlay(frame):
    """Vẽ bounding box + thông tin lên frame."""
    overlay = frame.copy()

    # Không vẽ gì nếu detections đã quá cũ (người đã rời đi)
    if _detections_timestamp > 0 and time.time() - _detections_timestamp > DETECTION_EXPIRE_SEC:
        return overlay

    for det in _latest_detections:
        bbox = det.get("bbox", [])
        if len(bbox) < 4:
            continue

        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        status = det["status"]
        if status == "GRANTED":
            color = (0, 200, 0)    # Xanh lá
        elif status == "ALREADY":
            color = (255, 200, 0)  # Xanh dương nhạt (đã điểm danh)
        else:
            color = (0, 0, 255)    # Đỏ (denied/locked)

        # Draw rectangle
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)

        # Draw corner accents
        corner_len = min(20, abs(x2-x1)//4)
        thick = 3
        # Top-left
        cv2.line(overlay, (x1, y1), (x1+corner_len, y1), color, thick)
        cv2.line(overlay, (x1, y1), (x1, y1+corner_len), color, thick)
        # Top-right
        cv2.line(overlay, (x2, y1), (x2-corner_len, y1), color, thick)
        cv2.line(overlay, (x2, y1), (x2, y1+corner_len), color, thick)
        # Bottom-left
        cv2.line(overlay, (x1, y2), (x1+corner_len, y2), color, thick)
        cv2.line(overlay, (x1, y2), (x1, y2-corner_len), color, thick)
        # Bottom-right
        cv2.line(overlay, (x2, y2), (x2-corner_len, y2), color, thick)
        cv2.line(overlay, (x2, y2), (x2, y2-corner_len), color, thick)

        # Prepare label
        name = det.get("name", "")
        mssv = det.get("mssv", "")
        conf = det.get("confidence", 0)
        label = f"{name}"
        if mssv:
            label += f" - {mssv}"
        label += f" {conf*100:.0f}%"

        # Draw label background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, 1)
        label_y = max(y1 - 8, th + 8)
        cv2.rectangle(overlay, (x1, label_y - th - 6), (x1 + tw + 8, label_y + 4), color, -1)
        cv2.putText(overlay, label, (x1 + 4, label_y - 2), font, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

    return overlay


@app.get("/api/stream")
async def stream_proxy():
    """Proxy MJPEG stream với face detection overlay."""
    async def generate():
        while True:
            frame = await esp32.capture_frame()
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            # Draw face detection overlay
            annotated = _draw_overlay(frame)

            _, jpeg = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                jpeg.tobytes() +
                b"\r\n"
            )
            await asyncio.sleep(0.05)  # ~20fps

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/snapshot")
async def get_snapshot():
    """Chụp 1 ảnh JPEG."""
    frame = await esp32.capture_frame()
    if frame is None:
        raise HTTPException(500, "Cannot capture frame")

    _, jpeg = cv2.imencode('.jpg', frame)
    return StreamingResponse(
        iter([jpeg.tobytes()]),
        media_type="image/jpeg"
    )


# ============================================
# ROUTES: Security API
# ============================================

@app.get("/api/security/config")
def get_security_config():
    return security.config


@app.put("/api/security/config")
def update_security_config(data: SecurityConfigSchema):
    security.update_config(data.model_dump())
    return {"status": "ok", "config": security.config}


@app.post("/api/security/lock")
async def lock_room():
    """Khóa phòng từ xa."""
    security.lock_room()
    await _broadcast_ws("room_lock", {
        "locked": True,
        "timestamp": datetime.now().isoformat()
    })
    return {"status": "ok", "locked": True}


@app.post("/api/security/unlock")
async def unlock_room():
    """Mở khóa phòng."""
    security.unlock_room()
    await _broadcast_ws("room_lock", {
        "locked": False,
        "timestamp": datetime.now().isoformat()
    })
    return {"status": "ok", "locked": False}


@app.get("/api/security/lock-status")
def get_lock_status():
    """Trạng thái khóa phòng."""
    return {
        "locked": security.is_room_locked if security else False
    }


# ============================================
# ROUTES: System Status
# ============================================

@app.get("/api/status")
async def get_status(db: Session = Depends(get_db)):
    users_count = db.query(User).count()
    today = date.today()
    today_count = db.query(AttendanceLog).filter(
        AttendanceLog.timestamp >= datetime.combine(today, datetime.min.time()),
        AttendanceLog.status == "GRANTED"
    ).count()

    return SystemStatus(
        esp32_connected=esp32.is_connected if esp32 else False,
        esp32_ip=esp32.ip_address if esp32 else None,
        recognition_active=recognition_active,
        users_count=users_count,
        today_attendance=today_count,
        security_mode=security.mode_name if security else "UNKNOWN",
        deny_count=security.deny_count if security else 0,
        alarm_active=security.is_alarm_active if security else False,
        room_locked=security.is_room_locked if security else False,
        uptime_seconds=int(time.time() - start_time)
    )


# ============================================
# WEBSOCKET
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    print(f"[WS] Client connected ({len(ws_clients)} total)")

    try:
        while True:
            # Keep alive + receive commands
            data = await websocket.receive_text()
            # Clients có thể gửi commands nếu cần
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps({"event": "pong", "data": {}})
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in ws_clients:
            ws_clients.remove(websocket)
        print(f"[WS] Client disconnected ({len(ws_clients)} total)")


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(
        description="Smart Attendance Web Server"
    )
    parser.add_argument(
        "--esp32", type=str, default="",
        help="IP address of ESP32-S3"
    )
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Webcam index for simulator mode"
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="Server host"
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Server port"
    )
    args = parser.parse_args()

    # Pass config via environment variables
    if args.esp32:
        os.environ["ESP32_IP"] = args.esp32
    os.environ["CAMERA_INDEX"] = str(args.camera)

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info"
    )
