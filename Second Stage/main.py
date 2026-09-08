# ============================================================
#   FIRE-SEEKING CAR — Raspberry Pi Pico (MicroPython)
#   Stage 2 firmware — UART receiver for fire_detection.py
# ============================================================
#
#   ⚠️  UNTESTED — this file was reconstructed from the project
#   spec, not recovered from the original build. The original
#   main.py was never committed (0 bytes here and upstream).
#   Bench-test it on blocks with the wheels off the ground
#   before running it on the floor. See "First run" in README.
#
#   Host (fire_detection.py) sends one ASCII line per state
#   change at 115200 baud:
#       FIRE_LEFT / FIRE_CENTER / FIRE_RIGHT / NO_FIRE
#
#   FIRE_*   → approach the flame, halt at FIRE_STOP, buzz
#   NO_FIRE  → patrol using Stage 1 obstacle avoidance
# ============================================================
from machine import Pin, PWM, UART
import time

# ── Servo ────────────────────────────────────────────────────
#  NOTE: GP16 here, not GP0 as in Stage 1. Low pins are needed
#  for UART and the buzzer in this stage.
servo = PWM(Pin(16))
servo.freq(50)

# ── Ultrasonic ───────────────────────────────────────────────
Trig = Pin(2, Pin.OUT)
Echo = Pin(3, Pin.IN)

# ── Motor driver (L298N) ─────────────────────────────────────
ENA = PWM(Pin(4))
IN1 = Pin(5, Pin.OUT)
IN2 = Pin(6, Pin.OUT)
IN3 = Pin(7, Pin.OUT)
IN4 = Pin(8, Pin.OUT)
ENB = PWM(Pin(9))

ENA.freq(1000)
ENB.freq(1000)

# ── UART link to the host PC ─────────────────────────────────
uart = UART(0, baudrate=115200, tx=Pin(12), rx=Pin(13))

# ── Buzzer ───────────────────────────────────────────────────
#  Wired for a PASSIVE buzzer (needs a driven frequency), which
#  is what the parts list specifies. For an ACTIVE buzzer,
#  replace with `buzzer = Pin(15, Pin.OUT)` and swap the bodies
#  of buzzer_on() / buzzer_off() for value(1) / value(0).
buzzer = PWM(Pin(15))
buzzer.freq(2000)
buzzer.duty_u16(0)

# ============================================================
#   TUNING
# ============================================================
MAX_SPEED  = 30000   # patrol forward speed (PWM duty)
TURN_SPEED = 40000   # pivot speed — needs more torque than driving
SLOW_SPEED = 20000   # fire approach speed

#  If the car stalls or will not pivot, raise these. Stage 1
#  was tuned at MAX_SPEED 65535 / TURN_SPEED 50000 on the same
#  chassis, so there is plenty of headroom.

SAFE_DIST    = 35    # cm — obstacle avoidance trigger
FIRE_STOP    = 30    # cm — halt distance when approaching fire
SAMPLES      = 5     # readings averaged per measurement
FIRE_SAMPLES = 3     # fewer samples in fire mode = faster reaction
ECHO_TIMEOUT = 38000 # µs — covers the HC-SR04's full 400 cm range

TURN_PULSE_MS = 250  # length of one steering nudge in fire mode

#  If the host goes quiet for this long, assume the link died
#  and fall back to patrolling. Chosen above the host's 1.5 s
#  FIRE_TIMEOUT so normal state changes never trip it.
LINK_TIMEOUT_MS = 3000

VALID_COMMANDS = ("FIRE_LEFT", "FIRE_CENTER", "FIRE_RIGHT", "NO_FIRE")

# ============================================================
#   MOTOR CONTROL
# ============================================================

def _drive(speed, a, b, c, d):
    ENA.duty_u16(speed)
    IN1.value(a); IN2.value(b)
    ENB.duty_u16(speed)
    IN3.value(c); IN4.value(d)

def forward(speed=MAX_SPEED):
    _drive(speed, 0, 1, 1, 0)

def backward(speed=TURN_SPEED):
    _drive(speed, 1, 0, 0, 1)

def left(speed=TURN_SPEED):
    _drive(speed, 1, 0, 1, 0)

def right(speed=TURN_SPEED):
    _drive(speed, 0, 1, 0, 1)

def stop():
    ENA.duty_u16(0)
    IN1.value(0); IN2.value(0)
    ENB.duty_u16(0)
    IN3.value(0); IN4.value(0)

# ============================================================
#   BUZZER
# ============================================================

def buzzer_on():
    buzzer.duty_u16(32768)      # 50% duty square wave

def buzzer_off():
    buzzer.duty_u16(0)

# ============================================================
#   ULTRASONIC
#   Identical maths to Stage 1: 10 µs trigger, time the echo,
#   convert with the speed of sound. Returns 999 on timeout,
#   which means "nothing in range", i.e. open space.
# ============================================================

def _read_once():
    Trig.value(0)
    time.sleep_us(5)

    Trig.value(1)
    time.sleep_us(10)
    Trig.value(0)

    start = time.ticks_us()
    while Echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > ECHO_TIMEOUT:
            return 999

    pulse_start = time.ticks_us()

    while Echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), pulse_start) > ECHO_TIMEOUT:
            return 999

    duration = time.ticks_diff(time.ticks_us(), pulse_start)
    return round((duration * 0.0343) / 2, 1)

