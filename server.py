# app.py - ESP32 LED Control Server
# Architecture: REST API + JSON + CORS
# Deploy: Render.com (Gunicorn)

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)  # Cho phép AJAX từ browser

# ==========================================
# STATE MACHINE - Trạng thái hệ thống
# ==========================================
# Đây là "single source of truth" - mọi thứ
# đều đọc/ghi vào dict này
state = {
    "power": 0,
    "mode": 0,
    "speed": 500,
    "brightness": 150,
    "last_seen": 0,    # Timestamp ESP32 poll gần nhất
    "online": False    # ESP32 có đang online không
}

EFFECT_NAMES = {
    0: "Alternate",
    1: "Running",
    2: "All Blink",
    3: "Cross",
    4: "Stack"
}

# ==========================================
# API ENDPOINTS
# ==========================================

@app.route('/api/status', methods=['GET'])
def get_status():
    """
    ESP32 và Dashboard đều gọi endpoint này.
    Trả về JSON đầy đủ thay vì CSV.
    """
    # Check ESP32 online/offline (timeout 5 giây)
    state["online"] = (time.time() - state["last_seen"]) < 5
    
    return jsonify({
        "power": state["power"],
        "mode": state["mode"],
        "mode_name": EFFECT_NAMES.get(state["mode"], "Unknown"),
        "speed": state["speed"],
        "brightness": state["brightness"],
        "online": state["online"]
    })

