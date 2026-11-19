# Listener (Robot -- central)

from BLE_CEEO import Listen
import time
import json
from machine import Pin, PWM
from colorLineCalibrate import LineSensors

NAME = "Jude"
buffer = b""

# read sensors
sensors = LineSensors()


# Each motor uses two PWM pins: one drives it one way, the other drives it the other way
class Motor:
    def __init__(self, m1, m2):
        self.M1 = PWM(m1, freq=500, duty_u16=0)
        self.M2 = PWM(m2, freq=500, duty_u16=0)

    def run(self, speed):                 # -100..100, positive = M1 side
        duty = int(min(abs(speed), 100) * 65535 / 100)
        if speed > 0:
            self.M1.duty_u16(duty)
            self.M2.duty_u16(0)
        elif speed < 0:
            self.M1.duty_u16(0)
            self.M2.duty_u16(duty)
        else:
            self.M1.duty_u16(0)
            self.M2.duty_u16(0)


right_motor = Motor(14, 27)               # same pins as ESPNOW/motorTest.py
left_motor = Motor(13, 12)                # order swapped so positive = forward, like lineFollow.py


def drive(l, r):                          # -100..100 each, positive = forward
    right_motor.run(r)
    left_motor.run(l)


drive(0, 0)                               # make sure motors are off at startup


buzzer = PWM(Pin(23), freq=440, duty_u16=0)   # built-in buzzer (same pin as lineFollow.py)

buzzer.duty_u16(0)                            # make sure the horn is off at startup
HORN_VOLUME = 2000                            # same volume lineFollow.py uses
last_a = 0
last_b = 0
last_seen = 0

NORMAL_SPEED = 60    # % of full speed when driving normally
BOOST_SPEED = 100     # % of full speed while button B is held


def handle(msg):
    # y = forward/back, x = turn. Mixing gives smooth arcade-style steering.
    scale = BOOST_SPEED if msg["b"] else NORMAL_SPEED
    y, x = msg["y"] * scale // 100, msg["x"] * scale // 100
    drive(y + x, y - x)

    # print only when a button changes (so the terminal isn't flooded)
    global last_a, last_b
    if msg["a"] != last_a:
        print("Button A (horn):", "pressed" if msg["a"] else "released")
        last_a = msg["a"]
    if msg["b"] != last_b:
        print("Button B (boost):", "pressed" if msg["b"] else "released")
        last_b = msg["b"]

    # button A = horn (sounds while held)
    buzzer.duty_u16(HORN_VOLUME if msg["a"] else 0)

def callback(data):
    # Pieces arrive in up to 20-byte chunks; a newline ends each message
    global buffer
    buffer += data
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        try:
            handle(json.loads(line.decode()))
        except ValueError:
            pass   # garbled message, ignore it

def send(p, msg):
    # send a dict as JSON ending in a newline, in 20-byte pieces
    payload = json.dumps(msg) + "\n"
    for start in range(0, len(payload), 20):
        p.send(payload[start:start + 20])
        time.sleep_ms(20)


def sendColor(p):
    global last_seen
    seen = 1 if sensors.right.color() == "red" else 0   # change "red" to your color

    if seen == last_seen:      # nothing changed, don't send
        return
    last_seen = seen

    send(p, {"color": "red" if seen else "none"})
    print("Sent color:", "red" if seen else "none")


p = None
try:
    p = Listen(NAME, verbose=False)
    p.callback = callback

    print("Looking for the remote", NAME, "...")
    if p.connect_up():
        print("Connected")
        while p.is_connected:
            sendColor(p)
            time.sleep_ms(100)
    print("Lost connection")
finally:
    drive (0,0)
    buzzer.duty_u16(0)
    if p:
        p.disconnect()