/**
 * =================================================================
 *  SMART ATTENDANCE - ESP32-S3 Firmware
 * =================================================================
 *  Chức năng:
 *    1. Camera OV3660 → HTTP snapshot (/capture) + MJPEG stream (/stream)
 *    2. LCD1602 I2C   → Hiển thị tên, MSSV, trạng thái
 *    3. Relay         → Mở khóa chốt điện từ
 *    4. Buzzer        → Âm thanh thông báo
 *
 *  HTTP Endpoints:
 *    GET  /capture        → Chụp ảnh JPEG
 *    GET  /stream         → MJPEG stream (xem trên browser)
 *    GET  /status         → JSON trạng thái hệ thống
 *    POST /lcd            → Điều khiển LCD (JSON body)
 *    POST /relay          → Điều khiển relay (JSON body)
 *    POST /buzzer         → Điều khiển buzzer (JSON body)
 *    GET  /lcd?line1=X&line2=Y  → LCD bằng query params
 *    GET  /relay?action=open&duration=3000
 *    GET  /buzzer?pattern=ok
 *
 *  Thư viện cần cài (Arduino IDE):
 *    - ESP32 Board Support v3.x (chọn "ESP32-S3 Dev Module")
 *    - LiquidCrystal_I2C (by Frank de Brabander)
 *    - ArduinoJson v7 (by Benoit Blanchon)
 *
 *  Board Settings trong Arduino IDE:
 *    - Board: "ESP32S3 Dev Module"
 *    - PSRAM: "OPI PSRAM"
 *    - Flash Size: "8MB" hoặc "16MB"
 *    - Partition Scheme: "Huge APP (3MB No OTA/1MB SPIFFS)"
 *    - Upload Speed: 921600
 * =================================================================
 */

#include "esp_camera.h"
#include "esp_http_server.h"
#include <WiFi.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

#include "camera_pins.h"

// ============================================
// CẤU HÌNH WIFI - ĐỔI THEO MẠNG CỦA BẠN
// ============================================
const char* WIFI_SSID     = "Wi-MESH - HCMUTE";      // ← Đổi
const char* WIFI_PASSWORD  = "hcmute@2024";   // ← Đổi

// ============================================
// CẤU HÌNH CAMERA
// ============================================
#define FRAME_SIZE    FRAMESIZE_VGA    // 640x480 (đủ cho face recognition)
#define JPEG_QUALITY  12               // 10-63, thấp = chất lượng cao hơn

// ============================================
// BIẾN TOÀN CỤC & STRUCTS
// ============================================

// Buzzer pattern: mỗi step = {on_ms, off_ms}, kết thúc bằng {0,0}
struct BuzzerStep {
    unsigned int on_ms;
    unsigned int off_ms;
};

httpd_handle_t camera_httpd  = NULL;
httpd_handle_t control_httpd = NULL;

LiquidCrystal_I2C lcd(LCD_I2C_ADDR, LCD_COLS, LCD_ROWS);

// Relay timer (non-blocking)
volatile unsigned long relay_close_time = 0;
volatile bool relay_is_open = false;

// Trạng thái
unsigned long boot_time = 0;
unsigned long frame_count = 0;

// ============================================
// LCD FUNCTIONS
// ============================================

void lcd_init() {
    // Khởi tạo I2C & LCD từ từ để tránh lỗi
    Serial.println("Init I2C for LCD...");
    Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
    Wire.setClock(50000); // Hạ tốc độ I2C xuống 50kHz để chống nhiễu font chữ
    delay(100);
    lcd.init();
    lcd.backlight();
    lcd_show("SMART ATTEND", "Booting...");
    Serial.println("[LCD] Initialized");
}

void lcd_show(const char* line1, const char* line2) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(line1);
    lcd.setCursor(0, 1);
    lcd.print(line2);
    Serial.printf("[LCD] L1: %s\n", line1);
    Serial.printf("[LCD] L2: %s\n", line2);
}

void lcd_idle() {
    lcd_show("SMART ATTEND", "Scan face...");
}

// ============================================
// RELAY FUNCTIONS (Non-blocking)
// ============================================

