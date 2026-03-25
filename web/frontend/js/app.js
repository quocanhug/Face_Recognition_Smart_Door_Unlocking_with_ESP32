/**
 * =============================================================
 *  SMART ATTENDANCE - Dashboard App (WebSocket + REST)
 * =============================================================
 */

// ==============================
// STATE
// ==============================
let ws = null;
let wsConnected = false;
let users = [];
let todayLogs = [];
let currentPage = 'dashboard';
let roomLocked = false;

const API = '';  // Same origin

// ==============================
// INIT
// ==============================
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    fetchStatus();
    fetchUsers();
    fetchTodayLogs();
    startClock();

    // Auto-refresh
    setInterval(fetchStatus, 5000);
    setInterval(fetchTodayLogs, 30000);
});

// ==============================
// LIVE CLOCK
// ==============================
function startClock() {
    updateClock();
    setInterval(updateClock, 1000);
}

function updateClock() {
    const now = new Date();
    const time = now.toLocaleTimeString('vi-VN', { hour12: false });
    const date = now.toLocaleDateString('vi-VN', {
        weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric'
    });
    setText('liveClock', time);
    setText('liveDate', date);
}

// ==============================
// PAGE NAVIGATION
// ==============================
function switchPage(page) {
    currentPage = page;
    // Hide all pages
    document.querySelectorAll('.page-content').forEach(el => el.style.display = 'none');
    // Deactivate tabs
    document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

    if (page === 'dashboard') {
        document.getElementById('pageDashboard').style.display = 'grid';
        document.getElementById('tabDashboard').classList.add('active');
    } else if (page === 'history') {
        document.getElementById('pageHistory').style.display = 'block';
        document.getElementById('tabHistory').classList.add('active');
        fetchHistory();
    }
}

// ==============================
// WEBSOCKET
// ==============================
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        wsConnected = true;
        updateWSIndicator(true);
        console.log('[WS] Connected');

        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleWSEvent(msg.event, msg.data);
        } catch (e) {
            console.error('[WS] Parse error:', e);
        }
    };

    ws.onclose = () => {
        wsConnected = false;
        updateWSIndicator(false);
        console.log('[WS] Disconnected, reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
        wsConnected = false;
        updateWSIndicator(false);
    };
}

function handleWSEvent(event, data) {
    switch (event) {
        case 'attendance':
            onAttendanceEvent(data);
            break;
        case 'security_alert':
            onSecurityAlert(data);
            break;
        case 'room_lock':
            onRoomLockEvent(data);
            break;
        case 'room_lock_denied':
            onRoomLockDenied(data);
            break;
        case 'pong':
            break;
        default:
            console.log('[WS] Unknown event:', event, data);
    }
}

function updateWSIndicator(connected) {
    const el = document.getElementById('wsIndicator');
    if (el) {
        el.className = connected ? 'ws-indicator connected' : 'ws-indicator';
    }
}

// ==============================
// EVENT HANDLERS
// ==============================
function onAttendanceEvent(data) {
    // Add to log list
    const logList = document.getElementById('logList');
    const item = createLogItem(data);
    logList.insertBefore(item, logList.firstChild);

    while (logList.children.length > 20) {
        logList.removeChild(logList.lastChild);
    }

    const empty = logList.querySelector('.log-empty');
    if (empty) empty.remove();

    if (data.status === 'GRANTED') {
        showToast(`✅ ${data.user_name} (${data.mssv})`, 'success');
    }

    fetchStatus();
}

function onSecurityAlert(data) {
    const alertEl = document.getElementById('securityAlert');
    if (alertEl) {
        alertEl.classList.add('active');
        alertEl.innerHTML = `
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                <span style="font-size:18px">🚨</span>
                <strong>CẢNH BÁO AN NINH</strong>
            </div>
            <div style="font-size:13px;color:var(--text-secondary)">
                Mode: ${data.mode} | Deny: ${data.deny_count}x
                ${data.alarm_active ? ' | 🔔 ALARM!' : ''}
            </div>
        `;
    }

    showToast(`🚨 Access Deny #${data.deny_count} (${data.mode})`, 'error');

    if (!data.alarm_active) {
        setTimeout(() => {
            if (alertEl) alertEl.classList.remove('active');
        }, 10000);
    }
}

