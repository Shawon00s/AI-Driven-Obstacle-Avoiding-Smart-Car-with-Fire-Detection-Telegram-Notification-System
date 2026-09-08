import os

from ultralytics import YOLO
import cv2, serial, requests, time, threading, queue
import numpy as np
from flask import Flask, Response, render_template_string

# ============================================================
#   CONFIG
# ============================================================
BOT_TOKEN         = os.getenv("BOT_TOKEN", "")
CHAT_ID           = os.getenv("CHAT_ID", "")
TELEGRAM_COOLDOWN = 15
STREAM_URL        = os.getenv("STREAM_URL", "")
SERIAL_PORT       = os.getenv("SERIAL_PORT", "COM5")

# ============================================================
#   SHARED STATE
# ============================================================
raw_frame    = None
output_frame = None
status_text  = "Starting..."
raw_lock     = threading.Lock()
out_lock     = threading.Lock()
stop_flag    = threading.Event()
tg_queue     = queue.Queue(maxsize=1)

last_uart_cmd      = ""
last_telegram_time = 0
last_fire_time     = 0
FIRE_TIMEOUT       = 1.5

# ============================================================
#   INIT
# ============================================================
model = YOLO("fire.pt")

try:
    ser = serial.Serial(SERIAL_PORT, 115200, timeout=1)
    print("[UART] OK — Port:", SERIAL_PORT)
except Exception as e:
    ser = None
    print("[UART] Not found:", e)

# ============================================================
#   UART SEND HELPER
# ============================================================
def uart_send(cmd):
    global last_uart_cmd
    if cmd != last_uart_cmd:
        if ser:
            try:
                ser.write((cmd + "\n").encode())
                print(f"[UART] Sent: {cmd}")
            except Exception as ex:
                print(f"[UART] Error: {ex}")
        else:
            print(f"[UART] No serial — would send: {cmd}")
        last_uart_cmd = cmd

# ============================================================
#   THREAD 1 — MJPEG READER
# ============================================================
def mjpeg_reader():
    global raw_frame, status_text
    while not stop_flag.is_set():
        try:
            status_text = "Connecting to camera..."
            resp = requests.get(
                STREAM_URL, stream=True, timeout=10,
                headers={"Connection": "keep-alive"}
            )
            status_text = "Camera connected"
            buf = bytes()

            for chunk in resp.iter_content(chunk_size=8192):
                if stop_flag.is_set():
                    return
                buf += chunk

                if len(buf) > 200000:
                    s = buf.rfind(b'\xff\xd8')
                    buf = buf[s:] if s != -1 else bytes()
                    continue

                while True:
                    s = buf.find(b'\xff\xd8')
                    e = buf.find(b'\xff\xd9')
                    if s == -1 or e == -1 or e <= s:
                        break
                    jpg = buf[s:e+2]
                    buf = buf[e+2:]
                    frame = cv2.imdecode(
                        np.frombuffer(jpg, dtype=np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    if frame is not None and frame.size > 0:
                        with raw_lock:
                            raw_frame = cv2.resize(frame, (640, 480))

        except Exception as ex:
            status_text = "Stream error — retrying..."
            print(f"[Stream] {ex}")
            buf = bytes()
            time.sleep(2)

# ============================================================
#   THREAD 2 — YOLO WORKER
# ============================================================
def yolo_worker():
    global output_frame, last_telegram_time, status_text, last_fire_time

    while not stop_flag.is_set():
        with raw_lock:
            if raw_frame is None:
                time.sleep(0.01)
                continue
            frame = raw_frame.copy()

        # YOLO inference
        results = model(frame, conf=0.5, verbose=False)

        command = "NO_FIRE"
        fire    = False

        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf > 0.5:
                    fire = True
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cx = (x1 + x2) // 2
                    w  = frame.shape[1]

                    if   cx < w // 3:    command = "FIRE_LEFT"
                    elif cx > 2 * w // 3: command = "FIRE_RIGHT"
                    else:                command = "FIRE_CENTER"

                    # Draw the detection box.
                    cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,255), 2)
                    cv2.putText(frame, f"FIRE {conf:.2f}",
                                (x1, y1-8),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (0,0,255), 2)

        now = time.time()

        # Update the last-fire timestamp when fire is detected.
        if fire:
            last_fire_time = now

        # Hold the last command briefly after detection times out.
        if not fire and (now - last_fire_time) < FIRE_TIMEOUT:
            command = "FIRE_CENTER"
            fire    = True

        # Add the status label to the frame.
        color = (0, 0, 255) if fire else (0, 255, 0)
        cv2.putText(frame, command, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        status_text = f"🔥 {command}" if fire else "✅ NO_FIRE"

        # Update the output frame.
        with out_lock:
            output_frame = frame.copy()

        # Send the command over UART.
        uart_send(command)

        # Telegram
        if fire and (now - last_telegram_time) >= TELEGRAM_COOLDOWN:
            if not tg_queue.full():
                tg_queue.put((frame.copy(),
                              f"🔥 Fire! Direction: {command}"))
                last_telegram_time = now

# ============================================================
#   THREAD 3 — TELEGRAM
# ============================================================
def telegram_worker():
    while True:
        item = tg_queue.get()
        if item is None:
            break
        fc, caption = item
        try:
            _, enc = cv2.imencode(".jpg", fc)
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": caption},
                files={"photo": ("fire.jpg", enc.tobytes(), "image/jpeg")},
                timeout=15
            )
            print("[TG] OK!" if r.json().get("ok") else
                  f"[TG] Err: {r.text[:100]}")
        except Exception as ex:
            print(f"[TG] {ex}")
        finally:
            tg_queue.task_done()

