# Yell (Remote -- peripheral)

from BLE_CEEO import Yell
from joystick import Joystick
from machine import Pin, PWM
import time
import json
import veml6040
import neopixel

NAME = "Jude"     # must match the yeller's name
buffer = b""

robot_color="None"

lights = neopixel.NeoPixel(Pin(15),2)

js = Joystick()
btn_a = Pin(19, Pin.IN, Pin.PULL_UP)
btn_b = Pin(5, Pin.IN, Pin.PULL_UP)
buzzer = PWM(Pin(23), freq=1000, duty_u16=0)

DEADZONE = 300
PRESS = 3800     # pressing the stick spikes a reading to max -> treat as stop

# Measure the resting position at startup (leave the stick alone!)
time.sleep_ms(500)
CENTER_X = sum(js.adc_x.read() for _ in range(20)) // 20
CENTER_Y = sum(js.adc_y.read() for _ in range(20)) // 20
print("Center:", CENTER_X, CENTER_Y)


# Setting up celebration song
C5, E5, G5, C6 = 523, 659, 784, 1047
MELODY = [
    (C5, 120), (0, 30),
    (E5, 120), (0, 30),
    (G5, 120), (0, 30),
    (C6, 300), (0, 80),
    (G5, 120), (0, 30),
    (C6, 500),
]

song_i = 0
note_end = 0

def update_song(active):
    global song_i, note_end
    if not active:
        # not red: silence and reset so it can play again next time
        buzzer.duty_u16(0)
        song_i = 0
        note_end = time.ticks_ms()
        return
    now = time.ticks_ms()
    if time.ticks_diff(now, note_end) < 0:
        return                      # current note still playing
    if song_i >= len(MELODY):
        buzzer.duty_u16(0)          # song finished, stay quiet until red clears
        return
    freq, dur = MELODY[song_i]
    if freq:
        buzzer.freq(freq)
        buzzer.duty_u16(2000)
    else:
        buzzer.duty_u16(0)
    note_end = time.ticks_add(now, dur)
    song_i += 1

def axis(raw, center):
    # turn a 0-4095 reading into -100..100, with a deadzone in the middle
    v = raw - center
    if abs(v) < DEADZONE:
        return 0
    return max(-100, min(100, int(v * 100 / 1000)))


def send(p, msg):
    payload = json.dumps(msg) + "\n"
    for start in range(0, len(payload), 20):
        p.send(payload[start:start + 20])
        time.sleep_ms(20)

def callback(data):
    global buffer, robot_color
    buffer += data
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        try:
            print("Robot says:", json.loads(line.decode()))
            robot_color=json.loads(line.decode())["color"]
        except ValueError:
            pass

p = None


try:
    p = Yell(NAME, interval_us=30000,verbose=False)
    p.callback=callback

    print("Looking for Robot", NAME, "...")
    if p.connect_up():
        print("Connected")
        last = None
        while p.is_connected:
            rx = js.adc_x.read()
            ry = js.adc_y.read()
            if rx > PRESS or ry > PRESS:      # stick pressed down -> stop
                jx, jy = 0, 0
            else:
                jx, jy = -axis(rx, CENTER_X), axis(ry, CENTER_Y)
            print(jx,jy)
            msg = {
                "x": jx,
                "y": jy,
                "a": 1 if not btn_a.value() else 0,
                "b": 1 if not btn_b.value() else 0,
            }
            if msg != last:   # only send when something changed
                send(p, msg)
                last = msg
            time.sleep_ms(50)
            update_song(robot_color == "red")
            if robot_color == "red":
                lights[0]=(60,0,0)
                lights[1]=(60,0,0)
                lights.write()
            if robot_color != "red":
                lights[0]=(0,0,0)
                lights[1]=(0,0,0)
                lights.write()

    print("Lost connection")
finally:
    if p:
        p.disconnect()