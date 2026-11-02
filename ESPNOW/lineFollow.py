from colorLineCalibrate import LineSensors
import time
import json
from machine import Pin
from machine import PWM
import neopixel

class Motor:
    def __init__(self,m1,m2):
        self.M1 = PWM(m1, freq=500, duty_u16=0)
        self.M2 = PWM(m2, freq=500, duty_u16=0)
        self.stop()

    def stop(self):
        self.M1.duty_u16(0)
        self.M2.duty_u16(0)

    def drive(self, speed, forward):
        # speed -100..100: positive drives the robot forward, negative reverses.
        # forward = the direction value (0 or 1) that makes THIS wheel push the robot forward
        if speed >= 0:
            self.start(forward, speed)
        else:
            self.start(1 - forward, -speed)

    def start(self, direction = 0, speed = 50):
        if direction:
            self.M1.duty_u16(int(speed*65535/100))
            self.M2.duty_u16(0)
        else:
            self.M1.duty_u16(0)
            self.M2.duty_u16(int(speed*65535/100))

BUZZER_PIN = 23       # built-in buzzer
Motor1 = Motor(14,27)
Motor2 = Motor(12,13)
buzzer = PWM(Pin(BUZZER_PIN), freq=1000, duty_u16=0)
NEOPIXEL_PIN = 15     # the board's 2 built-in RGB LEDs (same as DJude)
NUM_PIXELS = 2
pixels = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)

# Motor1 is on the right side of the robot, Motor2 on the left
LeftMotor = Motor2
RightMotor = Motor1

# read sensors
sensors = LineSensors()

# while True:
#     print("left: ", sensors.left.brightness())
#     print("right: ", sensors.right.brightness())
#     time.sleep(0.5)


# scale brightness, clamp motor speeds
def clamp(value, low, high):
    return max(low, min(high, value))


def scaled(sensor):
    # reading divided by that sensor's threshold: below 1 = black, above 1 = white
    # (clamped so a very bright reading can't blow up the error)
    return clamp(sensor.brightness() / sensor.threshold, 0, 2)

# LED color for each marker (0-255 per channel; kept dim, full brightness is very bright)
COLOR_RGB = {"red": (60, 0, 0), "green": (0, 60, 0), "blue": (0, 0, 60)}

def set_lights(rgb):
    for i in range(NUM_PIXELS):
        pixels[i] = rgb
    pixels.write()


# ---- melodies: a note player that never blocks the steering ----
# notes in Hz. A melody is a list of (note, beats); 0 = a rest. play_melody() queues it up and
# update_melody() (called every pass of the main loop) switches the buzzer from note to note.
C4, D4, E4, F4, G4, A4, B4 = 262, 294, 330, 349, 392, 440, 494
C5, D5, E5, F5, G5, A5, B5 = 523, 587, 659, 698, 784, 880, 988
C6 = 1047
REST = 0
NOTE_GAP = 25            # ms of silence after each note so repeated notes are heard separately

melody = []              # the steps being played: (freq, ms)
melody_i = 0
melody_next = 0          # when to move on to the next step

def play_melody(notes, beat_ms):
    # start a melody now (replaces one that is still playing)
    global melody, melody_i, melody_next
    steps = []
    for freq, beats in notes:
        ms = int(beats * beat_ms)
        if freq:
            steps.append((freq, ms - NOTE_GAP))
            steps.append((0, NOTE_GAP))
        else:
            steps.append((0, ms))
    melody = steps
    melody_i = 0
    melody_next = time.ticks_ms()
    buzzer.duty_u16(0)

def update_melody(now):
    # call every loop: moves to the next note when the current one is done
    global melody, melody_i, melody_next
    if not melody or time.ticks_diff(now, melody_next) < 0:
        return
    if melody_i >= len(melody):
        buzzer.duty_u16(0)
        melody = []
        return
    freq, ms = melody[melody_i]
    melody_i += 1
    if freq:
        buzzer.freq(freq)
        buzzer.duty_u16(BEEP_DUTY)
    else:
        buzzer.duty_u16(0)
    melody_next = time.ticks_add(now, ms)


