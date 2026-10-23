from machine import Pin, PWM
import neopixel
import time

from spotifyAPI import (connect_wifi, refresh_token, now_playing, get_volume,
                        next_song, prev_song, play, pause, set_volume, play_playlist)
from joystick import Joystick
from colorScanner import ColorScanner, PLAYLISTS
from accelerometer import Accel

# ---------------- PINS (change to match your wiring) ----------------
SERVO_PIN = 4
MOTOR_PIN_A = 18      # DC motor driver input 1 (speed)
MOTOR_PIN_B = 19      # DC motor driver input 2 (kept low = one direction)
NEOPIXEL_PIN = 15
NUM_PIXELS = 2
BUZZER_PIN = 23

# ---------------- SETTINGS ----------------
MOTOR_SPEED = 30000          # 0-65535, how fast the turntable spins
HEAD_UP = 90                 # servo angle at the top of a bob
HEAD_DOWN = 70               # servo angle at the bottom of a bob
HEAD_REST = 60               # head drooped when paused
VOLUME_STEP = 10
POLL_MS = 5000               # how often to ask Spotify what's playing
SCAN_MS = 200                # how often to check the color sensor
DEFAULT_BPM = 100

# light color + default BPM for each record (until the BPM API is added)
RECORD_RGB = {"red": (60, 0, 0), "blue": (0, 0, 60), "green": (0, 60, 0)}
RECORD_BPM = {"red": 125, "blue": 85, "green": 100}

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
acc = Accel()

volume = safe(get_volume) or 50
playing = False
track_uri = None
record = None              # last record scanned
bpm = DEFAULT_BPM
head_is_up = False
next_bob = 0
next_poll = 0
next_scan = 0

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
        safe(set_volume, volume)
    elif e == "down":
        volume = max(0, volume - VOLUME_STEP)
        safe(set_volume, volume)
    elif e == "right":
        flash((40, 40, 40))
        safe(next_song)
        next_poll = time.ticks_add(now, 1000)   # check the new song soon
    elif e == "left":
        flash((40, 40, 40))
        safe(prev_song)
        next_poll = time.ticks_add(now, 1000)
    elif e == "press":
        if playing:
            safe(pause)
            playing = False
        else:
            safe(play)
            playing = True
        beep(1200, 60)

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
            safe(play_playlist, PLAYLISTS[color])
            playing = True
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
        info = safe(now_playing)
        if info:
            song, artist, image_url, uri, is_playing = info
            playing = is_playing
            if uri != track_uri:
                track_uri = uri
                print("Now playing:", song, "-", artist)
                # TODO: look up this song's BPM (ReccoBeats) and set bpm here
        else:
            playing = False

    # --- outputs ---
    set_motor(playing)
    if playing:
        set_lights(RECORD_RGB.get(record, (30, 0, 30)))
        # head-bob to the beat: up and down once per beat
        if time.ticks_diff(now, next_bob) >= 0:
            head_is_up = not head_is_up
            set_head(HEAD_UP if head_is_up else HEAD_DOWN)
            half_beat = int(60000 / bpm / 2)
            next_bob = time.ticks_add(now, half_beat)
    else:
        set_lights((3, 3, 3))                   # dim when paused
        set_head(HEAD_REST)

    time.sleep_ms(20)
