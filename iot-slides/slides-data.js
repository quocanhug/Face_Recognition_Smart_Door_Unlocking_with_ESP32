// Slide data - each entry is raw HTML for one slide
const SLIDES = [

// ===== SLIDE 1: COVER =====
`<div class="flex flex-col items-center justify-center text-center min-h-[70vh]">
  <p class="text-[11px] font-bold text-slate-500 uppercase tracking-[.25em] mb-2">Trường Đại học Sư phạm Kỹ thuật TP.HCM · Môn: Vạn Vật Kết Nối</p>
  <p class="text-xs text-slate-600 mb-12">HK1 2025-2026 · Nhóm 02</p>
  <h1 class="sl-title text-center" style="font-size:clamp(2.2rem,5vw,3.8rem)">Hệ Thống Giám Sát An Ninh<br>& Điểm Danh Thời Gian Thực<br><span class="grad">Bằng Nhận Diện Khuôn Mặt</span></h1>
  <p class="text-slate-400 text-sm mb-12">ESP32-S3-CAM · Python Flask · Face Recognition · IoT</p>
  <div class="flex gap-8 justify-center flex-wrap mb-8">
    <div class="flex flex-col items-center gap-1"><div class="w-12 h-12 rounded-full bg-gradient-to-br from-[#00d2ff] to-[#0061ff] flex items-center justify-center text-slate-950 font-black">A</div><span class="text-sm font-semibold">Đinh Quốc Anh</span><span class="text-[10px] text-slate-500 font-mono">24133003</span></div>
    <div class="flex flex-col items-center gap-1"><div class="w-12 h-12 rounded-full bg-gradient-to-br from-[#00d2ff] to-[#0061ff] flex items-center justify-center text-slate-950 font-black">H</div><span class="text-sm font-semibold">Lý Gia Hân</span><span class="text-[10px] text-slate-500 font-mono">24131016</span></div>
    <div class="flex flex-col items-center gap-1"><div class="w-12 h-12 rounded-full bg-gradient-to-br from-[#00d2ff] to-[#0061ff] flex items-center justify-center text-slate-950 font-black">T</div><span class="text-sm font-semibold">Đỗ Thanh Thành Tài</span><span class="text-[10px] text-slate-500 font-mono">24133050</span></div>
  </div>
  <div class="gc inline-flex px-6 py-2 text-sm">GVHD: <strong class="text-white ml-1">ThS. Đinh Công Đoan</strong></div>
</div>`,

// ===== SLIDE 2: MỤC LỤC =====
`<div class="sl-head"><div class="line"></div><span>Overview</span></div>
<h2 class="sl-title">Nội Dung <span class="grad">Trình Bày</span></h2>
<div class="sl-grid c3">
  <div class="gc"><span class="ic">📋</span><h4>Phần 1: Mở đầu</h4><p>Đặt vấn đề, tính cấp thiết, mục tiêu nghiên cứu</p></div>
  <div class="gc"><span class="ic">🏗️</span><h4>Phần 2: Kiến trúc</h4><p>Thiết kế hệ thống, lựa chọn công nghệ</p></div>
  <div class="gc"><span class="ic">🔧</span><h4>Phần 3: Phần cứng</h4><p>ESP32-S3, Relay, LCD, Khóa điện từ</p></div>
  <div class="gc"><span class="ic">💻</span><h4>Phần 4: Phần mềm</h4><p>Nguyên lý hoạt động, giao diện web, an ninh</p></div>
  <div class="gc"><span class="ic">📊</span><h4>Phần 5: Kết quả</h4><p>Thực nghiệm, khó khăn & giải pháp</p></div>
  <div class="gc"><span class="ic">🎯</span><h4>Phần 6: Kết luận</h4><p>Đánh giá, hướng phát triển</p></div>
</div>`,

// ===== SLIDE 3: ĐẶT VẤN ĐỀ =====
`<div class="sl-head"><div class="line"></div><span>Mở đầu · Problem Statement</span></div>
<h2 class="sl-title">Đặt <span class="grad">Vấn Đề</span></h2>
<p class="text-slate-400 text-sm mb-6">Thực trạng kiểm soát ra vào phòng thực hành tại các trường đại học</p>
<div class="sl-grid c3">
  <div class="gc"><span class="ic">🔑</span><h4>Chìa khóa / Thẻ từ</h4><p>Dễ mất, dễ sao chép, không xác thực được danh tính thực sự</p></div>
  <div class="gc"><span class="ic">🔢</span><h4>Mã PIN</h4><p>Dễ lộ khi nhập nơi đông người, có thể chia sẻ, quên mã</p></div>
  <div class="gc"><span class="ic">📝</span><h4>Sổ ký tay</h4><p>Không truy vết được chính xác khi xảy ra sự cố</p></div>
</div>
<div class="callout">
  <p>📊 Theo <strong>Verizon Data Breach Report (2023)</strong>: hơn <strong>80%</strong> các vụ xâm nhập trái phép liên quan đến thông tin xác thực bị đánh cắp hoặc bị đoán.</p>
</div>`,

// ===== SLIDE 4: TÍNH CẤP THIẾT =====
`<div class="sl-head"><div class="line"></div><span>Background & Rationale</span></div>
<h2 class="sl-title">Tính Cấp Thiết & <span class="grad">Lý Do Chọn Đề Tài</span></h2>
<div class="sl-grid c7-5">
  <div class="gc" style="border-left:4px solid rgba(0,210,255,.4)">
    <h4 class="flex items-center gap-2 mb-4"><span class="material-symbols-outlined text-[#00d2ff]">psychology</span> Tại sao nhận diện khuôn mặt?</h4>
    <div class="sl-grid c2">
      <div><p class="text-[#00d2ff] text-[10px] font-bold uppercase tracking-widest mb-1">Security First</p><p class="text-slate-400 text-sm border-l border-slate-800 pl-3">Không thể để quên, sao chép hay chuyển nhượng</p></div>
      <div><p class="text-[#00d2ff] text-[10px] font-bold uppercase tracking-widest mb-1">Post-COVID Norm</p><p class="text-slate-400 text-sm border-l border-slate-800 pl-3">Không tiếp xúc (contactless) - xu hướng toàn cầu</p></div>
      <div><p class="text-[#00d2ff] text-[10px] font-bold uppercase tracking-widest mb-1">Smart Tracking</p><p class="text-slate-400 text-sm border-l border-slate-800 pl-3">Xác thực chính xác, ghi log tự động 24/7</p></div>
      <div><p class="text-[#00d2ff] text-[10px] font-bold uppercase tracking-widest mb-1">Economic Value</p><p class="text-slate-400 text-sm border-l border-slate-800 pl-3">ESP32-S3-CAM <span class="text-white font-bold">chưa đến 200.000 VNĐ</span></p></div>
    </div>
  </div>
  <div class="gc">
    <h4 class="flex items-center gap-2 mb-4"><span class="material-symbols-outlined text-[#0061ff]">search_insights</span> Khoảng trống nghiên cứu</h4>
    <ul class="space-y-4">
      <li class="flex gap-3"><div class="icon-box bg-red-500/10 border border-red-500/20"><span class="material-symbols-outlined text-red-400 text-lg">money_off</span></div><div><p class="text-sm text-slate-300">Raspberry Pi cost barrier</p><p class="text-xs text-slate-500">Chi phí cao <span class="text-red-400 font-bold">(1.2-1.5 triệu)</span></p></div></li>
      <li class="flex gap-3"><div class="icon-box bg-cyan-500/10 border border-cyan-500/20"><span class="material-symbols-outlined text-[#00d2ff] text-lg">developer_board</span></div><div><p class="text-sm text-slate-300">ESP32 Underexploited</p><p class="text-xs text-slate-500">Chưa khai thác trong nhận diện khuôn mặt</p></div></li>
      <li class="flex gap-3"><div class="icon-box bg-green-500/10 border border-green-500/20"><span class="material-symbols-outlined text-green-400 text-lg">rocket_launch</span></div><div><p class="text-sm text-slate-300">Scalability Gap</p><p class="text-xs text-slate-500">Cơ hội giải pháp chi phí thấp</p></div></li>
    </ul>
  </div>
</div>
<div class="callout" style="border-left-color:#00f2fe;background:linear-gradient(90deg,rgba(0,242,254,.06),rgba(0,97,255,.03))">
  <p class="flex items-center gap-3"><span class="material-symbols-outlined text-[#00d2ff] text-2xl" style="font-variation-settings:'FILL' 1">lightbulb</span>
  <span class="text-lg font-bold text-white italic">"Chứng minh tính khả thi của kiến trúc <span class="text-[#00d2ff] glow-text">thiết bị nhúng rẻ + server AI</span> trong bài toán bảo mật thực tiễn"</span></p>
</div>`,

// ===== SLIDE 5: MỤC TIÊU =====
`<div class="sl-head"><div class="line"></div><span>Objectives</span></div>
<h2 class="sl-title">Mục Tiêu <span class="grad">Đề Tài</span></h2>
<div class="sl-grid c3" style="margin-bottom:20px">
  <div class="gc text-center stat-hover"><p class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#00d2ff] to-[#0061ff]">≥90%</p><p class="text-xs text-slate-500 mt-1">Độ chính xác nhận diện</p></div>
  <div class="gc text-center stat-hover"><p class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#00d2ff] to-[#0061ff]">≤3s</p><p class="text-xs text-slate-500 mt-1">Thời gian phản hồi</p></div>
  <div class="gc text-center stat-hover"><p class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#00d2ff] to-[#0061ff]">≤5%</p><p class="text-xs text-slate-500 mt-1">False Acceptance Rate</p></div>
</div>
<ul class="list-feat">
  <li><span class="text-[#00d2ff]">📸</span> Lập trình ESP32-S3-CAM thu thập ảnh JPEG và truyền lên server qua HTTP POST</li>
  <li><span class="text-[#00d2ff]">🧠</span> Xây dựng server Python với endpoint nhận diện khuôn mặt trả về JSON</li>
  <li><span class="text-[#00d2ff]">👥</span> CSDL khuôn mặt: tối thiểu 5 người, 15–20 ảnh/người</li>
  <li><span class="text-[#00d2ff]">🔓</span> Điều khiển relay + khóa điện từ JF-0826B mở 3 giây khi nhận diện thành công</li>
  <li><span class="text-[#00d2ff]">📺</span> Hiển thị tên/từ chối trên LCD 1602 I2C + ghi log CSV</li>
</ul>`,

// ===== SLIDE 6: KIẾN TRÚC HỆ THỐNG =====
`<div class="sl-head"><div class="line"></div><span>System Architecture</span></div>
<h2 class="sl-title">Kiến Trúc <span class="grad">Tổng Thể Hệ Thống</span></h2>
<p class="text-slate-400 text-sm mb-6">Mô hình Client-Server hai tầng trong mạng LAN nội bộ</p>
<div class="flex flex-col gap-4 items-center">
  <div class="flex gap-4 flex-wrap justify-center">
    <div class="gc text-center px-6 py-4 stat-hover" style="border-color:rgba(0,210,255,.25)"><span class="material-symbols-outlined text-[#00d2ff] text-2xl">language</span><p class="text-sm font-bold mt-2">Web Dashboard</p><p class="text-[10px] text-slate-500">HTML/CSS/JS</p></div>
    <div class="gc text-center px-6 py-4 stat-hover" style="border-color:rgba(0,210,255,.25)"><span class="material-symbols-outlined text-[#00d2ff] text-2xl">send</span><p class="text-sm font-bold mt-2">Telegram Bot</p><p class="text-[10px] text-slate-500">Cảnh báo từ xa</p></div>
  </div>
  <p class="text-[#00d2ff] text-xs font-bold">⬇️ HTTP / WebSocket ⬇️</p>
  <div class="flex gap-4 flex-wrap justify-center">
    <div class="gc text-center px-6 py-4 stat-hover" style="border-color:rgba(139,92,246,.25)"><span class="material-symbols-outlined text-purple-400 text-2xl">psychology</span><p class="text-sm font-bold mt-2">AI Server (Python)</p><p class="text-[10px] text-slate-500">FastAPI + Face Recognition</p></div>
    <div class="gc text-center px-6 py-4 stat-hover" style="border-color:rgba(139,92,246,.25)"><span class="material-symbols-outlined text-purple-400 text-2xl">database</span><p class="text-sm font-bold mt-2">Database</p><p class="text-[10px] text-slate-500">SQLite + encodings.pkl</p></div>
  </div>
  <p class="text-[#00d2ff] text-xs font-bold">⬇️ HTTP REST API ⬇️</p>
  <div class="flex gap-4 flex-wrap justify-center">
    <div class="gc text-center px-6 py-4 stat-hover" style="border-color:rgba(34,197,94,.25)"><span class="material-symbols-outlined text-green-400 text-2xl">photo_camera</span><p class="text-sm font-bold mt-2">ESP32-S3-CAM</p><p class="text-[10px] text-slate-500">Camera OV3660</p></div>
    <div class="gc text-center px-6 py-4 stat-hover" style="border-color:rgba(255,107,53,.25)"><span class="material-symbols-outlined text-orange-400 text-2xl">lock_open</span><p class="text-sm font-bold mt-2">Relay + Khóa JF-0826B</p><p class="text-[10px] text-slate-500">Fail-Secure 12V</p></div>
    <div class="gc text-center px-6 py-4 stat-hover" style="border-color:rgba(236,72,153,.25)"><span class="material-symbols-outlined text-pink-400 text-2xl">tv</span><p class="text-sm font-bold mt-2">LCD 1602 I2C</p><p class="text-[10px] text-slate-500">Phản hồi trực quan</p></div>
  </div>
</div>`,

// ===== SLIDE 7: THÀNH PHẦN =====
`<div class="sl-head"><div class="line"></div><span>System Components</span></div>
<h2 class="sl-title">6 Khối <span class="grad">Chức Năng Chính</span></h2>
<div class="sl-grid c3">
  <div class="gc stat-hover"><span class="ic">🧠</span><h4>Khối Xử lý Trung tâm</h4><p>ESP32-S3-CAM N16R8 — "bộ não" phần cứng, điều phối camera, relay, LCD</p></div>
  <div class="gc stat-hover"><span class="ic">📷</span><h4>Khối Đầu vào</h4><p>Camera OV3660 QVGA 320×240, nút nhấn kích hoạt, ảnh JPEG 10-25KB</p></div>
  <div class="gc stat-hover"><span class="ic">⚡</span><h4>Khối Chấp hành</h4><p>Module Relay 5V + Khóa JF-0826B 12V, Fail-Secure, tự khóa sau 3s</p></div>
  <div class="gc stat-hover"><span class="ic">🖥️</span><h4>Khối Server</h4><p>Python FastAPI + face_recognition + ResNet-34, pipeline AI nhận diện</p></div>
  <div class="gc stat-hover"><span class="ic">📡</span><h4>Khối Giao tiếp mạng</h4><p>Wi-Fi 802.11 b/g/n, HTTP POST image/jpeg, JSON ≤500ms</p></div>
  <div class="gc stat-hover"><span class="ic">📺</span><h4>Khối Hiển thị</h4><p>LCD 1602 I2C (PCF8574), 2 dây SDA/SCL, phản hồi tức thì</p></div>
</div>`,

// ===== SLIDE 8: YÊU CẦU =====
`<div class="sl-head"><div class="line"></div><span>Requirements</span></div>
<h2 class="sl-title">Yêu Cầu <span class="grad">Hệ Thống</span></h2>
<div class="sl-grid c2">
  <div>
    <h4 class="text-white font-bold mb-3 flex items-center gap-2"><span class="material-symbols-outlined text-[#00d2ff]">checklist</span> Yêu cầu chức năng</h4>
    <table><thead><tr><th>Yêu cầu</th><th>Mô tả</th></tr></thead><tbody>
      <tr><td>📸 Thu thập ảnh</td><td>Chụp khuôn mặt qua OV3660 khi nhấn nút</td></tr>
      <tr><td>🧠 Nhận diện</td><td>Server xác định danh tính, trả JSON</td></tr>
      <tr><td>🔓 Kiểm soát khóa</td><td>Tự động mở JF-0826B 3s khi thành công</td></tr>
      <tr><td>📺 Hiển thị</td><td>LCD hiển thị tên/từ chối</td></tr>
      <tr><td>👤 Đăng ký mới</td><td>Thêm khuôn mặt qua server</td></tr>
      <tr><td>📝 Ghi nhật ký</td><td>Log tên, thời gian, kết quả CSV</td></tr>
      <tr><td>⚠️ Phân biệt người lạ</td><td>Từ chối + cảnh báo khi không có trong CSDL</td></tr>
    </tbody></table>
  </div>
  <div>
    <h4 class="text-white font-bold mb-3 flex items-center gap-2"><span class="material-symbols-outlined text-[#00d2ff]">tune</span> Yêu cầu phi chức năng</h4>
    <div class="space-y-3">
      <div class="gc"><h4>⚡ Hiệu năng</h4><p>Chụp → mở khóa ≤3s · Nhận diện ≤2s/ảnh · Truyền Wi-Fi ≤500ms</p></div>
      <div class="gc"><h4>🎯 Độ chính xác</h4><p>TPR ≥90% · FAR ≤5%</p></div>
      <div class="gc"><h4>🔄 Ổn định</h4><p>Liên tục ≥8h · Tự kết nối lại Wi-Fi · Hiển thị lỗi rõ ràng</p></div>
      <div class="gc"><h4>🔒 Bảo mật</h4><p>Fail-Secure khi mất điện · Ghi log mọi thất bại</p></div>
    </div>
  </div>
</div>`,

// ===== SLIDE 9: LỰA CHỌN CÔNG NGHỆ =====
`<div class="sl-head"><div class="line"></div><span>Technology Selection</span></div>
<h2 class="sl-title">Lựa Chọn <span class="grad">Công Nghệ</span></h2>
<div class="sl-grid c2">
  <div>
    <h4 class="text-white font-bold mb-3">Vi điều khiển</h4>
    <table><thead><tr><th>Tiêu chí</th><th>RPi 4</th><th>ESP32-CAM</th><th>ESP32-S3 ✅</th></tr></thead><tbody>
      <tr><td>PSRAM</td><td>4GB</td><td>4MB</td><td class="text-[#00d2ff] font-bold">8MB</td></tr>
      <tr><td>Flash</td><td>SD</td><td>4MB</td><td class="text-[#00d2ff] font-bold">16MB</td></tr>
      <tr><td>Chi phí</td><td class="text-red-400">~1.5tr</td><td>~80K</td><td class="text-green-400 font-bold">~200K</td></tr>
      <tr><td>Tiêu thụ</td><td>~3W</td><td>~0.5W</td><td class="font-bold">~0.5W</td></tr>
    </tbody></table>
  </div>
  <div>
    <h4 class="text-white font-bold mb-3">Thuật toán nhận diện</h4>
    <table><thead><tr><th>Thuật toán</th><th>Chính xác</th><th>Tốc độ</th></tr></thead><tbody>
      <tr><td>Haar + LBPH</td><td>75-85%</td><td>Rất nhanh</td></tr>
      <tr><td>HOG + SVM</td><td>85-90%</td><td>Nhanh</td></tr>
      <tr><td class="text-[#00d2ff] font-bold">face_recognition ✅</td><td class="text-[#00d2ff] font-bold">92-97%</td><td>1-2s/ảnh</td></tr>
    </tbody></table>
  </div>
</div>
<div class="callout"><p>🏆 <strong>Kiến trúc Client-Server</strong> được chọn: độ chính xác ~93% (vs 85% on-device), mở rộng không giới hạn người dùng, dễ nâng cấp thuật toán</p></div>`,

// ===== SLIDE 10: LINH KIỆN (IMAGE PLACEHOLDERS) =====
`<div class="sl-head"><div class="line"></div><span>Hardware Components</span></div>
<h2 class="sl-title">Linh Kiện <span class="grad">Phần Cứng</span></h2>
<div class="sl-grid c3">
  <div class="gc stat-hover">
    <h4>📸 ESP32-S3-CAM N16R8</h4>
    <div class="img-placeholder my-3" style="min-height:150px"><span class="material-symbols-outlined text-3xl">add_photo_alternate</span><span class="text-xs">Thêm hình ESP32-S3-CAM</span></div>
    <p>Xtensa LX7 240MHz, 8MB PSRAM, 16MB Flash, Wi-Fi, Camera DVP</p>
  </div>
  <div class="gc stat-hover">
    <h4>⚡ Module Relay 12V</h4>
    <div class="img-placeholder my-3" style="min-height:150px"><span class="material-symbols-outlined text-3xl">add_photo_alternate</span><span class="text-xs">Thêm hình Module Relay</span></div>
    <p>250VAC/10A, optocoupler PC817 cách ly, kích tự giữ</p>
  </div>
  <div class="gc stat-hover">
    <h4>📺 LCD 1602 I2C</h4>
    <div class="img-placeholder my-3" style="min-height:150px"><span class="material-symbols-outlined text-3xl">add_photo_alternate</span><span class="text-xs">Thêm hình LCD 1602</span></div>
    <p>16×2 ký tự, chip PCF8574, I2C 100kHz, chỉ 2 dây SDA+SCL</p>
  </div>
  <div class="gc stat-hover">
    <h4>🔓 Khóa JF-0826B 12V</h4>
    <div class="img-placeholder my-3" style="min-height:150px"><span class="material-symbols-outlined text-3xl">add_photo_alternate</span><span class="text-xs">Thêm hình Khóa chốt</span></div>
    <p>Solenoid Fail-Secure, 2A, mở 50-80ms, tự khóa khi mất điện</p>
  </div>
  <div class="gc stat-hover">
    <h4>🔌 Adapter 12V-2A</h4>
    <div class="img-placeholder my-3" style="min-height:150px"><span class="material-symbols-outlined text-3xl">add_photo_alternate</span><span class="text-xs">Thêm hình Adapter</span></div>
    <p>24W output, biên dự phòng 2.5× so với thực tế ~9W</p>
  </div>
  <div class="gc stat-hover">
    <h4>🔔 Buzzer Active 5V</h4>
    <div class="img-placeholder my-3" style="min-height:150px"><span class="material-symbols-outlined text-3xl">add_photo_alternate</span><span class="text-xs">Thêm hình Buzzer</span></div>
    <p>3 pattern: 1 beep thành công, 2 beep từ chối, 3 beep lỗi</p>
  </div>
</div>`,

// ===== SLIDE 11: SƠ ĐỒ + MÔ HÌNH =====
`<div class="sl-head"><div class="line"></div><span>Hardware Wiring & Assembly</span></div>
<h2 class="sl-title">Sơ Đồ Kết Nối & <span class="grad">Mô Hình Thực Tế</span></h2>
<div class="sl-grid c2">
  <div>
    <h4 class="text-white font-bold mb-3">Sơ đồ mạch nguyên lý</h4>
    <div class="img-placeholder" style="min-height:280px"><span class="material-symbols-outlined text-4xl">add_photo_alternate</span><span class="text-sm">Thêm hình sơ đồ mạch nguyên lý</span></div>
    <table class="mt-4"><thead><tr><th>GPIO</th><th>Kết nối</th><th>Chức năng</th></tr></thead><tbody>
      <tr><td>GPIO 0</td><td>Nút nhấn</td><td>Kích hoạt</td></tr>
      <tr><td>GPIO 1</td><td>LCD SDA</td><td>I2C Data</td></tr>
      <tr><td>GPIO 2</td><td>LCD SCL</td><td>I2C Clock</td></tr>
      <tr><td>GPIO 3</td><td>Relay IN</td><td>Đóng/ngắt khóa</td></tr>
      <tr><td>GPIO 14</td><td>Buzzer</td><td>Âm thanh cảnh báo</td></tr>
    </tbody></table>
  </div>
  <div>
    <h4 class="text-white font-bold mb-3">Mô hình lắp ráp thực tế</h4>
    <div class="img-placeholder mb-4" style="min-height:200px"><span class="material-symbols-outlined text-4xl">add_photo_alternate</span><span class="text-sm">Thêm hình mặt trước mô hình</span></div>
    <div class="img-placeholder" style="min-height:200px"><span class="material-symbols-outlined text-4xl">add_photo_alternate</span><span class="text-sm">Thêm hình mặt sau mô hình</span></div>
    <div class="callout mt-4"><p>⚡ <strong>Bảo vệ mạch:</strong> Diode 1N4007 triệt Back-EMF · Buck Converter 12V→5V hiệu suất >90%</p></div>
  </div>
</div>`,

// ===== SLIDE 12: NGUYÊN LÝ HOẠT ĐỘNG =====
`<div class="sl-head"><div class="line"></div><span>Operating Principle</span></div>
<h2 class="sl-title">Nguyên Lý <span class="grad">Hoạt Động</span></h2>
<div class="sl-grid c2">
  <div class="gc" style="border-left:4px solid rgba(34,197,94,.4)">
    <h4 class="text-green-400 flex items-center gap-2 mb-4"><span class="material-symbols-outlined">check_circle</span> Nhận diện thành công</h4>
    <ul class="list-feat">
      <li><span>1️⃣</span> Nhấn nút → Camera chụp JPEG</li>
      <li><span>2️⃣</span> HTTP POST → Server xử lý AI</li>
      <li><span>3️⃣</span> JSON → Tên người dùng (score ≥ 0.80)</li>
      <li><span>4️⃣</span> GPIO HIGH → Relay → Khóa mở 3s</li>
      <li><span>5️⃣</span> LCD: "CHAO MUNG! / [Tên]"</li>
      <li><span>6️⃣</span> Buzzer 1 beep · Log SUCCESS</li>
    </ul>
  </div>
  <div class="gc" style="border-left:4px solid rgba(239,68,68,.4)">
    <h4 class="text-red-400 flex items-center gap-2 mb-4"><span class="material-symbols-outlined">cancel</span> Từ chối truy cập</h4>
    <ul class="list-feat">
      <li><span>1️⃣</span> Khuôn mặt không khớp CSDL</li>
      <li><span>2️⃣</span> Relay OFF → Cửa vẫn KHÓA</li>
      <li><span>3️⃣</span> LCD: "ACCESS DENY"</li>
      <li><span>4️⃣</span> Buzzer 2 beep dài cảnh báo</li>
      <li><span>5️⃣</span> deny_count++ → Leo thang</li>
      <li><span>6️⃣</span> Vượt ngưỡng → Telegram + Còi 30s</li>
    </ul>
  </div>
</div>`,

// ===== SLIDE 13: GIAO DIỆN WEB =====
`<div class="sl-head"><div class="line"></div><span>Web Interface</span></div>
<h2 class="sl-title">Giao Diện <span class="grad">Web Dashboard</span></h2>
<div class="sl-grid c2">
  <div class="gc stat-hover">
    <h4>📊 Dashboard — Điểm danh</h4>
    <div class="img-placeholder my-3" style="min-height:220px"><span class="material-symbols-outlined text-4xl">add_photo_alternate</span><span class="text-sm">Thêm hình giao diện Dashboard</span></div>
    <p>Camera MJPEG 20FPS, nhật ký real-time, nút khóa/mở phòng</p>
  </div>
  <div class="gc stat-hover">
    <h4>📋 Lịch sử điểm danh</h4>
    <div class="img-placeholder my-3" style="min-height:220px"><span class="material-symbols-outlined text-4xl">add_photo_alternate</span><span class="text-sm">Thêm hình giao diện lịch sử</span></div>
    <p>Thống kê tổng hợp, lọc theo thời gian, xuất CSV</p>
  </div>
  <div class="gc stat-hover">
    <h4>🚨 Cảnh báo an ninh</h4>
    <div class="img-placeholder my-3" style="min-height:220px"><span class="material-symbols-outlined text-4xl">add_photo_alternate</span><span class="text-sm">Thêm hình cảnh báo an ninh</span></div>
    <p>Banner real-time khi phát hiện người lạ, gửi Telegram</p>
  </div>
  <div class="gc stat-hover">
    <h4>👥 Thêm người dùng mới</h4>
    <div class="img-placeholder my-3" style="min-height:220px"><span class="material-symbols-outlined text-4xl">add_photo_alternate</span><span class="text-sm">Thêm hình đăng ký người dùng</span></div>
    <p>Tạo tài khoản, Enroll khuôn mặt, trích xuất vector tự động</p>
  </div>
</div>`,

// ===== SLIDE 14: AN NINH =====
`<div class="sl-head"><div class="line"></div><span>Security Mechanism</span></div>
<h2 class="sl-title">Cơ Chế <span class="grad">An Ninh Thông Minh</span></h2>
<div class="sl-grid c2">
  <div class="gc stat-hover"><h4 class="flex items-center gap-2"><span class="material-symbols-outlined text-[#00d2ff]">timer</span> Debounce 30s</h4><p>Bỏ qua yêu cầu trùng lặp từ cùng người trong 30 giây — tránh ghi điểm danh trùng</p></div>
  <div class="gc stat-hover"><h4 class="flex items-center gap-2"><span class="material-symbols-outlined text-[#00d2ff]">hourglass_top</span> Cooldown 5s</h4><p>Khoảng trễ giữa 2 lần cảnh báo người lạ — tránh spam Buzzer và Telegram</p></div>
  <div class="gc stat-hover"><h4 class="flex items-center gap-2"><span class="material-symbols-outlined text-red-400">trending_up</span> Leo thang phản ứng</h4><p>deny_count vượt ngưỡng → Gửi ảnh xâm nhập qua Telegram + Hú còi 30s</p></div>
  <div class="gc stat-hover"><h4 class="flex items-center gap-2"><span class="material-symbols-outlined text-purple-400">dark_mode</span> Night Mode Auto-lock</h4><p>Tự động khóa phòng ban đêm theo lịch trình, hỗ trợ khóa thủ công từ xa</p></div>
</div>`,

// ===== SLIDE 15: KẾT QUẢ THỰC NGHIỆM =====
`<div class="sl-head"><div class="line"></div><span>Experimental Results</span></div>
<h2 class="sl-title">Kết Quả <span class="grad">Thực Nghiệm</span></h2>
<table><thead><tr><th>Kịch bản</th><th>Kết quả</th><th>Thời gian</th></tr></thead><tbody>
  <tr><td>✅ Nhận diện hợp lệ</td><td>LCD tên, Buzzer 1 beep, Relay mở 3s</td><td>~2 giây</td></tr>
  <tr><td>❌ Không hợp lệ</td><td>LCD "ACCESS DENY", Buzzer 2 beep, cửa khóa</td><td>~2 giây</td></tr>
  <tr><td>🔄 Debounce test</td><td>"DA DIEM DANH", không ghi trùng</td><td>< 30s</td></tr>
  <tr><td>🌐 Điều khiển từ xa</td><td>Dashboard → "MỞ KHÓA" → khóa mở 3s</td><td>< 1 giây</td></tr>
  <tr><td>👤 Đăng ký mới</td><td>3-5 ảnh → vector 512-D → nhận diện ngay</td><td>~10 giây</td></tr>
  <tr><td>🔌 Fail-Secure test</td><td>Ngắt nguồn → lò xo đẩy chốt → cửa KHÓA</td><td>Tức thì</td></tr>
</tbody></table>
<div class="sl-grid c3" style="margin-top:20px">
  <div class="gc text-center stat-hover"><p class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#00d2ff] to-[#0061ff]">~2s</p><p class="text-xs text-slate-500">Phản hồi TB</p></div>
  <div class="gc text-center stat-hover"><p class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#00d2ff] to-[#0061ff]">>90%</p><p class="text-xs text-slate-500">Độ chính xác</p></div>
  <div class="gc text-center stat-hover"><p class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#00d2ff] to-[#0061ff]">8h+</p><p class="text-xs text-slate-500">Hoạt động liên tục</p></div>
</div>`,

// ===== SLIDE 16: KHÓ KHĂN =====
`<div class="sl-head"><div class="line"></div><span>Challenges & Solutions</span></div>
<h2 class="sl-title">Khó Khăn & <span class="grad">Giải Pháp</span></h2>
<div class="sl-grid c2">
  <div class="gc stat-hover"><h4>⚡ Sụt áp & Back-EMF</h4><p>Dòng khởi động 500mA gây reset ESP32</p><div class="callout mt-3"><p>✅ <strong>Giải pháp:</strong> Tách nguồn 12V/5V + Diode 1N4007 triệt Back-EMF</p></div></div>
  <div class="gc stat-hover"><h4>📌 Xung đột GPIO</h4><p>DVP camera + PSRAM chiếm hầu hết GPIO</p><div class="callout mt-3"><p>✅ <strong>Giải pháp:</strong> LCD qua I2C chỉ 2 dây, dùng GPIO 3/14 an toàn</p></div></div>
  <div class="gc stat-hover"><h4>⏱️ Độ trễ & Bottleneck</h4><p>AI block event loop, server không phản hồi</p><div class="callout mt-3"><p>✅ <strong>Giải pháp:</strong> run_in_executor() + QVGA 320×240 + JPEG 70%</p></div></div>
  <div class="gc stat-hover"><h4>🔆 Sai số môi trường</h4><p>Ánh sáng/góc thay đổi giảm chính xác</p><div class="callout mt-3"><p>✅ <strong>Giải pháp:</strong> Hybrid Metric (70% Cosine + 30% L2) + Mean Embedding 15-20 ảnh</p></div></div>
</div>`,

// ===== SLIDE 17: KẾT QUẢ ĐẠT ĐƯỢC =====
`<div class="sl-head"><div class="line"></div><span>Achievements</span></div>
<h2 class="sl-title">Kết Quả <span class="grad">Đạt Được</span></h2>
<ul class="list-feat">
  <li><div class="icon-box bg-cyan-500/10 border border-cyan-500/20 mr-1"><span class="material-symbols-outlined text-[#00d2ff]">hub</span></div> <div><strong class="text-white">Hệ sinh thái AIoT tích hợp:</strong> Hội tụ Computer Vision + IoT, tự động hóa hoàn chỉnh từ biên đến server</div></li>
  <li><div class="icon-box bg-purple-500/10 border border-purple-500/20 mr-1"><span class="material-symbols-outlined text-purple-400">psychology</span></div> <div><strong class="text-white">Thuật toán nhận diện đa tầng:</strong> Hybrid Model kết hợp Cosine + L2, ngưỡng 0.80, >90% chính xác</div></li>
  <li><div class="icon-box bg-green-500/10 border border-green-500/20 mr-1"><span class="material-symbols-outlined text-green-400">memory</span></div> <div><strong class="text-white">Hạ tầng phần cứng hoàn chỉnh:</strong> ESP32-S3 + OV3660 + LCD + Relay + Buzzer, chu trình khép kín</div></li>
  <li><div class="icon-box bg-blue-500/10 border border-blue-500/20 mr-1"><span class="material-symbols-outlined text-blue-400">language</span></div> <div><strong class="text-white">Web Dashboard real-time:</strong> FastAPI + WebSocket + MJPEG 20FPS, quản lý điểm danh và an ninh</div></li>
  <li><div class="icon-box bg-red-500/10 border border-red-500/20 mr-1"><span class="material-symbols-outlined text-red-400">shield</span></div> <div><strong class="text-white">An ninh thông minh:</strong> Day/Night auto-lock, leo thang cảnh báo, Telegram Bot API</div></li>
</ul>`,

// ===== SLIDE 18: ƯU NHƯỢC ĐIỂM =====
`<div class="sl-head"><div class="line"></div><span>Evaluation</span></div>
<h2 class="sl-title">Ưu Điểm & <span class="grad">Nhược Điểm</span></h2>
<div class="sl-grid c2">
  <div class="gc" style="border-left:4px solid rgba(34,197,94,.4)">
    <h4 class="text-green-400 mb-4">✅ Ưu điểm</h4>
    <ul class="list-feat">
      <li><span>•</span> Số hóa quy trình, loại bỏ rủi ro thẻ từ/chìa khóa</li>
      <li><span>•</span> Giám sát real-time qua WebSocket + MJPEG</li>
      <li><span>•</span> Bảo mật dữ liệu tập trung tại server</li>
      <li><span>•</span> Chi phí phần cứng thấp (~200K ESP32)</li>
      <li><span>•</span> Linh hoạt, tương thích cao</li>
    </ul>
  </div>
  <div class="gc" style="border-left:4px solid rgba(239,68,68,.4)">
    <h4 class="text-red-400 mb-4">⚠️ Nhược điểm</h4>
    <ul class="list-feat">
      <li><span>•</span> Phụ thuộc Wi-Fi — timeout khi nghẽn mạng</li>
      <li><span>•</span> Camera OV3660 giới hạn ánh sáng kém</li>
      <li><span>•</span> AI nặng — cần CPU/GPU server tốt</li>
      <li><span>•</span> SQLite chỉ phù hợp prototype</li>
      <li><span>•</span> Chưa có anti-spoofing</li>
    </ul>
  </div>
</div>`,

// ===== SLIDE 19: HƯỚNG PHÁT TRIỂN =====
`<div class="sl-head"><div class="line"></div><span>Future Work</span></div>
<h2 class="sl-title">Hướng <span class="grad">Phát Triển</span></h2>
<div class="sl-grid c2">
  <div class="gc stat-hover"><h4 class="flex items-center gap-2"><span class="material-symbols-outlined text-[#00d2ff]">camera_enhance</span> Nâng cấp camera</h4><p>Camera độ phân giải cao + cảm biến hồng ngoại (IR) cho nhận diện ban đêm</p></div>
  <div class="gc stat-hover"><h4 class="flex items-center gap-2"><span class="material-symbols-outlined text-[#00d2ff]">shield</span> Anti-Spoofing</h4><p>Liveness Detection dựa trên chuyển động hoặc chiều sâu — chống ảnh 2D/video</p></div>
  <div class="gc stat-hover"><h4 class="flex items-center gap-2"><span class="material-symbols-outlined text-[#00d2ff]">cloud</span> Cloud & Tăng tốc</h4><p>TensorRT/ONNX + PostgreSQL/MySQL + Cloud đa chi nhánh</p></div>
  <div class="gc stat-hover"><h4 class="flex items-center gap-2"><span class="material-symbols-outlined text-[#00d2ff]">smartphone</span> Mobile App</h4><p>Native App + Push Notification tức thời, quản lý từ xa</p></div>
</div>
<div class="callout"><p>🔐 <strong>MFA (Multi-Factor Authentication):</strong> Tích hợp RFID hoặc vân tay tại biên (Edge), đảm bảo vận hành khi mất kết nối Server</p></div>`,

// ===== SLIDE 20: CẢM ƠN =====
`<div class="flex flex-col items-center justify-center text-center min-h-[60vh]">
  <p class="text-6xl mb-6" style="animation:float 3s ease-in-out infinite">🎓</p>
  <h1 class="sl-title text-center" style="font-size:clamp(2rem,5vw,3.5rem)"><span class="grad">Cảm Ơn Thầy Và Các Bạn</span><br>Đã Lắng Nghe!</h1>
  <p class="text-slate-400 text-sm mb-10">Hệ thống giám sát an ninh & điểm danh thời gian thực bằng nhận diện khuôn mặt</p>
  <div class="flex gap-8 justify-center flex-wrap mb-8">
    <div class="flex flex-col items-center gap-1"><div class="w-10 h-10 rounded-full bg-gradient-to-br from-[#00d2ff] to-[#0061ff] flex items-center justify-center text-slate-950 font-black text-sm">A</div><span class="text-sm font-semibold">Đinh Quốc Anh</span></div>
    <div class="flex flex-col items-center gap-1"><div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-[#0061ff] flex items-center justify-center text-white font-black text-sm">H</div><span class="text-sm font-semibold">Lý Gia Hân</span></div>
    <div class="flex flex-col items-center gap-1"><div class="w-10 h-10 rounded-full bg-gradient-to-br from-green-400 to-[#00d2ff] flex items-center justify-center text-slate-950 font-black text-sm">T</div><span class="text-sm font-semibold">Đỗ Thanh Thành Tài</span></div>
  </div>
  <div class="gc inline-flex px-6 py-2 text-sm">GVHD: <strong class="text-white ml-1">ThS. Đinh Công Đoan</strong> · Nhóm 02 · HK1 2025-2026</div>
</div>
<style>@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}</style>`

];

// ===== INJECT SLIDES INTO DOM =====
(function() {
  const container = document.getElementById('slidesContainer');
  if (!container) return;
  SLIDES.forEach((html, i) => {
    const section = document.createElement('section');
    section.className = 'slide-panel flex-col gap-8' + (i === 0 ? ' active' : '');
    section.id = 'slide-' + (i + 1);
    section.innerHTML = html;
    container.appendChild(section);
  });
})();