void relay_init() {
    pinMode(RELAY_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, RELAY_INACTIVE);
    Serial.println("[RELAY] Initialized");
}

void relay_open(unsigned long duration_ms) {
    digitalWrite(RELAY_PIN, RELAY_ACTIVE);
    relay_is_open = true;
    relay_close_time = millis() + duration_ms;
    Serial.printf("[RELAY] OPEN for %lu ms\n", duration_ms);
}

void relay_close() {
    digitalWrite(RELAY_PIN, RELAY_INACTIVE);
    relay_is_open = false;
    Serial.println("[RELAY] CLOSED");
}

void relay_update() {
    // Gọi trong loop() - tự đóng relay sau thời gian
    if (relay_is_open && millis() >= relay_close_time) {
        relay_close();
    }
}

// ============================================
// BUZZER FUNCTIONS (Non-blocking)
// ============================================

// Các pattern định nghĩa sẵn
const BuzzerStep PATTERN_OK[]     = {{200, 0}, {0, 0}};
const BuzzerStep PATTERN_ERROR[]  = {{300, 100}, {300, 0}, {0, 0}};
const BuzzerStep PATTERN_ENROLL[] = {{100, 50}, {100, 50}, {100, 0}, {0, 0}};
// Alarm: kêu to, dài, lặp lại liên tục cho đến khi stop
const BuzzerStep PATTERN_ALARM[]  = {
    {800, 200}, {800, 200}, {800, 200},
    {800, 200}, {800, 200}, {0, 0}
};

// Buzzer state machine
const BuzzerStep* buzzer_pattern = NULL;
int buzzer_step = 0;
bool buzzer_is_on = false;
unsigned long buzzer_next_time = 0;
bool buzzer_active_flag = false;
bool buzzer_alarm_loop = false;  // true = lặp lại pattern liên tục (alarm mode)
unsigned long buzzer_alarm_stop_time = 0;  // 0 = không giới hạn, >0 = tự tắt sau thời gian

void buzzer_init() {
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, !BUZZER_ACTIVE);
    Serial.println("[BUZZER] Initialized");
}

void buzzer_start_pattern(const BuzzerStep* pattern) {
    buzzer_pattern = pattern;
    buzzer_step = 0;
    buzzer_is_on = true;
    buzzer_active_flag = true;
    buzzer_next_time = millis();
    // Bắt đầu step đầu tiên ngay
    digitalWrite(BUZZER_PIN, BUZZER_ACTIVE);
    buzzer_next_time = millis() + pattern[0].on_ms;
    Serial.println("[BUZZER] Pattern started");
}

void buzzer_update() {
    // Gọi trong loop() - xử lý buzzer không block
    if (!buzzer_active_flag || buzzer_pattern == NULL) return;

    // === AUTO-STOP: tự tắt alarm sau thời gian ===
    if (buzzer_alarm_loop && buzzer_alarm_stop_time > 0 && millis() >= buzzer_alarm_stop_time) {
        buzzer_alarm_loop = false;
        buzzer_active_flag = false;
        buzzer_is_on = false;
        buzzer_alarm_stop_time = 0;
        digitalWrite(BUZZER_PIN, !BUZZER_ACTIVE);
        Serial.println("[BUZZER] ALARM AUTO-STOPPED (timeout)");
        return;
    }

    if (millis() < buzzer_next_time) return;

    if (buzzer_is_on) {
        // Vừa hết thời gian ON → tắt buzzer
        digitalWrite(BUZZER_PIN, !BUZZER_ACTIVE);
        buzzer_is_on = false;

        unsigned int off_ms = buzzer_pattern[buzzer_step].off_ms;
        if (off_ms > 0) {
            buzzer_next_time = millis() + off_ms;
        } else {
            // Không có off_ms → chuyển step tiếp ngay
            buzzer_step++;
            if (buzzer_pattern[buzzer_step].on_ms == 0) {
                // Hết pattern
                if (buzzer_alarm_loop) {
                    // Alarm mode: lặp lại từ đầu
                    buzzer_step = 0;
                    buzzer_is_on = true;
                    digitalWrite(BUZZER_PIN, BUZZER_ACTIVE);
                    buzzer_next_time = millis() + buzzer_pattern[0].on_ms;
                    Serial.println("[BUZZER] Alarm loop restart");
                } else {
                    buzzer_active_flag = false;
                    Serial.println("[BUZZER] Pattern done");
                }
            } else {
                // Bắt đầu step mới
                buzzer_is_on = true;
                digitalWrite(BUZZER_PIN, BUZZER_ACTIVE);
                buzzer_next_time = millis() + buzzer_pattern[buzzer_step].on_ms;
            }
        }
    } else {
        // Vừa hết thời gian OFF → chuyển step tiếp
        buzzer_step++;
        if (buzzer_pattern[buzzer_step].on_ms == 0) {
            // Hết pattern
            if (buzzer_alarm_loop) {
                buzzer_step = 0;
                buzzer_is_on = true;
                digitalWrite(BUZZER_PIN, BUZZER_ACTIVE);
                buzzer_next_time = millis() + buzzer_pattern[0].on_ms;
                Serial.println("[BUZZER] Alarm loop restart");
            } else {
                buzzer_active_flag = false;
                Serial.println("[BUZZER] Pattern done");
            }
        } else {
            // Bắt đầu step mới
            buzzer_is_on = true;
            digitalWrite(BUZZER_PIN, BUZZER_ACTIVE);
            buzzer_next_time = millis() + buzzer_pattern[buzzer_step].on_ms;
        }
    }
}


