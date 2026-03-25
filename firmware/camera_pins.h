/**
 * ============================================================
 *  CAMERA PIN DEFINITIONS - ESP32-S3
 * ============================================================
 *  Chọn 1 trong các board bên dưới bằng cách uncomment.
 *  Nếu board của bạn khác, tự sửa pin ở mục CUSTOM.
 * ============================================================
 */

#ifndef CAMERA_PINS_H
#define CAMERA_PINS_H

// ============================
// CHỌN BOARD CỦA BẠN TẠI ĐÂY
// ============================
// Uncomment ĐÚNG 1 dòng:

#define BOARD_ESP32S3_EYE        // Espressif ESP32-S3-EYE
// #define BOARD_FREENOVE_S3     // Freenove ESP32-S3 CAM
// #define BOARD_XIAO_S3        // Seeed XIAO ESP32-S3 Sense
// #define BOARD_CUSTOM          // Custom board (tự sửa pin)


// ============================================
// ESP32-S3-EYE (Espressif official)
// ============================================
#if defined(BOARD_ESP32S3_EYE)
  #define PWDN_GPIO_NUM    -1
  #define RESET_GPIO_NUM   -1
  #define XCLK_GPIO_NUM    15
  #define SIOD_GPIO_NUM    4
  #define SIOC_GPIO_NUM    5
  #define Y9_GPIO_NUM      16    // D7
  #define Y8_GPIO_NUM      17    // D6
  #define Y7_GPIO_NUM      18    // D5
  #define Y6_GPIO_NUM      12    // D4
  #define Y5_GPIO_NUM      10    // D3
  #define Y4_GPIO_NUM      8     // D2
  #define Y3_GPIO_NUM      9     // D1
  #define Y2_GPIO_NUM      11    // D0
  #define VSYNC_GPIO_NUM   6
  #define HREF_GPIO_NUM    7
  #define PCLK_GPIO_NUM    13

// ============================================
// FREENOVE ESP32-S3 CAM
// ============================================
#elif defined(BOARD_FREENOVE_S3)
  #define PWDN_GPIO_NUM    -1
  #define RESET_GPIO_NUM   -1
  #define XCLK_GPIO_NUM    15
  #define SIOD_GPIO_NUM    4
  #define SIOC_GPIO_NUM    5
  #define Y9_GPIO_NUM      16
  #define Y8_GPIO_NUM      17
  #define Y7_GPIO_NUM      18
  #define Y6_GPIO_NUM      12
  #define Y5_GPIO_NUM      10
  #define Y4_GPIO_NUM      8
  #define Y3_GPIO_NUM      9
  #define Y2_GPIO_NUM      11
  #define VSYNC_GPIO_NUM   6
  #define HREF_GPIO_NUM    7
  #define PCLK_GPIO_NUM    13

// ============================================
// SEEED XIAO ESP32-S3 SENSE
// ============================================
#elif defined(BOARD_XIAO_S3)
  #define PWDN_GPIO_NUM    -1
  #define RESET_GPIO_NUM   -1
  #define XCLK_GPIO_NUM    10
  #define SIOD_GPIO_NUM    40
  #define SIOC_GPIO_NUM    39
  #define Y9_GPIO_NUM      48
  #define Y8_GPIO_NUM      11
  #define Y7_GPIO_NUM      12
  #define Y6_GPIO_NUM      14
  #define Y5_GPIO_NUM      16
  #define Y4_GPIO_NUM      18
  #define Y3_GPIO_NUM      17
  #define Y2_GPIO_NUM      15
  #define VSYNC_GPIO_NUM   38
  #define HREF_GPIO_NUM    47
  #define PCLK_GPIO_NUM    13

// ============================================
// CUSTOM BOARD - TỰ SỬA PIN TẠI ĐÂY
// ============================================
#elif defined(BOARD_CUSTOM)
  #define PWDN_GPIO_NUM    -1
  #define RESET_GPIO_NUM   -1
  #define XCLK_GPIO_NUM    15
  #define SIOD_GPIO_NUM    4
  #define SIOC_GPIO_NUM    5
  #define Y9_GPIO_NUM      16
  #define Y8_GPIO_NUM      17
  #define Y7_GPIO_NUM      18
  #define Y6_GPIO_NUM      12
  #define Y5_GPIO_NUM      10
  #define Y4_GPIO_NUM      8
  #define Y3_GPIO_NUM      9
  #define Y2_GPIO_NUM      11
  #define VSYNC_GPIO_NUM   6
  #define HREF_GPIO_NUM    7
  #define PCLK_GPIO_NUM    13

#else
  #error "Hay chon board trong camera_pins.h!"
#endif

// ============================================
// PERIPHERAL PINS (LCD, Relay, Buzzer)
// Sửa nếu cần, tránh trùng với camera pins
// ============================================

// LCD1602 I2C
#define LCD_SDA_PIN        1
#define LCD_SCL_PIN        2
#define LCD_I2C_ADDR       0x27   // Đổi sang 0x3F nếu cần
#define LCD_COLS           16
#define LCD_ROWS           2

// Relay (khóa chốt điện từ)
// GPIO48 bị WS2812 on-board chiếm → dùng GPIO3
#define RELAY_PIN          3
#define RELAY_ACTIVE       HIGH   // HIGH = mở relay (tùy module)
#define RELAY_INACTIVE     LOW
#define RELAY_OPEN_MS      3000   // Thời gian mở mặc định (ms)

// Buzzer
// GPIO47 bị TFT LCD on-board chiếm → dùng GPIO14
#define BUZZER_PIN         14
#define BUZZER_ACTIVE      HIGH   // Buzzer 12095: (+)→GPIO14, (-)→GND = kêu khi HIGH

#endif // CAMERA_PINS_H
