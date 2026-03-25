"""
=============================================================
 SMART ATTENDANCE SYSTEM - Main Application
=============================================================
 Hệ thống điểm danh & mở khóa cửa bằng nhận diện khuôn mặt.
 Hybrid Model: YOLOv8 + MediaPipe + FaceNet

 Chế độ chạy:
   1. python main.py                → Test với webcam (simulator)
   2. python main.py --esp32 IP     → Kết nối ESP32-S3 thật
   3. python main.py --enroll       → Chế độ enroll khuôn mặt
   4. python main.py --manage       → Quản lý người dùng
=============================================================
"""

import cv2
import sys
import os
import time
import argparse
import threading
from face_processor import FaceProcessor
from user_database import UserDatabase
from attendance import AttendanceManager
from esp32_controller import ESP32Controller, ESP32Simulator
from security_manager import SecurityManager


# ============================================
# CẤU HÌNH
# ============================================
RECOGNITION_THRESHOLD = 0.80    # Ngưỡng nhận diện (0.0-1.0)
DEBOUNCE_SECONDS = 30           # Chống điểm danh lặp (giây)
RELAY_OPEN_DURATION = 3         # Thời gian mở khóa (giây)
LCD_DISPLAY_DURATION = 3        # Thời gian hiển thị kết quả (giây)
PROCESS_INTERVAL_SEC = 0.5      # Xử lý nhận diện mỗi N giây (0.5s = nhanh hơn)
UNKNOWN_COOLDOWN_SEC = 5.0      # Cooldown giữa 2 lần hiện UNKNOWN
DB_PATH = "user_database.pkl"   # File database người dùng
ENROLL_LIMIT = 20               # Số ảnh mục tiêu khi enroll
ENROLL_MIN_CONFIDENCE = 0.8     # Confidence tối thiểu để lưu ảnh enroll