# --- red: La Cucaracha ("La cu-ca-ra-cha, la cu-ca-ra-cha, ya no pue-de ca-mi-nar") ---
LA_CUCARACHA = [
    (C4, 1), (C4, 1), (C4, 1), (F4, 3), (A4, 2), (REST, 1),
    (C4, 1), (C4, 1), (C4, 1), (F4, 3), (A4, 2), (REST, 1),
    (F4, 1), (F4, 1), (E4, 1), (E4, 1), (D4, 1), (D4, 1), (C4, 4),
]

# --- blue: William Tell Overture finale -- the galloping "da da DUM" fanfare ---
# NOTE: the rhythm is the gallop, but I wrote the pitches from memory and could not check them
# against a score -- if it doesn't sound right, fix the notes here.
WILLIAM_TELL = [
    (G4, 1), (G4, 1), (G4, 2), (G4, 1), (G4, 1), (G4, 2),
    (C5, 1), (C5, 1), (C5, 2), (C5, 1), (C5, 1), (E5, 2),
    (G5, 1), (E5, 1), (C5, 3),
]

# --- green: Ride of the Valkyries -- the repeated-note heroic call ---
# NOTE: same warning as above: from memory, not checked against a score. Edit the notes to taste.
VALKYRIES = [
    (E5, 2), (E5, 1), (E5, 1), (A5, 3), (REST, 1),
    (E5, 2), (E5, 1), (E5, 1), (A5, 3), (REST, 1),
    (C6, 2), (A5, 1), (E5, 1), (A5, 4),
]

# one function per color -- called once when that marker is detected
def beepRed():
    play_melody(LA_CUCARACHA, 120)

def beepGreen():
    play_melody(VALKYRIES, 110)

def beepBlue():
    play_melody(WILLIAM_TELL, 90)

BEEP_FUNCS = {"red": beepRed, "green": beepGreen, "blue": beepBlue}



# add p controller
base = 40
Kp = 125
# left - right when the robot is in the ideal spot (left on white, right on black).
target = 0.38

Kd = 100


# what to do if it lost the line
# lost = both sensors clearly see white (see LOST_LEFT / LOST_RIGHT below). It pivots toward the side
# the line was last on: last error > 0 = line was to the left, otherwise to the right.
# "lost" = both sensors read plain white for LOST_STEPS steps in a row. Levels are from the log:
# left reads ~1.1 on white and ~0.75 on black; right reads ~0.65 on black and tops out ~1.0 on white
LOST_LEFT = 1.0
LOST_RIGHT = 0.93
LOST_STEPS = 5           # 5 steps = 250 ms of white on both sensors before it counts as lost
white_steps = 0

# remember which side the tape was last seen on, so a lost robot knows which way to look.
# "left" = the left sensor was on the tape (tape is to the left); "right" = the right sensor was.
RIGHT_DARK = 0.8         # right sensor below this = it is on the tape (it reads ~0.65-0.75 there)
tape_side = "right"

# the LEFT sensor normally sits on white. When it dips onto the tape the line is curving LEFT, so
# the robot has to turn left -- but a dark left reading used to look like "right sensor on white"
# (error went negative) and it turned RIGHT, away from the line.
LEFT_WHITE = 1.1         # what the left sensor reads on plain white (measure it: see the log)
LEFT_MARGIN = 0.1        # left must dip this far below LEFT_WHITE before it counts as on the tape
CORNER_GAIN = 1.5        # how hard to turn left per 1.0 the left sensor dips (0.25 dip -> ~+0.4 error)

# turning hard the same way for too long means it's spinning, not following: stop
STUCK_ERROR = 0.25
STUCK_STEPS = 16         # 16 steps = 0.8 s
stuck_steps = 0
LOST_SPEED = 20          # speed of the driving wheel while searching (the other wheel stops)
LOST_TIMEOUT = 2000      # ms of searching before giving up and stopping
lost_since = None
last_error = 0           # last error seen on the line: decides which way to search when lost

# slow down in turns: forward speed drops as the error grows
SLOW_FACTOR = 50         # speed lost per 1.0 of |error| -- raise to slow down more in turns
MIN_BASE = 12            # never slow below this (motors stall at very low speeds)

