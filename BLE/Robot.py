# Yeller (Robot -- peripheral)

from BLE_CEEO import Yell
import time
import json
from machine import Pin, PWM

NAME = "Jude"
buffer = b""

# Set motor pins
left_dir  = Pin(12, Pin.OUT);  left_pwm  = PWM(Pin(13), freq=1000)
right_dir = Pin(14, Pin.OUT);  right_pwm = PWM(Pin(27), freq=1000)

def drive(l, r):                          # -100..100 each
    l = max(-100, min(100, l))
    r = max(-100, min(100, r))
    left_dir.value(l >= 0);   left_pwm.duty(abs(l) * 1023 // 100)
    right_dir.value(r >= 0);  right_pwm.duty(abs(r) * 1023 // 100)


def handle(msg):
    # y = forward/back, x = turn. Mixing gives smooth arcade-style steering.
    y, x = msg["y"], msg["x"]
    drive(y + x, y - x)

    if msg["a"]:
        print("Button A")                 # put your action here (horn, servo, etc.)
    if msg["b"]:
        print("Button B")

def callback(data):
    # Pieces arrive in up to 20-byte chunks; a newline ends each message
    global buffer
    buffer += data
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        print("Received:", json.loads(line.decode()))


p = None
try:
    p = Yell(NAME, interval_us=30000, verbose=False)
    p.callback = callback

    print("Waiting for the remote...")
    if p.connect_up():
        print("Connected")
        while p.is_connected:
            time.sleep_ms(100)
    print("Lost connection")
finally:
    drive (0,0)
    if p:
        p.disconnect()