function onRoomLockEvent(data) {
    roomLocked = data.locked;
    updateLockUI();
    if (data.locked) {
        showToast('🔒 Phòng đã khóa - Người quen sẽ được yêu cầu quay lại', 'warning');
    } else {
        showToast('🔓 Phòng đã mở khóa', 'success');
    }
}

function onRoomLockDenied(data) {
    showToast(`🔒 ${data.user_name} (${data.mssv}) - Phòng đang khóa!`, 'error');
}

// ==============================
// API CALLS
// ==============================
async function fetchStatus() {
    try {
        const resp = await fetch(`${API}/api/status`);
        const data = await resp.json();

        setText('statUsers', data.users_count);
        setText('statToday', data.today_attendance);
        setText('statMode', data.security_mode);
        setText('statUptime', formatUptime(data.uptime_seconds));

        const dot = document.getElementById('esp32Dot');
        if (dot) {
            dot.className = `status-dot ${data.esp32_connected ? 'online' : 'offline'}`;
        }
        setText('esp32Status', data.esp32_connected
            ? `ESP32: ${data.esp32_ip}` : 'ESP32: Offline');

        const modeDot = document.getElementById('modeDot');
        if (modeDot) {
            modeDot.className = `status-dot ${data.security_mode === 'NIGHT' ? 'night' : 'online'}`;
        }
        setText('modeStatus', data.security_mode === 'NIGHT' ? '🌙 Night' : '☀️ Day');

        // Sync room lock state
        roomLocked = data.room_locked || false;
        updateLockUI();

    } catch (e) {
        console.error('[API] Status error:', e);
    }
}

async function fetchUsers() {
    try {
        const resp = await fetch(`${API}/api/users`);
        const data = await resp.json();
        users = data.users;
        renderUserList(users);
    } catch (e) {
        console.error('[API] Users error:', e);
    }
}

async function fetchTodayLogs() {
    try {
        const resp = await fetch(`${API}/api/attendance/today`);
        const data = await resp.json();
        todayLogs = data.logs;
        renderLogList(todayLogs);
    } catch (e) {
        console.error('[API] Logs error:', e);
    }
}

async function fetchHistory() {
    const days = document.getElementById('historyDays').value;
    try {
        const resp = await fetch(`${API}/api/attendance/history?days=${days}`);
        const data = await resp.json();
        renderHistoryTable(data.logs, data.total);
    } catch (e) {
        console.error('[API] History error:', e);
    }
}

