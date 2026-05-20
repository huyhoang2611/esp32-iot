from flask import Flask, request

app = Flask(__name__)

# ===== BIẾN HỆ THỐNG =====
current_mode = 0
current_power = 0
current_speed = 500
current_brightness = 150

# ===== WEB GIAO DIỆN =====
@app.route("/")
def home():

    return f"""
    <h1>ESP32 LED CONTROL</h1>

    <h2>Power: {current_power}</h2>
    <h2>Mode: {current_mode}</h2>

    <br>

    <a href="/set?power=1"><button>ON</button></a>
    <a href="/set?power=0"><button>OFF</button></a>

    <br><br>

    <a href="/set?mode=0"><button>MODE 0</button></a>
    <a href="/set?mode=1"><button>MODE 1</button></a>
    <a href="/set?mode=2"><button>MODE 2</button></a>
    <a href="/set?mode=3"><button>MODE 3</button></a>
    <a href="/set?mode=4"><button>MODE 4</button></a>

    <br><br>

    <a href="/set?speed=100"><button>FAST</button></a>
    <a href="/set?speed=1000"><button>SLOW</button></a>

    <br><br>

    <a href="/set?brightness=60"><button>LOW</button></a>
    <a href="/set?brightness=255"><button>HIGH</button></a>
    """

# ===== NHẬN LỆNH TỪ WEB =====
@app.route("/set")
def set_data():

    global current_mode
    global current_power
    global current_speed
    global current_brightness

    if "mode" in request.args:
        current_mode = int(request.args["mode"])

    if "power" in request.args:
        current_power = int(request.args["power"])

    if "speed" in request.args:
        current_speed = int(request.args["speed"])

    if "brightness" in request.args:
        current_brightness = int(request.args["brightness"])

    return """
    <h1>UPDATED</h1>
    <a href="/">BACK</a>
    """

# ===== ESP32 ĐỌC DỮ LIỆU =====
@app.route("/getData")
def get_data():

    return f"{current_power},{current_mode},{current_speed},{current_brightness}"

# ===== CHẠY SERVER =====
app.run(host="0.0.0.0", port=5000)