def distance(samples=SAMPLES):
    """Average several pings, discarding timeouts and outliers."""
    readings = []

    for _ in range(samples):
        d = _read_once()
        if d != 999:
            readings.append(d)
        time.sleep_ms(15)       # HC-SR04 needs ~15 ms between pings

    if not readings:
        return 999
    if len(readings) == 1:
        return readings[0]

    if len(readings) > 3:
        readings.remove(max(readings))
        readings.remove(min(readings))

    return round(sum(readings) / len(readings), 1)

# ============================================================
#   SERVO — SG90 at 50 Hz (20 ms period)
# ============================================================

def servoLeft():
    servo.duty_u16(8192)        # 180°
    time.sleep_ms(600)

def servoRight():
    servo.duty_u16(1638)        # 0°
    time.sleep_ms(600)

def servoCenter():
    servo.duty_u16(4915)        # 90°
    time.sleep_ms(600)

# ============================================================
#   UART COMMAND RECEIVER
#
#   The host only writes on change, so commands are rare. We
#   buffer bytes and act on the LAST complete line received —
#   if several arrived while we were busy, the newest one is
#   the only one still true.
# ============================================================
command    = "NO_FIRE"
last_rx_ms = time.ticks_ms()
_rx_buf    = b""

def poll_command():
    """Drain the UART and latch the newest valid command."""
    global command, last_rx_ms, _rx_buf

    if uart.any():
        chunk = uart.read()
        if chunk:
            _rx_buf += chunk

    if b"\n" not in _rx_buf:
        if len(_rx_buf) > 128:      # noise on the line — resync
            _rx_buf = b""
        return command

    parts   = _rx_buf.split(b"\n")
    _rx_buf = parts[-1]             # keep any trailing partial line

    for raw in parts[:-1]:
        try:
            token = raw.strip().decode().upper()
        except Exception:
            continue                # ignore undecodable noise
        if token in VALID_COMMANDS:
            command    = token
            last_rx_ms = time.ticks_ms()
            print("[UART]", token)

    return command

def link_lost():
    return time.ticks_diff(time.ticks_ms(), last_rx_ms) > LINK_TIMEOUT_MS

# ============================================================
#   FIRE MODE
#
#   The sonar stays pointed FORWARD so the halt distance stays
#   meaningful — steering comes from the host's direction, not
#   from panning the sensor. Each pass makes one small
#   correction, so the car converges as the host keeps
#   re-reporting where the flame is.
# ============================================================

def fire_mode(cmd):
    dist = distance(FIRE_SAMPLES)

    if dist <= FIRE_STOP:
        # Close enough — hold position and sound the alarm.
        stop()
        buzzer_on()
        print("FIRE at {} cm — holding".format(dist))
        return

    buzzer_off()

    if cmd == "FIRE_LEFT":
        left(TURN_SPEED)
        time.sleep_ms(TURN_PULSE_MS)
        forward(SLOW_SPEED)
    elif cmd == "FIRE_RIGHT":
        right(TURN_SPEED)
        time.sleep_ms(TURN_PULSE_MS)
        forward(SLOW_SPEED)
    else:                            # FIRE_CENTER
        forward(SLOW_SPEED)

    print("Approaching ({}) — {} cm".format(cmd, dist))

# ============================================================
#   OBSTACLE MODE — Stage 1 behaviour
#
#   The scan blocks for ~2 s of servo travel. We poll the UART
#   at each step so a fire report interrupts the scan instead
#   of waiting it out.
# ============================================================

def _fire_pending():
    return poll_command().startswith("FIRE")

def obstacle_mode():
    dist = distance()
    print("Front: {} cm | safe: {} cm".format(dist, SAFE_DIST))

    if dist >= SAFE_DIST:
        forward()
        return

    stop()
    time.sleep_ms(300)
    if _fire_pending():
        return

    servoLeft()
    leftDis = distance()
    if _fire_pending():
        servoCenter()
        return

    servoCenter()
    servoRight()
    rightDis = distance()
    servoCenter()
    if _fire_pending():
        return

    time.sleep_ms(300)

    if leftDis == 999 and rightDis == 999:
        print(">> Both open — turning left (default)")
        left()
    elif leftDis > rightDis and leftDis > SAFE_DIST:
        print(">> Turn left  ({} > {})".format(leftDis, rightDis))
        left()
    elif rightDis > leftDis and rightDis > SAFE_DIST:
        print(">> Turn right ({} > {})".format(rightDis, leftDis))
        right()
    else:
        # Boxed in — back out and take the better side.
        print(">> Both sides blocked — reversing")
        backward()
        time.sleep_ms(800)
        stop()
        time.sleep_ms(300)

        servoLeft()
        leftDis = distance()
        servoCenter()
        servoRight()
        rightDis = distance()
        servoCenter()

        left() if leftDis >= rightDis else right()

    time.sleep_ms(500)
    stop()
    time.sleep_ms(200)

# ============================================================
#   MAIN LOOP
# ============================================================
print("=== Fire-Seeking Car — waiting for host ===")
stop()
buzzer_off()
servoCenter()
time.sleep(1)

try:
    while True:
        cmd = poll_command()

        # Host gone quiet — drop back to patrolling rather than
        # continuing to drive on a stale fire bearing.
        if link_lost() and cmd != "NO_FIRE":
            print("[UART] link lost — reverting to patrol")
            command = cmd = "NO_FIRE"
            buzzer_off()

        if cmd.startswith("FIRE"):
            fire_mode(cmd)
        else:
            buzzer_off()
            obstacle_mode()

        time.sleep_ms(50)

except KeyboardInterrupt:
    pass
finally:
    # Never leave the motors or buzzer energised on exit.
    stop()
    buzzer_off()
    servoCenter()
    print("=== Stopped ===")
