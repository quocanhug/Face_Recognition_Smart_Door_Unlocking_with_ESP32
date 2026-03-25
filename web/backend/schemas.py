"""
=============================================================
 SCHEMAS - Pydantic Models cho API Request/Response
=============================================================
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ==================== USER ====================

class UserCreate(BaseModel):
    name: str
    mssv: str


class UserResponse(BaseModel):
    id: int
    name: str
    mssv: str
    face_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


# ==================== ATTENDANCE ====================

class AttendanceLogResponse(BaseModel):
    id: int
    user_name: Optional[str] = None
    mssv: Optional[str] = None
    timestamp: datetime
    status: str
    confidence: float

    class Config:
        from_attributes = True


class AttendanceListResponse(BaseModel):
    logs: list[AttendanceLogResponse]
    total: int
    date: str


# ==================== SECURITY ====================

class SecurityConfigSchema(BaseModel):
    night_start_hour: int = 18
    night_end_hour: int = 6
    deny_threshold: int = 2
    auto_lock_night: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    enable_notification: bool = True
    enable_night_alarm: bool = True


# ==================== SYSTEM ====================

class SystemStatus(BaseModel):
    esp32_connected: bool
    esp32_ip: Optional[str] = None
    recognition_active: bool
    users_count: int
    today_attendance: int
    security_mode: str
    deny_count: int
    alarm_active: bool
    room_locked: bool = False
    uptime_seconds: int


# ==================== WEBSOCKET EVENTS ====================

class WSEvent(BaseModel):
    event: str  # "attendance", "security_alert", "system_status"
    data: dict