# ============================================================
#   FLASK
# ============================================================
app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fire Detection</title>
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { background:#111; color:#fff;
           font-family:sans-serif; text-align:center; padding:20px; }
    h1   { color:#FF5722; margin-bottom:16px; font-size:24px; }
    img  { max-width:100%; border:2px solid #333;
           border-radius:8px; display:block; margin:0 auto; }
    #status { margin-top:14px; font-size:20px;
              padding:10px 20px; border-radius:6px;
              display:inline-block; background:#222; }
    .fire { background:#7f1010; color:#FF5722; }
    .ok   { background:#0a2f0a; color:#4CAF50; }
  </style>
  <script>
    setInterval(function(){
      fetch('/status').then(r=>r.text()).then(t=>{
        var el = document.getElementById('status');
        el.innerText = t;
        el.className = t.includes('FIRE') ? 'fire' : 'ok';
      });
    }, 1000);
  </script>
</head>
<body>
  <h1>🔥 Fire Detection Live</h1>
  <img src="/video" alt="Live stream">
  <div id="status" class="ok">Starting...</div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/status')
def status():
    return status_text

def gen_frames():
    while True:
        with out_lock:
            frame = output_frame.copy() if output_frame is not None else None
        if frame is None:
            time.sleep(0.05)
            continue
        _, jpeg = cv2.imencode('.jpg', frame,
                               [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               jpeg.tobytes() + b'\r\n')
        time.sleep(0.04)

@app.route('/video')
def video():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ============================================================
#   START
# ============================================================
if __name__ == "__main__":
    threading.Thread(target=mjpeg_reader,    daemon=True).start()
    threading.Thread(target=yolo_worker,     daemon=True).start()
    threading.Thread(target=telegram_worker, daemon=True).start()

    print("\n" + "="*45)
    print("  Browser: http://localhost:5000")
    print("  Serial: ", SERIAL_PORT)
    print("="*45 + "\n")

    app.run(host='0.0.0.0', port=5000,
            debug=False, threaded=True, use_reloader=False)

    stop_flag.set()
    tg_queue.put(None)
    if ser:
        ser.close()