@app.route('/api/control', methods=['POST'])
def control():
    """
    Dashboard gửi lệnh điều khiển lên đây.
    Body: JSON {"power": 1} hoặc {"mode": 2} v.v.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400
    
    # Validate và update từng field
    if "power" in data:
        state["power"] = int(data["power"]) & 1  # Chỉ 0 hoặc 1
    if "mode" in data:
        state["mode"] = max(0, min(4, int(data["mode"])))
    if "speed" in data:
        state["speed"] = max(100, min(2000, int(data["speed"])))
    if "brightness" in data:
        state["brightness"] = max(10, min(255, int(data["brightness"])))
    
    return jsonify({"ok": True, "state": state})

@app.route('/api/heartbeat', methods=['GET'])
def heartbeat():
    """
    ESP32 gọi endpoint này mỗi 1 giây để báo "tôi đang sống".
    Đồng thời nhận lệnh mới về.
    """
    state["last_seen"] = time.time()
    state["online"] = True
    
    return jsonify({
        "power": state["power"],
        "mode": state["mode"],
        "speed": state["speed"],
        "brightness": state["brightness"]
    })

# ==========================================
# BACKWARD COMPATIBILITY
# ESP32 cũ vẫn dùng /getData được
# ==========================================
@app.route('/getData', methods=['GET'])
def get_data_legacy():
    state["last_seen"] = time.time()
    return f"{state['power']},{state['mode']},{state['speed']},{state['brightness']}"

@app.route('/set', methods=['GET'])
def set_legacy():
    for key in ['power', 'mode', 'speed', 'brightness']:
        if key in request.args:
            state[key] = int(request.args[key])
    return "OK"

# Dashboard HTML (xem phần 2)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ESP32 LED Control</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Outfit:wght@300;400;500;600&display=swap');

  /* ======= CSS VARIABLES - Design System ======= */
  :root {
    --bg:      #0d1117;
    --bg2:     #161b22;
    --bg3:     #21262d;
    --border:  rgba(48,54,61,0.9);
    --accent:  #00d4ff;     /* cyan - trạng thái active */
    --accent2: #ff6b35;     /* orange - cảnh báo */
    --green:   #39d353;     /* online / success */
    --muted:   #8b949e;     /* text phụ */
    --text:    #e6edf3;     /* text chính */
    --mono:    'Share Tech Mono', monospace;
    --sans:    'Outfit', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--sans); min-height: 100vh; }

  /* ======= LAYOUT ======= */
  .container { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
  
  /* ======= TOPBAR ======= */
  .topbar {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .logo { font-family: var(--mono); font-size: 13px; color: var(--accent); letter-spacing: 2px; }
  .status-pill {
    display: flex; align-items: center; gap: 8px;
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: 20px; padding: 6px 14px;
    font-size: 12px; font-family: var(--mono);
    cursor: pointer; transition: border-color .2s;
  }
  .status-pill:hover { border-color: var(--accent); }
  .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    animation: pulse 2s infinite;
  }
  .dot.offline { background: #555; box-shadow: none; animation: none; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* ======= CARDS ======= */
  .card {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: 14px; padding: 20px;
    transition: border-color .2s;
  }
  .card:hover { border-color: rgba(0,212,255,.2); }
  .card-label {
    font-size: 10px; color: var(--muted);
    letter-spacing: 2px; text-transform: uppercase;
    font-family: var(--mono); margin-bottom: 14px;
  }

  /* ======= GRID ======= */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
  @media (max-width: 600px) {
    .grid-2, .grid-3 { grid-template-columns: 1fr; }
  }

  /* ======= POWER BUTTONS ======= */
  .power-row { display: flex; gap: 10px; }
  .pwr-btn {
    flex: 1; padding: 12px; border-radius: 10px;
    border: 1px solid var(--border); background: var(--bg3);
    font-family: var(--mono); font-size: 14px; color: var(--muted);
    cursor: pointer; letter-spacing: 2px; transition: all .15s;
  }
  .pwr-btn:hover { border-color: var(--accent); color: var(--accent); }
  .pwr-btn.on.active {
    background: rgba(0,212,255,.1); border-color: var(--accent);
    color: var(--accent); box-shadow: 0 0 16px rgba(0,212,255,.15);
  }
  .pwr-btn.off.active {
    background: rgba(255,107,53,.1); border-color: var(--accent2);
    color: var(--accent2); box-shadow: 0 0 16px rgba(255,107,53,.15);
  }

  /* ======= LED DISPLAY ======= */
  .led-row { display: flex; gap: 12px; justify-content: center; margin: 16px 0 10px; }
  .led-wrap { display: flex; flex-direction: column; align-items: center; gap: 6px; }
  .led {
    width: 28px; height: 28px; border-radius: 50%;
    background: #1a1a1a; border: 2px solid #2a2a2a;
    transition: all .2s;
  }
  .led.on {
    background: var(--accent);
    border-color: var(--accent);
    box-shadow: 0 0 16px var(--accent), 0 0 4px #fff;
  }
  .led-label { font-family: var(--mono); font-size: 9px; color: var(--muted); }
  .effect-tag {
    display: inline-block; margin-top: 8px;
    background: rgba(57,211,83,.08); border: 1px solid rgba(57,211,83,.3);
    color: var(--green); border-radius: 20px; padding: 4px 14px;
    font-size: 11px; font-family: var(--mono); letter-spacing: 1px;
  }

  /* ======= MODE BUTTONS ======= */
  .mode-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .mode-btn {
    background: var(--bg3); border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 8px; text-align: center; cursor: pointer;
    transition: all .15s; color: var(--muted); font-size: 12px;
  }
  .mode-btn:hover { border-color: var(--accent); color: var(--text); }
  .mode-btn.active {
    background: rgba(57,211,83,.08); border-color: var(--green); color: var(--green);
  }
  .mode-btn .icon { font-size: 18px; display: block; margin-bottom: 4px; }
  .mode-btn.wide { grid-column: 1 / -1; }

  /* ======= SLIDERS ======= */
  .slider-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  input[type=range] {
    flex: 1; -webkit-appearance: none; height: 4px;
    background: var(--bg3); border-radius: 4px; outline: none;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 16px; height: 16px;
    border-radius: 50%; background: var(--accent);
    cursor: pointer; box-shadow: 0 0 8px rgba(0,212,255,.6);
    transition: transform .15s;
  }
  input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.2); }
  .slider-meta { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 11px; color: var(--muted); }
  .slider-val { font-family: var(--mono); font-size: 14px; color: var(--accent); font-weight: bold; }

  /* ======= API STATUS BAR ======= */
  .api-bar {
    background: var(--bg2); border: 1px solid var(--border); border-radius: 12px;
    padding: 14px 16px; margin-top: 16px; display: flex;
    align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
  }
  .api-tags { display: flex; gap: 8px; flex-wrap: wrap; }
  .tag {
    padding: 4px 10px; border-radius: 6px; font-family: var(--mono); font-size: 11px;
    border: 1px solid transparent;
  }
  .tag.get { color: var(--green); border-color: rgba(57,211,83,.3); background: rgba(57,211,83,.05); }
  .tag.post { color: #e3b341; border-color: rgba(227,179,65,.3); background: rgba(227,179,65,.05); }
  .payload { font-family: var(--mono); font-size: 11px; color: var(--muted); }

  /* ======= NOTIFY TOAST ======= */
  #toast {
    position: fixed; bottom: 24px; right: 24px;
    background: var(--bg2); border: 1px solid var(--green); color: var(--green);
    padding: 10px 18px; border-radius: 10px; font-family: var(--mono); font-size: 12px;
    opacity: 0; transition: opacity .3s; pointer-events: none; z-index: 999;
  }
  #toast.show { opacity: 1; }
</style>
</head>
<body>
<div class="container">
  <!-- TOPBAR -->
  <div class="topbar">
    <div class="logo">ESP32 · LED CONTROL · v2</div>
    <div style="display:flex;gap:10px;align-items:center;">
      <span style="font-family:var(--mono);font-size:11px;color:var(--muted)" id="clock">--:--:--</span>
      <div class="status-pill" onclick="fetchStatus()">
        <div class="dot" id="esp-dot"></div>
        <span id="esp-label">ESP32: --</span>
      </div>
    </div>
  </div>

  <!-- ROW 1: Power + Mode -->
  <div class="grid-2">
    <!-- POWER CARD -->
    <div class="card">
      <div class="card-label">⚡ Power Control</div>
      <div class="power-row">
        <button class="pwr-btn on" id="btn-on" onclick="sendControl({power:1})">ON</button>
        <button class="pwr-btn off" id="btn-off" onclick="sendControl({power:0})">OFF</button>
      </div>
      <div style="text-align:center;">
        <div class="led-row">
          <div class="led-wrap"><div class="led" id="led0"></div><span class="led-label">D1</span></div>
          <div class="led-wrap"><div class="led" id="led1"></div><span class="led-label">D2</span></div>
          <div class="led-wrap"><div class="led" id="led2"></div><span class="led-label">D3</span></div>
          <div class="led-wrap"><div class="led" id="led3"></div><span class="led-label">D4</span></div>
        </div>
        <span class="effect-tag" id="effect-tag">--</span>
      </div>
    </div>

    <!-- MODE CARD -->
    <div class="card">
      <div class="card-label">🎨 Effect Mode</div>
      <div class="mode-grid">
        <div class="mode-btn" id="m0" onclick="sendControl({mode:0})"><span class="icon">⇄</span>Alternate</div>
        <div class="mode-btn" id="m1" onclick="sendControl({mode:1})"><span class="icon">▶</span>Run</div>
        <div class="mode-btn" id="m2" onclick="sendControl({mode:2})"><span class="icon">◉</span>All Blink</div>
        <div class="mode-btn" id="m3" onclick="sendControl({mode:3})"><span class="icon">✕</span>Cross</div>
        <div class="mode-btn wide" id="m4" onclick="sendControl({mode:4})"><span class="icon">▥</span>Stack</div>
      </div>
    </div>
  </div>

  <!-- ROW 2: Speed + Brightness + Info -->
  <div class="grid-3">
    <!-- SPEED -->
    <div class="card">
      <div class="card-label">⚡ Speed</div>
      <div class="slider-row">
        <input type="range" min="100" max="2000" step="50" id="sl-speed"
          oninput="document.getElementById('v-speed').textContent=this.value+'ms'"
          onchange="sendControl({speed:parseInt(this.value)})">
      </div>
      <div class="slider-meta">
        <span>FAST</span>
        <span class="slider-val" id="v-speed">500ms</span>
        <span>SLOW</span>
      </div>
    </div>

    <!-- BRIGHTNESS -->
    <div class="card">
      <div class="card-label">💡 Brightness</div>
      <div class="slider-row">
        <input type="range" min="10" max="255" step="5" id="sl-bright"
          oninput="document.getElementById('v-bright').textContent=this.value"
          onchange="sendControl({brightness:parseInt(this.value)})">
      </div>
      <div class="slider-meta">
        <span>DIM</span>
        <span class="slider-val" id="v-bright">150</span>
        <span>MAX</span>
      </div>
    </div>

    <!-- INFO -->
    <div class="card">
      <div class="card-label">📡 System</div>
      <div style="font-family:var(--mono);font-size:12px;color:var(--muted);line-height:2.1;">
        <div>Poll interval: <span style="color:var(--green)">1s</span></div>
        <div>Protocol: <span style="color:var(--accent)">HTTP/REST</span></div>
        <div>Data format: <span style="color:var(--accent)">JSON</span></div>
        <div>MCU: <span style="color:var(--accent2)">ESP32 240MHz</span></div>
        <div>LEDs: <span style="color:var(--accent2)">4 × PWM</span></div>
      </div>
    </div>
  </div>

  <!-- API STATUS BAR -->
  <div class="api-bar">
    <div class="api-tags">
      <span class="tag get">GET /api/status</span>
      <span class="tag post">POST /api/control</span>
      <span class="tag get">GET /api/heartbeat</span>
    </div>
    <div class="payload" id="payload">payload: --</div>
  </div>
</div>

<!-- TOAST NOTIFICATION -->
<div id="toast">✓ Command sent</div>

<script>
// =============================================
// STATE - Single source of truth ở client
// =============================================
let state = { power: 0, mode: 0, speed: 500, brightness: 150, online: false };
const EFFECTS = ['Alternate','Running','All Blink','Cross','Stack'];
const LED_PAT = {
  0: [[1,0,1,0],[0,1,0,1]],
  1: [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
  2: [[1,1,1,1],[0,0,0,0]],
  3: [[1,0,0,1],[0,1,1,0]],
  4: [[1,0,0,0],[1,1,0,0],[1,1,1,0],[1,1,1,1],[0,0,0,0]]
};
let ledFrame = 0, ledTimer = null;

// =============================================
// CLOCK
// =============================================
function updateClock() {
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('en-GB');
}
setInterval(updateClock, 1000);
updateClock();

// =============================================
// FETCH STATUS từ server (polling mỗi 2 giây)
// Đây là "long polling" pattern - client chủ động hỏi
// =============================================
async function fetchStatus() {
  try {
    // fetch() là Web API hiện đại, thay thế XMLHttpRequest
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();  // Parse JSON response
    state = { ...state, ...data };   // Merge vào state
    renderUI();
  } catch(e) {
    // Nếu lỗi → ESP32 offline
    state.online = false;
    document.getElementById('esp-dot').className = 'dot offline';
    document.getElementById('esp-label').textContent = 'ESP32: OFFLINE';
  }
}

// Polling mỗi 2 giây
setInterval(fetchStatus, 2000);
fetchStatus(); // Gọi ngay khi load

// =============================================
// SEND CONTROL - POST JSON đến server
// Sử dụng async/await pattern - non-blocking
// =============================================
async function sendControl(params) {
  try {
    const res = await fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)  // Serialize JS object → JSON string
    });
    const data = await res.json();
    if (data.ok) {
      state = { ...state, ...params };
      renderUI();
      showToast('✓ Sent: ' + JSON.stringify(params));
    }
  } catch(e) {
    showToast('✗ Connection error');
  }
}

// =============================================
// RENDER UI - Cập nhật DOM theo state
// Pattern: State → UI (one-way data flow)
// =============================================
function renderUI() {
  // Power buttons
  document.getElementById('btn-on').className  = 'pwr-btn on'  + (state.power ? ' active' : '');
  document.getElementById('btn-off').className = 'pwr-btn off' + (!state.power ? ' active' : '');

  // Mode buttons
  for (let i = 0; i < 5; i++) {
    document.getElementById('m' + i).className =
      'mode-btn' + (i === 4 ? ' wide' : '') + (state.mode === i ? ' active' : '');
  }

  // Effect label
  document.getElementById('effect-tag').textContent = EFFECTS[state.mode] || '--';

  // Sliders
  document.getElementById('sl-speed').value = state.speed;
  document.getElementById('v-speed').textContent = state.speed + 'ms';
  document.getElementById('sl-bright').value = state.brightness;
  document.getElementById('v-bright').textContent = state.brightness;

  // ESP32 online status
  const dot = document.getElementById('esp-dot');
  dot.className = 'dot' + (state.online ? '' : ' offline');
  document.getElementById('esp-label').textContent =
    'ESP32: ' + (state.online ? 'ONLINE' : 'OFFLINE');

  // Payload display
  document.getElementById('payload').textContent =
    'last: ' + JSON.stringify({power:state.power, mode:state.mode,
                               speed:state.speed, brightness:state.brightness});

  // Restart LED animation
  startLEDAnim();
}

// =============================================
// LED ANIMATION - Giả lập hiệu ứng trên browser
// Phản ánh trạng thái thực của ESP32
// =============================================
function startLEDAnim() {
  clearInterval(ledTimer);
  if (!state.power) {
    for (let i = 0; i < 4; i++) {
      document.getElementById('led'+i).className = 'led';
    }
    return;
  }
  const pats = LED_PAT[state.mode] || LED_PAT[0];
  ledTimer = setInterval(() => {
    const pat = pats[ledFrame % pats.length];
    pat.forEach((v, i) => {
      document.getElementById('led'+i).className = 'led' + (v ? ' on' : '');
    });
    ledFrame++;
  }, state.speed);
}

// =============================================
// TOAST NOTIFICATION
// =============================================
let toastTimer = null;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2000);
}

renderUI(); // Khởi tạo UI
</script>
</body>
</html>
"""
@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
