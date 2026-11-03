# Listener (Remote -- central)

from BLE_CEEO import Listen
from joystick import Joystick
from machine import Pin
import time
import json

NAME = "Jude"     # must match the yeller's name
buffer = b""

js = Joystick()
btn_a = Pin(13, Pin.IN, Pin.PULL_UP)
btn_b = Pin(14, Pin.IN, Pin.PULL_UP)

CENTER = 2048
DEADZONE = 300   

# Joystick
def axis(raw):
    # turn a 0-4095 reading into -100..100, with a deadzone in the middle
    v = raw - CENTER
    if abs(v) < DEADZONE:
        return 0
    return int(v * 100 / 2048)


def send(p, msg):
    payload = json.dumps(msg) + "\n"
    for start in range(0, len(payload), 20):
        p.send(payload[start:start + 20])
        time.sleep_ms(20)

p = None

try:
    p = Listen(NAME, verbose=False)
    p.callback = callback

    print("Looking for Robot", NAME, "...")
    if p.connect_up():
        print("Connected")
        last = None
        while p.is_connected:
            msg = {
                "x": axis(js.adc_x.read()),
                "y": axis(js.adc_y.read()),
                "a": 1 if not btn_a.value() else 0,
                "b": 1 if not btn_b.value() else 0,
            }
            if msg != last:   # only send when something changed
                send(p, msg)
                last = msg
            time.sleep_ms(50)
    print("Lost connection")
finally:
    if p:
        p.disconnect()