# ============================================================
#   OBSTACLE AVOIDING CAR — Raspberry Pi Pico (MicroPython)
#   FIXED: Long range sensing + reliable distance reading
# ============================================================
from machine import Pin, PWM
import time

# ── Servo ────────────────────────────────────────────────────
servo = PWM(Pin(0))
servo.freq(50)

# ── Ultrasonic ───────────────────────────────────────────────
Trig = Pin(2, Pin.OUT)
Echo = Pin(3, Pin.IN)

# ── Motor Driver ─────────────────────────────────────────────
ENA = PWM(Pin(4))
IN1 = Pin(5, Pin.OUT)
IN2 = Pin(6, Pin.OUT)
IN3 = Pin(7, Pin.OUT)
IN4 = Pin(8, Pin.OUT)
ENB = PWM(Pin(9))

ENA.freq(1000)
ENB.freq(1000)

MAX_SPEED  = 65535
TURN_SPEED = 50000

# ── KEY SETTINGS ─────────────────────────────────────────────
SAFE_DIST    = 35    # ← INCREASE THIS to detect obstacles earlier
                     #   HC-SR04 range: 2cm – 400cm
                     #   35cm gives robot enough time to stop & turn
                     #   Increase to 50cm if still bumping

SAMPLES      = 5     # readings averaged per measurement (more = more reliable)
ECHO_TIMEOUT = 38000 # µs — covers full 400cm range of HC-SR04
                     # (400cm * 2 / 0.0343cm/µs ≈ 23,000µs, 38000 = safe ceiling)

# ============================================================
#   MOTOR FUNCTIONS
# ============================================================

def forward():
    ENA.duty_u16(MAX_SPEED)
    IN1.value(0); IN2.value(1)
    ENB.duty_u16(MAX_SPEED)
    IN3.value(1); IN4.value(0)

def backward():
    ENA.duty_u16(TURN_SPEED)
    IN1.value(1); IN2.value(0)
    ENB.duty_u16(TURN_SPEED)
    IN3.value(0); IN4.value(1)

def left():
    ENA.duty_u16(TURN_SPEED)
    IN1.value(1); IN2.value(0)   # Motor 1 backward
    ENB.duty_u16(TURN_SPEED)
    IN3.value(1); IN4.value(0)   # Motor 2 forward

def right():
    ENA.duty_u16(TURN_SPEED)
    IN1.value(0); IN2.value(1)   # Motor 1 forward
    ENB.duty_u16(TURN_SPEED)
    IN3.value(0); IN4.value(1)   # Motor 2 backward

def stop():
    ENA.duty_u16(0)
    IN1.value(0); IN2.value(0)
    ENB.duty_u16(0)
    IN3.value(0); IN4.value(0)

# ============================================================
#   SINGLE RAW DISTANCE READING
#   - Uses ECHO_TIMEOUT to cover full HC-SR04 range
#   - Returns 999 if no echo (open space)
# ============================================================

def _read_once():
    # Start LOW
    Trig.value(0)
    time.sleep_us(5)            # slightly longer settle time

    # 10µs trigger pulse
    Trig.value(1)
    time.sleep_us(10)
    Trig.value(0)

    # Wait for Echo HIGH — timeout after ECHO_TIMEOUT µs
    start = time.ticks_us()
    while Echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > ECHO_TIMEOUT:
            return 999          # sensor not responding

    pulse_start = time.ticks_us()

    # Wait for Echo LOW — timeout after ECHO_TIMEOUT µs
    while Echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), pulse_start) > ECHO_TIMEOUT:
            return 999          # object too far or open space

    pulse_end = time.ticks_us()

    # Calculate distance
    duration = time.ticks_diff(pulse_end, pulse_start)
    cm = (duration * 0.0343) / 2
    return round(cm, 1)

# ============================================================
#   AVERAGED DISTANCE  ← KEY FIX
#   Takes SAMPLES readings, discards 999 (timeouts),
#   discards outliers (min & max), returns average.
#   This eliminates random spikes that let robot through.
# ============================================================

def distance():
    readings = []

    for _ in range(SAMPLES):
        d = _read_once()
        if d != 999:            # ignore timeout readings
            readings.append(d)
        time.sleep_ms(15)       # HC-SR04 needs ~15ms between pings

    if not readings:
        return 999              # all readings timed out = open space

    if len(readings) == 1:
        return readings[0]

    # Drop highest and lowest to remove outliers
    if len(readings) > 3:
        readings.remove(max(readings))
        readings.remove(min(readings))

    avg = sum(readings) / len(readings)
    return round(avg, 1)

# ============================================================
#   SERVO
#   SG90 correct duty values at 50Hz (period = 20ms):
#     0°   = 0.5ms → duty_u16 = 1638
#     90°  = 1.5ms → duty_u16 = 4915
#     180° = 2.5ms → duty_u16 = 8192
# ============================================================

def servoLeft():
    servo.duty_u16(8192)        # 180° — look left
    time.sleep_ms(600)          # wait for servo to physically reach position

def servoRight():
    servo.duty_u16(1638)        # 0°  — look right
    time.sleep_ms(600)

def servoCenter():
    servo.duty_u16(4915)        # 90° — look forward
    time.sleep_ms(600)

# ============================================================
#   MAIN LOOP
# ============================================================

print("=== Obstacle Avoiding Car Started ===")
servoCenter()
time.sleep(1)

while True:
    dis = distance()
    print(f"Front: {dis} cm  |  Safe zone: {SAFE_DIST} cm")

    if dis < SAFE_DIST:
        # ── Obstacle detected ─────────────────────────────────
        stop()
        time.sleep_ms(300)

        # Scan LEFT
        servoLeft()
        leftDis = distance()    # averaged reading
        print(f"  Left  scan: {leftDis} cm")

        servoCenter()

        # Scan RIGHT
        servoRight()
        rightDis = distance()   # averaged reading
        print(f"  Right scan: {rightDis} cm")

        servoCenter()
        time.sleep_ms(300)

        # ── Choose direction ──────────────────────────────────
        if leftDis == 999 and rightDis == 999:
            # Both sides completely open
            print(">> Both open — turning left (default)")
            left()
            time.sleep_ms(500)
            stop()

        elif leftDis > rightDis and leftDis > SAFE_DIST:
            print(f">> Turn Left  (left={leftDis} > right={rightDis})")
            left()
            time.sleep_ms(500)
            stop()

        elif rightDis > leftDis and rightDis > SAFE_DIST:
            print(f">> Turn Right (right={rightDis} > left={leftDis})")
            right()
            time.sleep_ms(500)
            stop()

        else:
            # Both sides blocked → reverse then re-scan
            print(">> Both sides blocked! Reversing...")
            backward()
            time.sleep_ms(800)
            stop()
            time.sleep_ms(300)

            # Re-scan after reversing
            servoLeft()
            leftDis = distance()
            servoCenter()
            servoRight()
            rightDis = distance()
            servoCenter()

            if leftDis >= rightDis:
                left()
            else:
                right()
            time.sleep_ms(500)
            stop()

        time.sleep_ms(200)

    else:
        # ── Clear path → full speed forward ──────────────────
        forward()

    time.sleep_ms(50)