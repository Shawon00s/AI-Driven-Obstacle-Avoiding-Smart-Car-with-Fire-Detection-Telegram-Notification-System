# AI-Driven Obstacle-Avoiding Smart Car

An experimental two-stage robotic-car project developed with a Raspberry Pi Pico, an HC-SR04 ultrasonic sensor, an SG90 servo, an L298N motor driver, and a camera-based fire-detection pipeline.

> **Repository status:** The obstacle-avoidance controller and the Python fire-detection service are included. The report also describes an ESP32-CAM/IR-sensor/buzzer integration, but its Arduino firmware and the Pico-to-fire-sensor integration are not present in this repository. `Second Stage/main.py` is currently empty, so the two stages should be run as separate programs.

## What Was Built

### Stage 1: Obstacle Avoidance

The Raspberry Pi Pico drives two DC motors through the L298N and moves an HC-SR04 sensor with an SG90 servo. The controller:

1. Measures the distance in front of the car.
2. Drives forward while the path is clear.
3. Stops when an obstacle is closer than the configured safe distance.
4. Scans left and right by rotating the servo.
5. Turns toward the side with more clearance.
6. Reverses and rescans when both sides are blocked.

The current controller in [First Stage/Obstacle_Avoiding_Car.py](First%20Stage/Obstacle_Avoiding_Car.py) uses a **35 cm** safe-distance threshold, five sensor samples per scan, outlier removal, and a 50 ms main-loop delay. A single ultrasonic reading is calculated from the echo pulse as:

```text
distance_cm = echo_time_us * 0.0343 / 2
```

The earlier prototype is retained in [First Stage/To_Test_Components/obstacle robot.py](First%20Stage/To_Test_Components/obstacle%20robot.py). It used a 10 cm threshold and did not have timeout protection or averaged readings. The report describes a 15 cm threshold; that is a historical test value, not the setting in the current controller.

### Stage 2: Fire Detection and Notification

The checked-in Python service in [Second Stage/fire_detection.py](Second%20Stage/fire_detection.py) is a computer-side implementation of the later stage. It:

- Loads the YOLO model from [Second Stage/fire.pt](Second%20Stage/fire.pt).
- Reads an MJPEG camera stream at `STREAM_URL`.
- Runs fire inference at a confidence threshold of 0.5.
- Classifies the fire position as `FIRE_LEFT`, `FIRE_CENTER`, or `FIRE_RIGHT`.
- Sends changed commands over serial at 115200 baud.
- Provides a Flask live-view page and status endpoint.
- Queues a fire image and sends it to Telegram, with a 15-second notification cooldown.

This implementation is different from the report's earlier architecture, which describes an IR fire sensor, passive buzzer, and ESP32-CAM firmware sending a still JPEG directly through the Telegram Bot API. Those report-described components should be treated as project history unless the missing firmware and wiring code are restored.

## Hardware and Pin Map

The pin assignments below are taken from the current Pico controller:

| Component | Pico connection |
| --- | --- |
| Servo signal | GP0, PWM 50 Hz |
| HC-SR04 trigger | GP2 |
| HC-SR04 echo | GP3 |
| L298N ENA | GP4, PWM 1 kHz |
| L298N IN1 / IN2 | GP5 / GP6 |
| L298N IN3 / IN4 | GP7 / GP8 |
| L298N ENB | GP9, PWM 1 kHz |

The report lists the following project hardware: Raspberry Pi Pico, ESP32-CAM, ESP32-CAM programming base board, HC-SR04, SG90 servo, L298N, IR fire detector, passive buzzer, two-wheel chassis, LM2596 buck converter, batteries, and a power bank. Power must be supplied according to the ratings of the actual board and peripherals; do not power motors or a servo directly from a Pico GPIO pin.

## Project Images

### Circuit reference

![Pico, L298N, servo, ultrasonic sensor, and battery wiring](First%20Stage/Circuit.jpg)