async function createUser(name, mssv) {
    try {
        const resp = await fetch(`${API}/api/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, mssv })
        });
        if (!resp.ok) {
            const err = await resp.json();
            showToast(`❌ ${err.detail}`, 'error');
            return;
        }
        showToast(`✅ Đã thêm ${name}`, 'success');
        fetchUsers();
    } catch (e) {
        showToast('❌ Lỗi kết nối', 'error');
    }
}

async function deleteUser(userId, name) {
    if (!confirm(`Xóa ${name}?`)) return;
    try {
        await fetch(`${API}/api/users/${userId}`, { method: 'DELETE' });
        showToast(`Đã xóa ${name}`, 'warning');
        fetchUsers();
        fetchStatus();
    } catch (e) {
        showToast('❌ Lỗi', 'error');
    }
}

async function enrollUser(userId, name) {
    showToast(`📸 Đang chụp ảnh cho ${name}...`, 'warning');
    try {
        const resp = await fetch(`${API}/api/users/${userId}/enroll`, {
            method: 'POST'
        });
        const data = await resp.json();
        if (resp.ok) {
            showToast(`✅ Enroll thành công: ${name} (${data.face_count} faces)`, 'success');
            fetchUsers();
        } else {
            showToast(`❌ ${data.detail}`, 'error');
        }
    } catch (e) {
        showToast('❌ Lỗi kết nối', 'error');
    }
}

// ==============================
// RENDER
// ==============================
function renderLogList(logs) {
    const el = document.getElementById('logList');
    if (!logs.length) {
        el.innerHTML = '<div class="log-empty">📋 Chưa có điểm danh hôm nay</div>';
        return;
    }

    el.innerHTML = logs.map(log => {
        const isGranted = log.status === 'GRANTED';
        const initial = log.user_name ? log.user_name[0].toUpperCase() : '?';
        const name = log.user_name || 'Unknown';
        const detail = log.mssv || 'Access Denied';
        const time = new Date(log.timestamp).toLocaleTimeString('vi-VN');
        const conf = log.confidence ? `${(log.confidence * 100).toFixed(0)}%` : '';

        return `
            <div class="log-item">
                <div class="log-avatar ${isGranted ? 'granted' : 'denied'}">${initial}</div>
                <div class="log-info">
                    <div class="log-name">${name}</div>
                    <div class="log-detail">${detail} ${conf ? `• ${conf}` : ''}</div>
                </div>
                <div class="log-time">${time}</div>
            </div>
        `;
    }).join('');
}

function renderUserList(users) {
    const el = document.getElementById('userList');
    if (!users.length) {
        el.innerHTML = '<div class="log-empty">Chưa có user nào</div>';
        return;
    }

    el.innerHTML = users.map(u => `
        <div class="user-item">
            <div class="user-info-block">
                <div class="user-avatar">${u.name[0].toUpperCase()}</div>
                <div>
                    <div class="user-name">${u.name}</div>
                    <div class="user-mssv">${u.mssv} • ${u.face_count} faces</div>
                </div>
            </div>
            <div class="user-actions">
                <button class="btn btn-sm btn-ghost" onclick="editUser(${u.id}, '${u.name.replace(/'/g, "\\'") }', '${u.mssv}')" title="Sửa thông tin">✏️</button>
                <button class="btn btn-sm btn-success" onclick="enrollUser(${u.id}, '${u.name}')" title="Enroll face">📸</button>
                <button class="btn btn-sm btn-danger" onclick="deleteUser(${u.id}, '${u.name}')" title="Delete">🗑️</button>
            </div>
        </div>
    `).join('');
}

function renderHistoryTable(logs, total) {
    const tbody = document.getElementById('historyBody');
    const summary = document.getElementById('historySummary');
    const footer = document.getElementById('historyFooter');

    // Summary stats
    const granted = logs.filter(l => l.status === 'GRANTED').length;
    const denied = logs.filter(l => l.status === 'DENIED').length;
    const uniqueUsers = new Set(logs.filter(l => l.mssv).map(l => l.mssv)).size;

    summary.innerHTML = `
        <div class="summary-item">
            <div class="summary-value">${granted}</div>
            <div class="summary-label">✅ Đã điểm danh</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">${denied}</div>
            <div class="summary-label">❌ Access Denied</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">${uniqueUsers}</div>
            <div class="summary-label">👤 Users điểm danh</div>
        </div>
    `;

    if (!logs.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="log-empty">Không có dữ liệu</td></tr>';
        footer.textContent = '';
        return;
    }

    tbody.innerHTML = logs.map((log, i) => {
        const isGranted = log.status === 'GRANTED';
        const dt = new Date(log.timestamp);
        const timeStr = dt.toLocaleString('vi-VN', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        const conf = log.confidence ? `${(log.confidence * 100).toFixed(1)}%` : '-';

        return `
            <tr>
                <td>${i + 1}</td>
                <td>${timeStr}</td>
                <td>${log.user_name || '<em style="color:var(--text-muted)">Unknown</em>'}</td>
                <td>${log.mssv || '-'}</td>
                <td><span class="badge ${isGranted ? 'badge-granted' : 'badge-denied'}">${log.status}</span></td>
                <td>${conf}</td>
            </tr>
        `;
    }).join('');

    footer.textContent = `Hiển thị ${logs.length} / ${total} bản ghi`;
}

function createLogItem(data) {
    const div = document.createElement('div');
    div.className = 'log-item';
    const isGranted = data.status === 'GRANTED';
    const initial = data.user_name ? data.user_name[0].toUpperCase() : '?';
    const name = data.user_name || 'Unknown';
    const detail = data.mssv || 'Access Denied';
    const time = new Date(data.timestamp).toLocaleTimeString('vi-VN');
    const conf = data.confidence ? `${data.confidence.toFixed(0)}%` : '';

    div.innerHTML = `
        <div class="log-avatar ${isGranted ? 'granted' : 'denied'}">${initial}</div>
        <div class="log-info">
            <div class="log-name">${name}</div>
            <div class="log-detail">${detail} ${conf ? `• ${conf}` : ''}</div>
        </div>
        <div class="log-time">${time}</div>
    `;
    return div;
}

// ==============================
// UI HELPERS
// ==============================
function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ==============================
// MODAL: Add User
// ==============================
let editingUserId = null;

function showAddUser() {
    editingUserId = null;
    document.getElementById('modalTitle').textContent = '➕ Thêm Người Dùng';
    document.getElementById('modalSubmitBtn').textContent = 'Thêm';
    document.getElementById('modalOverlay').classList.add('active');
    document.getElementById('inputName').value = '';
    document.getElementById('inputMssv').value = '';
    document.getElementById('inputName').focus();
}

function editUser(id, name, mssv) {
    editingUserId = id;
    document.getElementById('modalTitle').textContent = '✏️ Sửa Thông Tin';
    document.getElementById('modalSubmitBtn').textContent = 'Lưu';
    document.getElementById('modalOverlay').classList.add('active');
    document.getElementById('inputName').value = name;
    document.getElementById('inputMssv').value = mssv;
    document.getElementById('inputName').focus();
}

function hideModal() {
    document.getElementById('modalOverlay').classList.remove('active');
    editingUserId = null;
}

async function submitAddUser() {
    const name = document.getElementById('inputName').value.trim();
    const mssv = document.getElementById('inputMssv').value.trim();
    if (!name || !mssv) {
        showToast('Vui lòng nhập đầy đủ!', 'error');
        return;
    }

    const userId = editingUserId; // Save before hideModal resets it
    hideModal();

    if (userId) {
        // Edit existing user
        try {
            const res = await fetch(`/api/users/${userId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, mssv })
            });
            const data = await res.json();
            if (res.ok) {
                showToast(`Đã cập nhật: ${name}`);
                fetchUsers();
            } else {
                showToast(data.detail || 'Lỗi cập nhật', 'error');
            }
        } catch (e) {
            showToast('Lỗi kết nối', 'error');
        }
    } else {
        // Create new user
        createUser(name, mssv);
    }
}

// ==============================
// ROOM LOCK
// ==============================
async function toggleRoomLock() {
    const endpoint = roomLocked ? '/api/security/unlock' : '/api/security/lock';
    try {
        const resp = await fetch(`${API}${endpoint}`, { method: 'POST' });
        const data = await resp.json();
        roomLocked = data.locked;
        updateLockUI();
    } catch (e) {
        showToast('❌ Lỗi kết nối', 'error');
    }
}

function updateLockUI() {
    const lockIcon = document.getElementById('lockIcon');
    const lockStatus = document.getElementById('lockStatus');
    const lockToggle = document.getElementById('lockToggle');
    const banner = document.getElementById('roomLockBanner');

    if (lockIcon) lockIcon.textContent = roomLocked ? '🔒' : '🔓';
    if (lockStatus) lockStatus.textContent = roomLocked ? 'Khóa' : 'Mở khóa';
    if (lockToggle) {
        lockToggle.className = roomLocked
            ? 'status-badge lock-toggle locked' : 'status-badge lock-toggle';
    }
    if (banner) {
        banner.style.display = roomLocked ? 'flex' : 'none';
    }
}