# color markers on the line: each color plays its own melody (beepRed, beepGreen, beepBlue)
BEEP_DUTY = 2000         # buzzer volume (same as DJude)
MARKER_COLORS = ["red", "green", "blue"]
STABLE_COUNT = 3         # same marker this many color checks in a row before it counts
CONTROL_MS = 50          # steer + check for markers this often (a bit over the sensor's ~40 ms update)
next_control = 0
MAX_D_TERM = 30          # the derivative part of the correction can never be bigger than this
skip_d = True            # True = ignore the derivative once (first step, or just found the line again)
PRINT_MS = 200           # how often to print the steering numbers (printing every loop is slow)
next_print = 0
LOG = True               # True = print one compact line per steering step, to paste back for analysis
                         # columns: ms, left, right, error, d_term, L speed, R speed  (or LOST)
MARKER_COOLDOWN = 1000   # ms before the SAME color can beep again, so one marker beeps once
last_beep_color = None   # color of the last beep
seen_color = None
seen_reads = 0
last_beep = time.ticks_add(time.ticks_ms(), -MARKER_COOLDOWN)   # so the first marker can beep

# ---- ESP-NOW: tell another ESP which marker we just saw ----
# Everything here is set up ONCE, before the robot starts, and a send is one quick call in the
# marker branch (once per marker, because of MARKER_COOLDOWN) -- never every loop.
ESPNOW_ENABLED = True
PEER_MAC = bytes([0x20, 0x50, 0x0d, 0x2b, 0x14, 0x3c])     # the OTHER board's MAC (from macAddress.py), as 6 bytes
                         # (run macAddress.py on that board). None = ESP-NOW stays off.
# same message format as getPartner.py, so a receiver written for it will light its LED
MARKER_MESSAGES = {c: json.dumps({"state": "color", "payload": list(COLOR_RGB[c])}) for c in COLOR_RGB}
espnow_link = None

if ESPNOW_ENABLED and PEER_MAC is not None:
    try:
        import network
        import espnow
        sta = network.WLAN(network.WLAN.IF_STA)
        sta.active(True)
        sta.disconnect()
        espnow_link = espnow.ESPNow()
        espnow_link.active(True)
        espnow_link.add_peer(PEER_MAC)
    except Exception as err:            # a radio problem must never stop the robot
        print("ESP-NOW unavailable:", err)
        espnow_link = None

def send_marker(color):
    # fire and forget: sync=False returns right away instead of waiting for the other board's ACK
    if espnow_link is None:
        return
    try:
        espnow_link.send(PEER_MAC, MARKER_MESSAGES[color], False)
    except OSError as err:
        print("ESP-NOW send failed:", err)

# start button: the robot waits here until D34 is pressed
START_PIN = 34           # D34 (input only -- the board has no internal pull-up for it)
START_PRESSED = 0        # value the pin reads when pressed (0 for a button to ground).
                         # If it starts by itself without a press, change this to 1.