The circuit image is a wiring reference. Verify every connection against the pin map and the hardware revision before powering the car.

### Assembled car

![Assembled smart car](Second%20Stage/Car.jpg)

## Running Stage 1

1. Connect the Pico, motor driver, servo, and HC-SR04 according to the pin map.
2. Open [First Stage/Obstacle_Avoiding_Car.py](First%20Stage/Obstacle_Avoiding_Car.py) in Thonny.
3. Upload it to the Pico and run it on the MicroPython device.
4. Use the serial console to observe front, left, and right distance readings.

Run [First Stage/To_Test_Components/servo_tester.py](First%20Stage/To_Test_Components/servo_tester.py) by itself when checking the SG90. It exercises the servo from 0 to 180 degrees and returns it to center.

### Stage 1 performance

The report says the car was tested successfully indoors, but it does not provide repeat counts, reaction time, collision rate, battery runtime, or measured turning angles. From the current code, each scan takes at least 5 readings with a 15 ms gap, plus servo movement waits of 600 ms and a 300 ms stop delay. Actual performance depends on motor speed, surface, battery voltage, sensor placement, and the servo's physical movement time. For reproducible evaluation, record obstacle distance, successful avoidance, collision, turn direction, and battery voltage over a fixed number of trials.

## Running Stage 2

The current second stage runs on a computer with Python packages for Ultralytics, OpenCV, NumPy, Requests, Flask, and PySerial. Before running it:

1. Place `fire.pt` in the same directory as `fire_detection.py`.
2. Use [`.env.example`](.env.example) as a reference, then set the configuration in your shell. Do not put real values in the Python file:

```powershell
$env:BOT_TOKEN = "your-new-telegram-bot-token"
$env:CHAT_ID = "your-telegram-chat-id"
$env:STREAM_URL = "http://camera-ip/stream"
$env:SERIAL_PORT = "COM5"
```

	On Bash, use `export NAME="value"` instead. Configure a new bot token if an old token was ever shared; secrets should not be committed to Git.
3. Start the service:

```bash
cd "Second Stage"
python fire_detection.py
```

Open `http://localhost:5000` to view the annotated stream and status. The service sends the directional fire command over serial; the matching receiver firmware is not included here.

## Report Findings and Limitations

- **Power:** The report found that the LM2596 setup was unstable under load and used a USB power bank for the Pico, with the motors powered separately.
- **Camera compatibility:** The report describes replacing an incompatible ESP32-CAM/OV2640 combination with the intended RHYX-M21-45 camera configuration.
- **Fire detection:** The report notes inconsistent detection caused by fire distance, angle, ambient light, and fixed sensor/model sensitivity.
- **Connectivity:** Telegram notification needs Wi-Fi or another internet connection.
- **Coverage:** One front-mounted ultrasonic sensor cannot see all side and rear obstacles.
- **Power management:** There is no battery-level monitoring or low-battery alert.
- **Scope:** The report's planned water pump, real-time streaming on the ESP32-CAM, 360-degree sensing, GPS, and custom fire model are future work. The checked-in Python service does provide a local annotated stream, but it is not the report's missing ESP32-CAM firmware.

The report lists a total project cost of **BDT 3,818**, including the non-functional buck module and replaced camera hardware.

## Future Improvements

- Add a water pump and reservoir for fire suppression.
- Replace fixed fire sensing with a validated custom-trained model or calibrated sensor.
- Restore a documented Pico-to-camera/controller integration.
- Add multi-directional sensing or LiDAR.
- Add battery monitoring and location reporting.
- Move Telegram credentials to environment variables or a secret store.

## Development Tools

- **Thonny + MicroPython:** Pico motor, servo, and ultrasonic control.
- **Python:** YOLO inference, OpenCV stream handling, Flask dashboard, serial control, and Telegram upload.
- **Arduino IDE:** Used in the report for the ESP32-CAM firmware, which is not included in this checkout.