def run_recognition_mode(args):
    """
    Chế độ chính: Nhận diện khuôn mặt + điểm danh + mở khóa.
    AI chạy trên thread riêng để camera không bị đứng.
    """
    print("\n" + "=" * 55)
    print("  SMART ATTENDANCE SYSTEM")
    print("  Che do: NHAN DIEN & DIEM DANH")
    print("  Model: YOLOv8 + MediaPipe + FaceNet")
    print("=" * 55)

    # Khởi tạo modules
    db = UserDatabase(DB_PATH)
    processor = FaceProcessor(
        recognition_threshold=args.threshold
    )
    processor.set_database(db)
    attendance = AttendanceManager(debounce_seconds=DEBOUNCE_SECONDS)

    # Khởi tạo Security Manager
    security = SecurityManager(args.security_config)

    # Kết nối ESP32 hoặc dùng simulator
    if args.esp32:
        esp = ESP32Controller(args.esp32)
        if not esp.check_connection():
            print("\n[!] Khong ket noi duoc ESP32. Dung webcam simulator.")
            esp = ESP32Simulator(args.camera)
    else:
        esp = ESP32Simulator(args.camera)

    # Kiểm tra database
    if db.get_enrolled_count() == 0:
        print("\n=== DATABASE TRONG! Chua co khuon mat nao. ===")
        print("  Chay: python main.py --enroll")
        print("  de enroll khuon mat truoc.\n")

    esp.lcd_idle()

    print("\n[START] Dang chay... Nhan 'q' de thoat.\n")
    print("  Phim tat: 'l' = xem log | 'u' = xem users\n")

    # --- Shared state giữa main thread và AI thread ---
    current_frame = [None]
    last_results = []
    results_lock = threading.Lock()
    running = [True]
    lcd_reset_time = [0]
    last_unknown_time = [0]

    def ai_worker():
        """Thread riêng chạy AI, không block camera."""
        nonlocal last_results
        while running[0]:
            frame = current_frame[0]
            if frame is None:
                time.sleep(0.1)
                continue

            frame_copy = frame.copy()

            try:
                results = processor.process_frame(frame_copy, skip_mesh=True)
            except Exception as e:
                print(f"[AI ERROR] {e}")
                time.sleep(1)
                continue

            with results_lock:
                last_results = results

            # Xử lý TẤT CẢ khuôn mặt trong frame
            known_faces = [r for r in results if r.is_known]
            unknown_faces = [r for r in results
                            if not r.is_known and r.confidence > 0]

            # === KNOWN FACES ===
            for r in known_faces:
                # Kiểm tra Room Lock (khóa phòng từ xa)
                if security.is_room_locked:
                    esp.lcd_display("ROOM LOCKED", "Come back later")
                    esp.buzzer_beep("error")
                    lcd_reset_time[0] = time.time() + LCD_DISPLAY_DURATION
                    print(f"[LOCK] 🔒 {r.name} - Phòng đang khóa!")
                    break  # Không xử lý thêm

                logged = attendance.check_and_log(
                    r.user_id, r.name, r.mssv
                )
                if logged:
                    esp.lcd_recognized(r.name, r.mssv)
                    esp.relay_open(RELAY_OPEN_DURATION)
                    esp.buzzer_beep("ok")
                    lcd_reset_time[0] = time.time() + LCD_DISPLAY_DURATION
                    # Access granted → reset security counter + tắt alarm
                    security.on_access_granted(esp)
                else:
                    if not any(attendance.get_remaining_debounce(kr.user_id) == 0
                               for kr in known_faces):
                        esp.lcd_already()
                        lcd_reset_time[0] = time.time() + 2

            # === UNKNOWN FACES (có cooldown) ===
            if unknown_faces and not known_faces:
                now = time.time()
                if now - last_unknown_time[0] >= UNKNOWN_COOLDOWN_SEC:
                    esp.lcd_unknown()
                    esp.buzzer_beep("error")
                    lcd_reset_time[0] = now + LCD_DISPLAY_DURATION
                    last_unknown_time[0] = now
                    # Access deny → security manager xử lý
                    security.on_access_deny(esp)

            time.sleep(PROCESS_INTERVAL_SEC)

    # Khởi chạy AI thread
    ai_thread = threading.Thread(target=ai_worker, daemon=True)
    ai_thread.start()

    frame_count = 0
    fps_start = time.time()
    fps = 0.0

    try:
        while True:
            frame = esp.capture()
            if frame is None:
                time.sleep(0.05)
                continue

            # === FLIP CAMERA (mirror cho webcam simulator) ===
            # ESP32 firmware đã bật hmirror + vflip, chỉ flip khi dùng webcam
            if isinstance(esp, ESP32Simulator):
                frame = cv2.flip(frame, 1)

            # Cập nhật frame cho AI thread
            current_frame[0] = frame

            frame_count += 1

            # Reset LCD về idle
            if lcd_reset_time[0] > 0 and time.time() > lcd_reset_time[0]:
                esp.lcd_idle()
                lcd_reset_time[0] = 0

            # Vẽ kết quả (thread-safe read)
            with results_lock:
                display_results = list(last_results)

            frame = FaceProcessor.draw_results(frame, display_results)

            # FPS
            elapsed = time.time() - fps_start
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                fps_start = time.time()

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(
                frame,
                f"Users: {len(db.users)} | "
                f"Today: {attendance.get_today_count()}",
                (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
            )

            # Security status overlay
            sec_text = security.get_status_text()
            sec_color = (0, 0, 255) if security.is_alarm_active else (
                (0, 200, 255) if security.is_night_mode() else (0, 255, 0)
            )
            cv2.putText(frame, sec_text, (10, 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, sec_color, 1)

            cv2.imshow("Smart Attendance", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('l'):
                attendance.print_today()
            elif key == ord('u'):
                db.print_users()

    except KeyboardInterrupt:
        print("\n[STOP] Dung boi Ctrl+C")

    finally:
        running[0] = False
        ai_thread.join(timeout=3)
        cv2.destroyAllWindows()
        if hasattr(esp, 'release'):
            esp.release()
        print("[DONE] Da dong.")
        attendance.print_today()


def run_enroll_mode(args):
    """
    Chế độ enroll: Đăng ký khuôn mặt mới.
    Hybrid UI: YOLOv8 bbox vàng + MediaPipe mesh xanh + Progress bar.
    Chỉ lưu khi: confidence > 0.8 VÀ mặt chính diện.
    """
    print("\n" + "=" * 55)
    print("  SMART ATTENDANCE SYSTEM")
    print("  Che do: ENROLL KHUON MAT")
    print("  Model: YOLOv8 + MediaPipe + FaceNet")
    print("=" * 55)

    db = UserDatabase(DB_PATH)
    processor = FaceProcessor(recognition_threshold=args.threshold)
    processor.set_database(db)

    if db.users:
        db.print_users()

    print("\nChon hanh dong:")
    print("  1. Them nguoi moi + enroll bang webcam")
    print("  2. Them nguoi moi + enroll tu thu muc anh")
    print("  3. Enroll them anh cho nguoi da co")
    print("  4. Thoat")

    choice = input("\nLua chon (1-4): ").strip()

    if choice == "1":
        ho_ten = input("Nhap ho ten: ").strip()
        mssv = input("Nhap MSSV: ").strip()

        if not ho_ten or not mssv:
            print("[!] Can nhap day du ho ten va MSSV!")
            return

        user_id = db.add_user(ho_ten, mssv)
        _enroll_webcam(processor, db, user_id, ho_ten, args.camera)

        if db.get_user(user_id) and len(db.get_user(user_id).embeddings) == 0:
            db.remove_user(user_id)
            print(f"\n[!] Khong co anh nao, da xoa user.")

    elif choice == "2":
        ho_ten = input("Nhap ho ten: ").strip()
        mssv = input("Nhap MSSV: ").strip()
        folder = input("Duong dan thu muc anh: ").strip()

        if not ho_ten or not mssv or not folder:
            print("[!] Can nhap day du thong tin!")
            return

        user_id = db.add_user(ho_ten, mssv)
        count = processor.enroll_from_folder(folder, user_id)

        if count > 0:
            processor.invalidate_cache()
            print(f"\n[OK] Enroll hoan tat: {ho_ten} -> {count} anh")
        else:
            db.remove_user(user_id)
            print(f"\n[!] Khong enroll duoc anh nao!")

    elif choice == "3":
        db.print_users()
        try:
            user_id = int(input("Nhap User ID can enroll them: "))
        except ValueError:
            print("[!] ID khong hop le!")
            return

        user = db.get_user(user_id)
        if not user:
            print(f"[!] Khong tim thay User ID={user_id}")
            return

        _enroll_webcam(processor, db, user_id, user.ho_ten, args.camera)


def _enroll_webcam(processor, db, user_id, name, camera_index):
    """
    Mở webcam để enroll khuôn mặt.
    Hybrid UI: bbox vàng + mesh xanh + progress bar.
    Chỉ lưu khi confidence > 0.8 VÀ mặt chính diện (MediaPipe).
    """
    print(f"\n[INFO] Mo webcam cho: {name}")
    print(f"  === ENROLL MODE ===")
    print(f"  - AUTO: Tu chup moi 3 giay (bam 'a' bat/tat)")
    print(f"  - CLICK CHUOT TRAI vao cua so camera")
    print(f"  - Nhan SPACE hoac 's' de chup thu cong")
    print(f"  - Chi luu khi mat CHINH DIEN + confidence > {ENROLL_MIN_CONFIDENCE}")
    print(f"  - Nhan 'q' hoac ESC = Hoan tat")
    print(f"  - Muc tieu: {ENROLL_LIMIT} anh\n")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("[!] Khong mo duoc camera!")
        print(f"  Thu: python main.py --enroll --camera 1")
        return

    # Warmup camera
    print("[INFO] Dang khoi tao camera...")
    for _ in range(10):
        cap.read()
        time.sleep(0.05)

    # Tạo thư mục dataset (lưu ảnh crop)
    dataset_dir = os.path.join("dataset", name.replace(" ", "_"))
    os.makedirs(dataset_dir, exist_ok=True)

    # --- State ---
    enroll_count = 0
    should_capture = [False]
    auto_mode = [True]
    last_auto_time = time.time()
    AUTO_INTERVAL = 3.0

    # --- Mouse callback ---
    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            should_capture[0] = True
            print("  [CLICK] Da nhan click chuot!")

    window_name = "Enroll - Click de chup"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_name, on_mouse)

    print("[OK] Camera san sang!")
    print(f"[AUTO] Auto-capture: BAT (moi {AUTO_INTERVAL:.0f}s)\n")

    while enroll_count < ENROLL_LIMIT:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        # === FLIP CAMERA (mirror) ===
        frame = cv2.flip(frame, 1)

        # === Kiểm tra auto-capture ===
        if auto_mode[0]:
            elapsed = time.time() - last_auto_time
            if elapsed >= AUTO_INTERVAL:
                should_capture[0] = True
                last_auto_time = time.time()

        # === YOLO detect + MediaPipe mesh cho hiển thị ===
        try:
            boxes, probs = processor.detect_faces(frame)
        except Exception as e:
            print(f"[ERROR] Detection: {e}")
            boxes, probs = [], []

        # Lấy landmarks cho tất cả faces
        face_data = []
        for box, prob in zip(boxes, probs):
            landmarks = processor.get_face_mesh(frame, box)
            is_frontal = processor.is_frontal_face(landmarks)
            face_data.append((box, prob, landmarks, is_frontal))

        # === Xử lý chụp ===
        if should_capture[0] and face_data:
            should_capture[0] = False

            # Tìm face lớn nhất (gần nhất)
            best_face = max(face_data,
                            key=lambda f: (f[0][2]-f[0][0]) * (f[0][3]-f[0][1]))
            box, prob, landmarks, is_frontal = best_face

            if prob < ENROLL_MIN_CONFIDENCE:
                print(f"  >>> Confidence qua thap ({prob:.2f} < {ENROLL_MIN_CONFIDENCE})")
            elif not is_frontal:
                print(f"  >>> Mat KHONG chinh dien! Hay nhin thang vao camera.")
            else:
                print(f"  [PROCESSING] Dang trich xuat khuon mat...")

                success = processor.enroll_from_frame(frame, user_id)

                if success:
                    enroll_count += 1
                    print(f"  >>> OK! Da chup {enroll_count}/{ENROLL_LIMIT}")

                    # Lưu ảnh crop vào dataset
                    x1, y1, x2, y2 = box
                    face_crop = frame[y1:y2, x1:x2]
                    if face_crop.size > 0:
                        crop_path = os.path.join(
                            dataset_dir,
                            f"{name.replace(' ', '_')}_{enroll_count:04d}.jpg"
                        )
                        cv2.imwrite(crop_path, face_crop)

                    # Flash xanh
                    h, w = frame.shape[:2]
                    flash = frame.copy()
                    cv2.rectangle(flash, (0, 0), (w, h), (0, 255, 0), 15)
                    cv2.putText(flash, f"OK! ({enroll_count}/{ENROLL_LIMIT})",
                                (w // 2 - 100, h // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
                    cv2.imshow(window_name, flash)
                    cv2.waitKey(300)
                else:
                    print(f"  >>> FaceNet khong detect duoc mat trong crop!")
                    h, w = frame.shape[:2]
                    flash = frame.copy()
                    cv2.rectangle(flash, (0, 0), (w, h), (0, 0, 255), 10)
                    cv2.putText(flash, "KHONG THAY MAT!",
                                (w // 2 - 120, h // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
                    cv2.imshow(window_name, flash)
                    cv2.waitKey(300)

            continue

        elif should_capture[0] and not face_data:
            should_capture[0] = False
            print("  >>> Khong thay khuon mat nao!")
            continue

        # === Vẽ HUD ===
        display = frame.copy()
        h, w = display.shape[:2]

        # Vẽ YOLO bbox vàng + MediaPipe mesh xanh
        for box, prob, landmarks, is_frontal in face_data:
            x1, y1, x2, y2 = box

            # Bbox vàng
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 220, 255), 2)

            # Corner accents
            cl = min(20, (x2 - x1) // 4, (y2 - y1) // 4)
            for cx, cy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
                dx = cl if cx == x1 else -cl
                dy = cl if cy == y1 else -cl
                cv2.line(display, (cx, cy), (cx + dx, cy),
                         (0, 220, 255), 3)
                cv2.line(display, (cx, cy), (cx, cy + dy),
                         (0, 220, 255), 3)

            # Face Mesh xanh
            if landmarks:
                FaceProcessor.draw_face_mesh(display, landmarks,
                                             color=(0, 255, 0), thickness=1)

            # Confidence + Frontal status
            conf_text = f"{prob*100:.0f}%"
            front_text = "FRONTAL" if is_frontal else "NOT FRONTAL"
            front_color = (0, 255, 0) if is_frontal else (0, 0, 255)

            cv2.putText(display, conf_text, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 255), 1)
            cv2.putText(display, front_text, (x1, y2 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, front_color, 1)

        # Mode text
        mode_text = "AUTO" if auto_mode[0] else "MANUAL"
        cv2.putText(display, f"Mode: {mode_text} | 'a'=toggle | 'q'=xong",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (200, 200, 200), 1)

        if auto_mode[0]:
            remaining = AUTO_INTERVAL - (time.time() - last_auto_time)
            cv2.putText(display, f"Auto chup sau: {max(0,remaining):.1f}s",
                        (10, 48), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (0, 255, 255), 1)

        # === PROGRESS BAR + ENROLL LABEL ===
        FaceProcessor.draw_enroll_ui(display, name, enroll_count, ENROLL_LIMIT)

        cv2.imshow(window_name, display)

        # === Xử lý phím ===
        key = cv2.waitKey(30)

        if key == -1:
            continue

        key = key & 0xFF

        if key == ord('q') or key == 27:  # q hoặc ESC
            break
        elif key == ord('s') or key == 32:  # s hoặc SPACE
            should_capture[0] = True
            print("  [KEY] Nhan phim chup!")
        elif key == ord('a'):  # Toggle auto
            auto_mode[0] = not auto_mode[0]
            last_auto_time = time.time()
            status = "BAT" if auto_mode[0] else "TAT"
            print(f"  [AUTO] Auto-capture: {status}")

    cap.release()
    cv2.destroyAllWindows()

    if enroll_count > 0:
        processor.invalidate_cache()
        print(f"\n{'='*45}")
        print(f"  ENROLL HOAN TAT!")
        print(f"  Ten:  {name}")
        print(f"  So anh: {enroll_count}")
        print(f"  Luu tai: {dataset_dir}")
        print(f"{'='*45}")
    else:
        print(f"\n[!] Khong chup duoc anh nao.")


def run_manage_mode(args):
    """Chế độ quản lý: Xem/xóa người dùng."""
    print("\n" + "=" * 55)
    print("  SMART ATTENDANCE SYSTEM")
    print("  Che do: QUAN LY NGUOI DUNG")
    print("=" * 55)

    db = UserDatabase(DB_PATH)

    while True:
        db.print_users()
        print("Chon hanh dong:")
        print("  1. Xem chi tiet nguoi dung")
        print("  2. Xoa nguoi dung")
        print("  3. Xoa toan bo database")
        print("  4. Thoat")

        choice = input("\nLua chon (1-4): ").strip()

        if choice == "1":
            try:
                uid = int(input("Nhap User ID: "))
            except ValueError:
                continue
            user = db.get_user(uid)
            if user:
                print(f"\n  ID:     {user.user_id}")
                print(f"  Ten:    {user.ho_ten}")
                print(f"  MSSV:   {user.mssv}")
                print(f"  Faces:  {len(user.embeddings)}")
                print(f"  Tao:    {user.created_at}\n")
            else:
                print(f"  [!] Khong tim thay!")

        elif choice == "2":
            try:
                uid = int(input("Nhap User ID can xoa: "))
            except ValueError:
                continue
            confirm = input(f"Xac nhan xoa ID={uid}? (y/n): ")
            if confirm.lower() == 'y':
                db.remove_user(uid)

        elif choice == "3":
            confirm = input("XOA TOAN BO DATABASE? (yes/no): ")
            if confirm.lower() == 'yes':
                if os.path.exists(DB_PATH):
                    os.remove(DB_PATH)
                    db = UserDatabase(DB_PATH)
                    print("[OK] Da xoa toan bo!")

        elif choice == "4":
            break


def main():
    parser = argparse.ArgumentParser(
        description="Smart Attendance System - Hybrid Face Recognition",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "--esp32", type=str, default=None,
        help="IP address cua ESP32-S3 (vd: 192.168.1.100)"
    )
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Camera index cho webcam (mac dinh: 0)"
    )
    parser.add_argument(
        "--threshold", type=float, default=RECOGNITION_THRESHOLD,
        help=f"Nguong nhan dien 0.0-1.0 (mac dinh: {RECOGNITION_THRESHOLD})"
    )
    parser.add_argument(
        "--enroll", action="store_true",
        help="Che do enroll khuon mat moi"
    )
    parser.add_argument(
        "--manage", action="store_true",
        help="Che do quan ly nguoi dung"
    )
    parser.add_argument(
        "--security-config", type=str, default="security_config.json",
        dest="security_config",
        help="Duong dan file cau hinh an ninh (mac dinh: security_config.json)"
    )

    args = parser.parse_args()

    if args.enroll:
        run_enroll_mode(args)
    elif args.manage:
        run_manage_mode(args)
    else:
        run_recognition_mode(args)


if __name__ == "__main__":
    main()