// ============================================
// CAMERA INIT
// ============================================

bool camera_init() {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer   = LEDC_TIMER_0;
    config.pin_d0       = Y2_GPIO_NUM;
    config.pin_d1       = Y3_GPIO_NUM;
    config.pin_d2       = Y4_GPIO_NUM;
    config.pin_d3       = Y5_GPIO_NUM;
    config.pin_d4       = Y6_GPIO_NUM;
    config.pin_d5       = Y7_GPIO_NUM;
    config.pin_d6       = Y8_GPIO_NUM;
    config.pin_d7       = Y9_GPIO_NUM;
    config.pin_xclk     = XCLK_GPIO_NUM;
    config.pin_pclk     = PCLK_GPIO_NUM;
    config.pin_vsync    = VSYNC_GPIO_NUM;
    config.pin_href     = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn     = PWDN_GPIO_NUM;
    config.pin_reset    = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode    = CAMERA_GRAB_LATEST;   // Luôn lấy frame mới nhất
    config.fb_location  = CAMERA_FB_IN_PSRAM;

    // PSRAM available → dùng frame buffer lớn hơn
    if (psramFound()) {
        config.frame_size   = FRAME_SIZE;
        config.jpeg_quality = JPEG_QUALITY;
        config.fb_count     = 2;    // Double buffering
        Serial.printf("[CAM] PSRAM found: %d bytes\n", ESP.getPsramSize());
    } else {
        config.frame_size   = FRAMESIZE_QVGA;  // 320x240 nếu không có PSRAM
        config.jpeg_quality = 15;
        config.fb_count     = 1;
        Serial.println("[CAM] WARNING: No PSRAM! Reduced quality.");
    }

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("[CAM] Init FAILED: 0x%x\n", err);
        return false;
    }

    // Cấu hình sensor
    sensor_t *s = esp_camera_sensor_get();
    if (s) {
        s->set_brightness(s, 1);     // -2 to 2
        s->set_contrast(s, 1);       // -2 to 2
        s->set_saturation(s, 0);     // -2 to 2
        s->set_whitebal(s, 1);       // 0 = disable, 1 = enable
        s->set_awb_gain(s, 1);       // 0 = disable, 1 = enable
        s->set_wb_mode(s, 0);        // 0~4 - auto
        s->set_exposure_ctrl(s, 1);  // 0 = disable, 1 = enable
        s->set_aec2(s, 1);           // 0 = disable, 1 = enable
        s->set_gain_ctrl(s, 1);      // 0 = disable, 1 = enable
        s->set_hmirror(s, 1);        // 1 = mirror (tự nhiên như gương)
        s->set_vflip(s, 1);          // 1 = lật dọc (sửa camera ngược)
        Serial.println("[CAM] Sensor configured");
    }

    Serial.printf("[CAM] Initialized OK | Size: %d | Quality: %d\n",
                  FRAME_SIZE, JPEG_QUALITY);
    return true;
}

