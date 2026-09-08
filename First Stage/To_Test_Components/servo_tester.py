# ============================================================
#   SG90 SERVO DIAGNOSTIC TESTER
#   Run this ALONE to test if your servo is working
#   Watch the serial output in Thonny to see what's happening
# ============================================================
from machine import Pin, PWM
import time

servo = PWM(Pin(16))
servo.freq(50)

print("=== SG90 SERVO TESTER ===")
print("Watch the servo shaft — it should rotate left and right")
print()

# ── All possible duty values to try ──────────────────────────
# At 50Hz, period = 20ms
# SG90 pulse range: 0.5ms to 2.5ms
#
#  0.5ms / 20ms * 65535 = 1638   → 0°
#  1.0ms / 20ms * 65535 = 3276   → 45°
#  1.5ms / 20ms * 65535 = 4915   → 90° (center)
#  2.0ms / 20ms * 65535 = 6553   → 135°
#  2.5ms / 20ms * 65535 = 8192   → 180°

positions = [
    ("0°   (Right)",   1638),
    ("45°  (Mid-R)",   3276),
    ("90°  (Center)",  4915),
    ("135° (Mid-L)",   6553),
    ("180° (Left)",    8192),
]

# ── TEST 1: Go through all positions one by one ──────────────
print("--- TEST 1: Stepping through all positions ---")
for label, duty in positions:
    print(f"  Moving to {label}  →  duty_u16 = {duty}")
    servo.duty_u16(duty)
    time.sleep(2)       # 2 seconds at each position

print()

# ── TEST 2: Sweep slowly from 0° to 180° ────────────────────
print("--- TEST 2: Slow sweep 0° → 180° → 0° ---")
print("  Sweeping right to left...")
for duty in range(1638, 8192, 50):
    servo.duty_u16(duty)
    time.sleep_ms(20)

print("  Sweeping left to right...")
for duty in range(8192, 1638, -50):
    servo.duty_u16(duty)
    time.sleep_ms(20)

print()

# ── TEST 3: Snap between extremes ───────────────────────────
print("--- TEST 3: Snapping between 0° and 180° (5 times) ---")
for i in range(5):
    print(f"  Snap {i+1}: Going to 0° (Right)")
    servo.duty_u16(1638)
    time.sleep(1)
    print(f"  Snap {i+1}: Going to 180° (Left)")
    servo.duty_u16(8192)
    time.sleep(1)

# ── Return to center ─────────────────────────────────────────
print()
print("--- Done! Returning to center (90°) ---")
servo.duty_u16(4915)
time.sleep(1)

# ── Turn off PWM signal (servo relaxes) ─────────────────────
servo.duty_u16(0)
print()
print("=== RESULTS ===")
print("If servo moved during ANY test → servo is FINE, check wiring")
print("If servo did NOT move at all   → check power or servo is faulty")
print()
print("WIRING CHECK:")
print("  SG90 Orange wire → GP0 (signal)")
print("  SG90 Red wire    → 3.3V or 5V (NOT from Pico pin, use VBUS or battery)")
print("  SG90 Brown wire  → GND")
