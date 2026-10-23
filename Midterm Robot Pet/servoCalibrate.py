from machine import Pin, PWM
import time

# Head servo calibration -- run this file and type commands in the REPL.
# Find good angles, test the bob, then copy the printed settings into DJude.py.
SERVO_PIN = 4    # same as DJude.py

servo = PWM(Pin(SERVO_PIN), freq=50)

# starting values (same as DJude.py)
head_up = 75
head_down = 44
head_rest = 70
bpm = 100


def set_head(angle):
    # same math as DJude.py so the angles match
    us = 500 + (angle / 180) * (2500 - 500)
    servo.duty_ns(int(us * 1000))


def bob(beats):
    # bob up and down once per beat, same timing as DJude.py
    half_beat = int(60000 / bpm / 2)
    for i in range(beats):
        set_head(head_up)
        time.sleep_ms(half_beat)
        set_head(head_down)
        time.sleep_ms(half_beat)


def show_settings():
    print("Paste into DJude.py:")
    print("HEAD_UP = {}".format(head_up))
    print("HEAD_DOWN = {}".format(head_down))
    print("HEAD_REST = {}".format(head_rest))


print("""Commands:
  <number>   move the head to that angle (0-180)
  + / -      nudge the current angle by 2
  u / d / r  save the current angle as UP / DOWN / REST
  b          test the bob for 8 beats
  bpm <n>    change the test BPM (e.g. bpm 125)
  p          print the settings for DJude.py
  q          quit""")

angle = head_rest
set_head(angle)

while True:
    cmd = input("angle {} > ".format(angle)).strip().lower()
    if cmd == "q":
        break
    elif cmd == "+":
        angle = min(180, angle + 2)
    elif cmd == "-":
        angle = max(0, angle - 2)
    elif cmd == "u":
        head_up = angle
        print("UP =", head_up)
    elif cmd == "d":
        head_down = angle
        print("DOWN =", head_down)
    elif cmd == "r":
        head_rest = angle
        print("REST =", head_rest)
    elif cmd == "b":
        print("Bobbing at", bpm, "BPM between", head_down, "and", head_up)
        bob(8)
        set_head(angle)
        continue
    elif cmd.startswith("bpm "):
        try:
            bpm = int(cmd[4:])
        except ValueError:
            print("Use: bpm 125")
        continue
    elif cmd == "p":
        show_settings()
        continue
    else:
        try:
            angle = max(0, min(180, int(cmd)))
        except ValueError:
            print("Unknown command")
            continue
    set_head(angle)

show_settings()
set_head(head_rest)