// ============================================
// HTTP HANDLER: /capture (JPEG snapshot)
// ============================================

static esp_err_t capture_handler(httpd_req_t *req) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition",
                       "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");

    esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);

    frame_count++;
    return res;
}

// ============================================
// HTTP HANDLER: /stream (MJPEG)
// ============================================

#define PART_BOUNDARY "123456789000000000000987654321"
static const char* STREAM_CONTENT_TYPE =
    "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BOUNDARY =
    "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PART =
    "Content-Type: image/jpeg\r\n"
    "Content-Length: %u\r\n\r\n";

static esp_err_t stream_handler(httpd_req_t *req) {
    esp_err_t res = ESP_OK;
    char part_buf[64];

    httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    Serial.println("[STREAM] Client connected");

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("[STREAM] Frame capture failed");
            res = ESP_FAIL;
            break;
        }

        size_t hlen = snprintf(part_buf, 64, STREAM_PART, fb->len);

        res = httpd_resp_send_chunk(req, STREAM_BOUNDARY,
                                    strlen(STREAM_BOUNDARY));
        if (res != ESP_OK) { esp_camera_fb_return(fb); break; }

        res = httpd_resp_send_chunk(req, part_buf, hlen);
        if (res != ESP_OK) { esp_camera_fb_return(fb); break; }

        res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
        esp_camera_fb_return(fb);
        if (res != ESP_OK) break;

        frame_count++;
    }

    Serial.println("[STREAM] Client disconnected");
    return res;
}

// ============================================
// HELPER: Đọc POST body
// ============================================

String read_post_body(httpd_req_t *req) {
    int total_len = req->content_len;
    if (total_len <= 0 || total_len > 512) return "";

    char *buf = (char *)malloc(total_len + 1);
    if (!buf) return "";

    int received = 0;
    while (received < total_len) {
        int ret = httpd_req_recv(req, buf + received,
                                 total_len - received);
        if (ret <= 0) { free(buf); return ""; }
        received += ret;
    }
    buf[total_len] = '\0';

    String result = String(buf);
    free(buf);
    return result;
}

// Helper: Lấy query parameter
String get_query_param(httpd_req_t *req, const char *key) {
    char buf[256] = {0};
    if (httpd_req_get_url_query_str(req, buf, sizeof(buf)) != ESP_OK)
        return "";

    char value[64] = {0};
    if (httpd_query_key_value(buf, key, value, sizeof(value)) != ESP_OK)
        return "";

    return String(value);
}

// ============================================
// HTTP HANDLER: /lcd
// ============================================

static esp_err_t lcd_handler(httpd_req_t *req) {
    String line1 = "";
    String line2 = "";

    if (req->method == HTTP_POST) {
        // Parse JSON body
        String body = read_post_body(req);
        if (body.length() > 0) {
            JsonDocument doc;
            DeserializationError error = deserializeJson(doc, body);
            if (!error) {
                line1 = doc["line1"].as<String>();
                line2 = doc["line2"].as<String>();
            }
        }
    } else {
        // GET with query params
        line1 = get_query_param(req, "line1");
        line2 = get_query_param(req, "line2");
    }

    if (line1.length() > 0 || line2.length() > 0) {
        lcd_show(line1.c_str(), line2.c_str());
    }

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");
    httpd_resp_sendstr(req, "{\"status\":\"ok\"}");
    return ESP_OK;
}

// ============================================
// HTTP HANDLER: /relay
// ============================================