start_button = Pin(START_PIN, Pin.IN)
STOP_PIN = 35            # D35 stops the robot (also input only, no internal pull-up)
STOP_PRESSED = 0         # value the pin reads when pressed (0 for a button to ground)
stop_button = Pin(STOP_PIN, Pin.IN)
first_run = True
while True:
    # wait here until D34 is pressed (after a stop, D35 starts it again too)
    while stop_button.value() == STOP_PRESSED:      # let go of D35 first, it was just used to stop
        time.sleep_ms(10)
    if first_run:
        print("Ready -- press D34 to start line following")
    else:
        print("Stopped -- press D35 or D34 to run again")
    while not (start_button.value() == START_PRESSED
               or (not first_run and stop_button.value() == STOP_PRESSED)):
        time.sleep_ms(10)
    first_run = False
    time.sleep_ms(300)       # let the button settle so one press doesn't count twice
    while stop_button.value() == STOP_PRESSED:      # a D35 press that started the run must not stop it
        time.sleep_ms(10)
    print("Go!")

    # fresh state for every run
    white_steps = 0
    stuck_steps = 0
    lost_since = None
    last_error = 0
    skip_d = True
    next_control = 0
    seen_color = None
    seen_reads = 0
    tape_side = "right"

    try:
        while True:
            now = time.ticks_ms()

            # --- D35 stops the robot (the finally block below stops the motors) ---
            if stop_button.value() == STOP_PRESSED:
                print("Stopped by D35")
                break

            # --- keep the current melody going (doesn't block the driving) ---
            update_melody(now)

            # --- steer only once per CONTROL_MS, about how often the sensors give a new reading.
            # The wheels keep their last speeds in between. A faster loop just re-reads the same value,
            # which made the derivative 0 most loops and then one big spike.
            if time.ticks_diff(now, next_control) < 0:
                continue
            next_control = time.ticks_add(now, CONTROL_MS)

            left = scaled(sensors.left)
            right = scaled(sensors.right)

            # --- color markers: right sensor only (it's the one on the tape).
            # color(fresh=False) reuses the reading scaled() just took -- no extra I2C read.
            color = sensors.right.color(fresh=False)
            if color not in MARKER_COLORS:
                color = None
            if color is not None and color == seen_color:
                seen_reads += 1
            else:
                seen_color = color
                seen_reads = 1 if color is not None else 0
            # lights show the last marker color seen, and stay on until a different marker is seen
            if seen_reads == STABLE_COUNT:
                set_lights(COLOR_RGB[seen_color])

            # a different color can beep right away; the same color waits out the cooldown
            cooled_down = (seen_color != last_beep_color
                           or time.ticks_diff(now, last_beep) >= MARKER_COOLDOWN)
            if seen_reads == STABLE_COUNT and cooled_down:
                print("marker:", seen_color)
                BEEP_FUNCS[seen_color]()
                send_marker(seen_color)
                last_beep = now
                last_beep_color = seen_color

            if left < LEFT_WHITE - LEFT_MARGIN:
                tape_side = "left"
            elif right < RIGHT_DARK:
                tape_side = "right"
            both_white = left > LOST_LEFT and right > LOST_RIGHT
            if both_white:
                white_steps += 1
            else:
                white_steps = 0
            if white_steps >= LOST_STEPS:
                if lost_since is None:
                    lost_since = time.ticks_ms()
                if time.ticks_diff(time.ticks_ms(), lost_since) > LOST_TIMEOUT:
                    print("Lost the line, stopping")
                    break
                skip_d = True               # the first derivative after finding the line would be stale
                if LOG:
                    print(now, round(left, 2), round(right, 2), "LOST")
                if tape_side == "left":
                    # the tape was last under the left sensor -- pivot left: right wheel drives
                    print("lost -- searching left")
                    RightMotor.drive(LOST_SPEED, 1)
                    LeftMotor.stop()
                else:
                    # the tape was last under the right sensor -- pivot right: left wheel drives
                    print("lost -- searching right")
                    LeftMotor.drive(LOST_SPEED, 0)
                    RightMotor.stop()
                continue
            lost_since = None

            left_dark = max(0, LEFT_WHITE - left - LEFT_MARGIN)
            edge_error = (LEFT_WHITE - right) - target       # positive = right sensor too far onto the tape
            if left_dark > 0:
                error = CORNER_GAIN * left_dark + max(0, edge_error)   # tape under the left sensor: turn left
            elif both_white and tape_side == "left":
                error = abs(edge_error)                                # tape is on the left: turn left
            else:
                error = edge_error
            if abs(error) > STUCK_ERROR and error * last_error > 0:
                stuck_steps += 1
            else:
                stuck_steps = 0
            if stuck_steps >= STUCK_STEPS:
                print("Turning one way without finding the line, stopping")
                break
            if skip_d:
                last_error = error          # first step, or just found the line: no derivative kick
                skip_d = False
            derivative = error - last_error
            last_error = error
            d_term = clamp(Kd * derivative, -MAX_D_TERM, MAX_D_TERM)
            correction = (Kp * error) + d_term
            forward = max(MIN_BASE, base - SLOW_FACTOR * abs(error))
            left_speed = clamp(forward - correction, -100, 100)    # negative = wheel reverses
            right_speed = clamp(forward + correction, -100, 100)
            if LOG:
                print(now, round(left, 2), round(right, 2), round(error, 2), round(d_term, 1),
                      int(left_speed), int(right_speed))
            elif time.ticks_diff(now, next_print) >= 0:
                next_print = time.ticks_add(now, PRINT_MS)
                print("left:", round(left, 2), "right:", round(right, 2), "l-r:", round(left - right, 2),
                      "error:", round(error, 2), "d:", round(d_term, 1), "fwd:", round(forward),
                      "L:", left_speed, "R:", right_speed)
            LeftMotor.drive(left_speed, 0)
            RightMotor.drive(right_speed, 1)

    finally:
        # runs when you press Ctrl+C (or on a crash) so the robot doesn't keep driving
        LeftMotor.stop()
        RightMotor.stop()
        buzzer.duty_u16(0)
        set_lights((0, 0, 0))


# tune


