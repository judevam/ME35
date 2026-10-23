from machine import Pin, PWM, freq
import neopixel
import time

from spotifyAPI import (connect_wifi, refresh_token, now_playing, get_volume,
                        next_song, prev_song, play, pause, set_volume, play_playlist)
from joystick import Joystick
from colorScanner import ColorScanner, PLAYLISTS
from accelerometer import Accel

freq(240000000)   # full CPU speed -- makes each HTTPS handshake faster

# ---------------- PINS (Cytron Robo ESP32) ----------------
# joystick = 33 (X), 32 (Y) -> set in joystick.py
# color sensor = SDA 21, SCL 22 -> set in colorScanner.py
# motor encoder = 36, 39 -> not used yet (the turntable just spins)
SERVO_PIN = 4
MOTOR_PIN_A = 12      # motor speed (PWM)
MOTOR_PIN_B = 13      # kept low = one direction -- swap A and B if it spins the wrong way
NEOPIXEL_PIN = 15     # the board's 2 built-in RGB LEDs (same as your earlier projects)
NUM_PIXELS = 2
BUZZER_PIN = 23       # built-in buzzer

# ---------------- SETTINGS ----------------
MOTOR_SPEED = 30000          # 0-65535, how fast the turntable spins
HEAD_UP = 75                 # servo angle at the top of a bob
HEAD_DOWN = 44               # servo angle at the bottom of a bob
HEAD_REST = 70               # head drooped when paused
VOLUME_STEP = 10
POLL_MS = 8000               # how often to ask Spotify what's playing
VOLUME_DELAY = 400           # wait for the stick to settle, then send one volume change
SCAN_MS = 200                # how often to check the color sensor
DEFAULT_BPM = 100

# light color + default BPM for each record (until the BPM API is added)
RECORD_RGB = {"yellow": (50, 35, 0), "blue": (0, 0, 60), "green": (0, 60, 0)}
RECORD_BPM = {"yellow": 110, "blue": 85, "green": 125}

# ---------------- OUTPUTS ----------------
servo = PWM(Pin(SERVO_PIN), freq=50)
motor_a = PWM(Pin(MOTOR_PIN_A), freq=1000, duty_u16=0)
motor_b = Pin(MOTOR_PIN_B, Pin.OUT, value=0)
pixels = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)
buzzer = PWM(Pin(BUZZER_PIN), freq=1000, duty_u16=0)


def set_head(angle):
    us = 500 + (angle / 180) * (2500 - 500)
    servo.duty_ns(int(us * 1000))


def set_motor(on):
    motor_a.duty_u16(MOTOR_SPEED if on else 0)


def set_lights(rgb):
    for i in range(NUM_PIXELS):
        pixels[i] = rgb
    pixels.write()


def beep(freq, ms):
    # keep these short so they don't play over the music
    buzzer.freq(freq)
    buzzer.duty_u16(2000)
    time.sleep_ms(ms)
    buzzer.duty_u16(0)


def flash(rgb, ms=150):
    set_lights(rgb)
    time.sleep_ms(ms)


def show_state(on):
    # motor + lights for playing/paused -- called before API calls so the pet reacts instantly
    set_motor(on)
    if on:
        set_lights(RECORD_RGB.get(record, (30, 0, 30)))
    else:
        set_lights((3, 3, 3))                   # dim when paused
        set_head(HEAD_REST)


def safe(fn, *args):
    # run a Spotify call without crashing the pet if WiFi hiccups
    try:
        return fn(*args)
    except Exception as e:
        print("API error:", e)
        return None


# ---------------- GESTURES (TODO after recording headphone data) ----------------
def check_gesture(acc):
    # returns "skip" (shake no), "like" (nod yes) or None
    # TODO: fill in once we've looked at your nod/shake/tilt readings
    if acc is None:
        return None
    x, y, z = acc.read()
    return None


# ---------------- SETUP ----------------
print("Starting up...")
set_head(HEAD_REST)
set_lights((10, 0, 10))
connect_wifi()
refresh_token()

js = Joystick()
scanner = ColorScanner()
try:
    acc = Accel()
except OSError:
    acc = None            # not plugged in -- run without gestures
    print("No accelerometer found, skipping gestures")

volume = safe(get_volume) or 50
playing = False
track_uri = None
record = None              # last record scanned
bpm = DEFAULT_BPM
head_is_up = False
next_bob = 0
next_poll = 0
next_scan = 0
volume_send_at = None      # when to send the pending volume change (None = nothing pending)

beep(1500, 80)
beep(2000, 80)
print("Ready!")

# ---------------- MAIN LOOP ----------------
while True:
    now = time.ticks_ms()

    # --- joystick ---
    e = js.get_event()
    if e == "up":
        volume = min(100, volume + VOLUME_STEP)
        volume_send_at = time.ticks_add(now, VOLUME_DELAY)
    elif e == "down":
        volume = max(0, volume - VOLUME_STEP)
        volume_send_at = time.ticks_add(now, VOLUME_DELAY)
    elif e == "right":
        flash((40, 40, 40))
        safe(next_song)
        next_poll = time.ticks_add(now, 1000)   # check the new song soon
    elif e == "left":
        flash((40, 40, 40))
        safe(prev_song)
        next_poll = time.ticks_add(now, 1000)
    elif e == "press":
        playing = not playing
        show_state(playing)                     # react now, Spotify catches up
        beep(1200, 60)
        safe(play if playing else pause)

    if e in ("up", "down", "press"):
        # don't let a status check block the stick right after you use it
        next_poll = time.ticks_add(now, POLL_MS)

    # --- send the volume once the stick has settled ---
    if volume_send_at is not None and time.ticks_diff(now, volume_send_at) >= 0:
        volume_send_at = None
        safe(set_volume, volume)

    # --- color scanner (only while paused) ---
    if not playing and time.ticks_diff(now, next_scan) >= 0:
        next_scan = time.ticks_add(now, SCAN_MS)
        color = scanner.scan()
        if color in PLAYLISTS:
            print("Scanned record:", color)
            record = color
            bpm = RECORD_BPM.get(color, DEFAULT_BPM)
            set_head(HEAD_UP)                   # head lifts up
            beep(1800, 100)
            playing = True
            show_state(True)
            safe(play_playlist, PLAYLISTS[color])
            next_poll = time.ticks_add(now, 1500)

    # --- accelerometer gestures ---
    g = check_gesture(acc)
    if g == "skip":
        set_head(HEAD_REST)                     # head drops in disgust
        flash((60, 0, 0))
        beep(300, 120)
        safe(next_song)
        next_poll = time.ticks_add(now, 1000)

    # --- ask Spotify what's playing (also catches pausing from the laptop) ---
    if time.ticks_diff(now, next_poll) >= 0:
        next_poll = time.ticks_add(now, POLL_MS)
        try:
            info = now_playing()
            if info:
                song, artist, image_url, uri, is_playing = info
                playing = is_playing
                if uri != track_uri:
                    track_uri = uri
                    print("Now playing:", song, "-", artist)
                    # TODO: look up this song's BPM (ReccoBeats) and set bpm here
            else:
                playing = False
        except Exception as e:
            # keep the last state so the motor doesn't stutter on a WiFi blip
            print("API error:", e)

    # --- outputs ---
    show_state(playing)
    if playing:
        # head-bob to the beat: up and down once per beat
        if time.ticks_diff(now, next_bob) >= 0:
            head_is_up = not head_is_up
            set_head(HEAD_UP if head_is_up else HEAD_DOWN)
            half_beat = int(60000 / bpm / 2)
            next_bob = time.ticks_add(now, half_beat)

    time.sleep_ms(20)