static esp_err_t relay_handler(httpd_req_t *req) {
    String action = "";
    unsigned long duration = RELAY_OPEN_MS;

    if (req->method == HTTP_POST) {
        String body = read_post_body(req);
        if (body.length() > 0) {
            JsonDocument doc;
            if (!deserializeJson(doc, body)) {
                action = doc["action"].as<String>();
                if (doc["duration"])
                    duration = doc["duration"].as<unsigned long>() * 1000;
            }
        }
    } else {
        action = get_query_param(req, "action");
        String dur_str = get_query_param(req, "duration");
        if (dur_str.length() > 0) {
            unsigned long dur_val = dur_str.toInt();
            // Nếu giá trị nhỏ (< 100), coi là giây → nhân 1000
            // Nếu lớn (>= 100), coi là milliseconds
            duration = (dur_val < 100) ? dur_val * 1000 : dur_val;
        }
    }

    if (action == "open") {
        relay_open(duration);
    } else if (action == "close") {
        relay_close();
    }

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");

    char response[64];
    snprintf(response, sizeof(response),
             "{\"status\":\"ok\",\"relay\":\"%s\"}",
             relay_is_open ? "open" : "closed");
    httpd_resp_sendstr(req, response);
    return ESP_OK;
}

// ============================================
// HTTP HANDLER: /buzzer
// ============================================

static esp_err_t buzzer_handler(httpd_req_t *req) {
    String pattern = "ok";

    if (req->method == HTTP_POST) {
        String body = read_post_body(req);
        if (body.length() > 0) {
            JsonDocument doc;
            if (!deserializeJson(doc, body)) {
                pattern = doc["pattern"].as<String>();
            }
        }
    } else {
        String p = get_query_param(req, "pattern");
        if (p.length() > 0) pattern = p;
    }

    if (pattern == "ok") {
        buzzer_alarm_loop = false;
        buzzer_start_pattern(PATTERN_OK);
    } else if (pattern == "error") {
        buzzer_alarm_loop = false;
        buzzer_start_pattern(PATTERN_ERROR);
    } else if (pattern == "enroll") {
        buzzer_alarm_loop = false;
        buzzer_start_pattern(PATTERN_ENROLL);
    } else if (pattern == "alarm") {
        buzzer_alarm_loop = true;
        buzzer_alarm_stop_time = 0;  // Không giới hạn (chờ lệnh stop)
        buzzer_start_pattern(PATTERN_ALARM);
        Serial.println("[BUZZER] ALARM MODE - continuous until stop");
    } else if (pattern == "alarm_timed") {
        // Alarm có giới hạn thời gian (mặc định 30s)
        buzzer_alarm_loop = true;
        unsigned long dur_ms = 30000;  // default 30s

        // Lấy duration từ JSON hoặc query param
        if (req->method == HTTP_POST) {
            String body2 = read_post_body(req);
            if (body2.length() > 0) {
                JsonDocument doc2;
                if (!deserializeJson(doc2, body2)) {
                    if (doc2["duration"]) dur_ms = doc2["duration"].as<unsigned long>();
                }
            }
        } else {
            String dur_str = get_query_param(req, "duration");
            if (dur_str.length() > 0) dur_ms = dur_str.toInt();
        }

        buzzer_alarm_stop_time = millis() + dur_ms;
        buzzer_start_pattern(PATTERN_ALARM);
        Serial.printf("[BUZZER] ALARM TIMED - auto-stop in %lu ms\n", dur_ms);
    } else if (pattern == "stop") {
        buzzer_alarm_loop = false;
        buzzer_active_flag = false;
        buzzer_is_on = false;
        buzzer_alarm_stop_time = 0;
        digitalWrite(BUZZER_PIN, !BUZZER_ACTIVE);
        Serial.println("[BUZZER] ALARM STOPPED");
    }

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");
    httpd_resp_sendstr(req, "{\"status\":\"ok\"}");
    return ESP_OK;
}

// ============================================
// HTTP HANDLER: /status
// ============================================

static esp_err_t status_handler(httpd_req_t *req) {
    char response[256];
    unsigned long uptime = (millis() - boot_time) / 1000;

    snprintf(response, sizeof(response),
        "{"
        "\"status\":\"ok\","
        "\"device\":\"ESP32-S3 Smart Attendance\","
        "\"ip\":\"%s\","
        "\"uptime\":%lu,"
        "\"frames\":%lu,"
        "\"relay\":\"%s\","
        "\"psram\":%s,"
        "\"psram_size\":%d,"
        "\"heap_free\":%d"
        "}",
        WiFi.localIP().toString().c_str(),
        uptime,
        frame_count,
        relay_is_open ? "open" : "closed",
        psramFound() ? "true" : "false",
        ESP.getPsramSize(),
        ESP.getFreeHeap()
    );

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");
    httpd_resp_sendstr(req, response);
    return ESP_OK;
}

// ============================================
// HTTP HANDLER: / (Trang chủ web)
// ============================================

static const char INDEX_HTML[] = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <title>Smart Attendance - ESP32-S3</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: #eee;
               text-align: center; margin: 0; padding: 20px; }
        h1 { color: #e94560; }
        img { max-width: 100%; border-radius: 10px;
              border: 2px solid #e94560; }
        .btn { padding: 12px 24px; margin: 5px; border: none;
               border-radius: 8px; font-size: 16px; cursor: pointer;
               color: white; }
        .btn-green { background: #2ecc71; }
        .btn-red { background: #e74c3c; }
        .btn-blue { background: #3498db; }
        .status { background: #16213e; padding: 15px;
                  border-radius: 10px; margin: 15px 0;
                  text-align: left; }
        .status span { color: #e94560; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Smart Attendance</h1>
    <p>ESP32-S3 Camera Server</p>
    <img id="stream" src="/stream" alt="Camera Stream">
    <div style="margin-top: 15px;">
        <button class="btn btn-green"
                onclick="fetch('/relay?action=open&duration=3000')">
            Open Relay (3s)
        </button>
        <button class="btn btn-red"
                onclick="fetch('/relay?action=close')">
            Close Relay
        </button>
        <button class="btn btn-blue"
                onclick="fetch('/buzzer?pattern=ok')">
            Buzzer Test
        </button>
    </div>
    <div class="status" id="statusDiv">
        <p>IP: <span id="ip">-</span></p>
        <p>Uptime: <span id="uptime">-</span>s</p>
        <p>Frames: <span id="frames">-</span></p>
        <p>Relay: <span id="relay">-</span></p>
    </div>
    <script>
        setInterval(async () => {
            try {
                const r = await fetch('/status');
                const d = await r.json();
                document.getElementById('ip').textContent = d.ip;
                document.getElementById('uptime').textContent = d.uptime;
                document.getElementById('frames').textContent = d.frames;
                document.getElementById('relay').textContent = d.relay;
            } catch(e) {}
        }, 2000);
    </script>
</body>
</html>
)rawliteral";

static esp_err_t index_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    httpd_resp_sendstr(req, INDEX_HTML);
    return ESP_OK;
}

// ============================================
// START HTTP SERVERS
// ============================================

void start_http_server() {
    // Server 1: Camera (port 80)
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.max_uri_handlers = 10;
    config.stack_size = 8192;
    config.max_open_sockets = 7;        // Nâng lên 7 để không bị rớt connection khi app gọi liên tục
    config.lru_purge_enable = true;     // Tự đóng socket cũ nhất khi hết
    config.recv_wait_timeout = 3;       // Timeout nhận data 3s (giảm từ 5s → giải phóng socket nhanh hơn)
    config.send_wait_timeout = 3;       // Timeout gửi data 3s

    if (httpd_start(&camera_httpd, &config) == ESP_OK) {
        // GET /
        httpd_uri_t index_uri = {
            .uri = "/", .method = HTTP_GET,
            .handler = index_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &index_uri);

        // GET /capture
        httpd_uri_t capture_uri = {
            .uri = "/capture", .method = HTTP_GET,
            .handler = capture_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &capture_uri);

        // GET /status
        httpd_uri_t status_uri = {
            .uri = "/status", .method = HTTP_GET,
            .handler = status_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &status_uri);

        // POST /lcd
        httpd_uri_t lcd_post_uri = {
            .uri = "/lcd", .method = HTTP_POST,
            .handler = lcd_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &lcd_post_uri);

        // GET /lcd (query params fallback)
        httpd_uri_t lcd_get_uri = {
            .uri = "/lcd", .method = HTTP_GET,
            .handler = lcd_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &lcd_get_uri);

        // POST /relay
        httpd_uri_t relay_post_uri = {
            .uri = "/relay", .method = HTTP_POST,
            .handler = relay_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &relay_post_uri);

        // GET /relay (query params fallback)
        httpd_uri_t relay_get_uri = {
            .uri = "/relay", .method = HTTP_GET,
            .handler = relay_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &relay_get_uri);

        // POST /buzzer
        httpd_uri_t buzzer_post_uri = {
            .uri = "/buzzer", .method = HTTP_POST,
            .handler = buzzer_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &buzzer_post_uri);

        // GET /buzzer (query params fallback)
        httpd_uri_t buzzer_get_uri = {
            .uri = "/buzzer", .method = HTTP_GET,
            .handler = buzzer_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(camera_httpd, &buzzer_get_uri);

        Serial.println("[HTTP] Server started on port 80");
    }

    // Server 2: Stream (port 81) — tách riêng để không block
    httpd_config_t stream_config = HTTPD_DEFAULT_CONFIG();
    stream_config.server_port = 81;
    stream_config.ctrl_port = 32769;
    stream_config.stack_size = 8192;
    stream_config.max_open_sockets = 2;     // Stream chỉ cần 1-2 clients
    stream_config.lru_purge_enable = true;

    if (httpd_start(&control_httpd, &stream_config) == ESP_OK) {
        httpd_uri_t stream_uri = {
            .uri = "/stream", .method = HTTP_GET,
            .handler = stream_handler, .user_ctx = NULL
        };
        httpd_register_uri_handler(control_httpd, &stream_uri);
        Serial.println("[HTTP] Stream server on port 81");
    }
}

// ============================================
// WIFI CONNECT
// ============================================

void wifi_connect() {
    lcd_show("SMART ATTEND", "Connecting WiFi");

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WIFI] Connected! IP: %s\n",
                      WiFi.localIP().toString().c_str());

        // Hiển thị IP trên LCD
        char ip_str[17];
        snprintf(ip_str, 17, "%s", WiFi.localIP().toString().c_str());
        lcd_show("IP Address:", ip_str);
        delay(2000);
    } else {
        Serial.println("\n[WIFI] FAILED to connect!");
        lcd_show("WIFI FAILED!", "Check settings");

        // Loop forever — cần restart ESP32
        while (true) {
            delay(1000);
        }
    }
}

// ============================================
// SETUP
// ============================================

void setup() {
    Serial.begin(115200);
    Serial.println("\n");
    Serial.println("=================================");
    Serial.println(" SMART ATTENDANCE - ESP32-S3");
    Serial.println("=================================");

    boot_time = millis();

    // 1. Init peripherals
    buzzer_init();
    relay_init();
    lcd_init();

    // 2. Init camera
    Serial.println("\n[INIT] Camera...");
    if (!camera_init()) {
        lcd_show("CAMERA ERROR!", "Check wiring");
        Serial.println("[FATAL] Camera init failed!");
        while (true) { delay(1000); }
    }

    // 3. Connect WiFi
    Serial.println("\n[INIT] WiFi...");
    wifi_connect();

    // 4. Start HTTP server
    Serial.println("\n[INIT] HTTP Server...");
    start_http_server();

    // 5. Ready!
    lcd_idle();
    buzzer_start_pattern(PATTERN_OK);

    Serial.println("\n=================================");
    Serial.println(" SYSTEM READY!");
    Serial.printf(" Camera:  http://%s/capture\n",
                  WiFi.localIP().toString().c_str());
    Serial.printf(" Stream:  http://%s:81/stream\n",
                  WiFi.localIP().toString().c_str());
    Serial.printf(" Control: http://%s/\n",
                  WiFi.localIP().toString().c_str());
    Serial.println("=================================\n");
}

// ============================================
// LOOP
// ============================================

void loop() {
    // Cập nhật relay timer (non-blocking close)
    relay_update();
    
    // Cập nhật buzzer state machine (non-blocking)
    buzzer_update();

    // Kiểm tra WiFi reconnect
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[WIFI] Disconnected! Reconnecting...");
        lcd_show("WIFI LOST!", "Reconnecting...");
        WiFi.reconnect();

        int retry = 0;
        while (WiFi.status() != WL_CONNECTED && retry < 20) {
            delay(500);
            retry++;
        }

        if (WiFi.status() == WL_CONNECTED) {
            Serial.println("[WIFI] Reconnected!");
            lcd_idle();
        }
    }

    // Xóa delay(10) vì làm chậm state machine
}
