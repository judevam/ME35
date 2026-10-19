import network, time, gc
import urequests, ubinascii
import mysecrets
import math
import json
from machine import Pin, PWM

WIFI_SSID = mysecrets.SSID
WIFI_PASS = mysecrets.PWD
ACCESS_KEY = mysecrets.OS_A
SECRET_KEY = mysecrets.OS_S

DID = "8fc929adacefe8180b9633d1"
WID = "41f2efbb9f94fd1a20e944c6"
EID = "d82f45c883dbe54c46cebce4"

CALIBRATE = False  # set True to re-match the arm to Onshape and save new offsets

# --- Servo settings ---
MAX_DUTY = 65535
PERIOD_MS = 20    # 50 Hz -> 20 ms period
MIN_PULSE = 0.5   # ms at 0 degrees
MAX_PULSE = 2.5   # ms at 180 degrees
OFFSETS = [100, 30]       # overwritten by offsets.json if it exists
INVERTS = [True, False]   # set True on the servo that moves the wrong way
RANGES = [None, (-163, 20)]  # Onshape min/max for each joint (None = don't check)

try:
    with open("offsets.json") as f:
        OFFSETS = json.load(f)
except OSError:
    pass

servos = [
    PWM(Pin(4), freq=50),   # servo for "Cylindrical 3"
    PWM(Pin(5), freq=50),   # servo for "Cylindrical 5"
]


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            time.sleep(0.5)
    print("Connected:", wlan.ifconfig())

def onshape_get(path):
    creds = ubinascii.b2a_base64((ACCESS_KEY + ":" + SECRET_KEY).encode()).decode().strip()
    headers = {
        "Authorization": "Basic " + creds,
        "Accept": "application/json;charset=UTF-8;qs=0.09",
    }
    gc.collect()
    r = urequests.get("https://cad.onshape.com" + path, headers=headers)
    if r.status_code != 200:
        print("Error", r.status_code, r.text[:300])
        r.close()
        return None
    data = r.json()
    r.close()
    return data

connect_wifi()

# Document name
doc = onshape_get("/api/v10/documents/" + DID)
if doc:
    print("Document:", doc["name"])

# Assembly contents
WANTED = ["Cylindrical 3", "Cylindrical 5"]

def getAngles(WANTED):
    data = onshape_get("/api/v10/assemblies/d/{}/w/{}/e/{}/matevalues".format(DID, WID, EID))

    rz = {}

    if data:
        for mate in data["mateValues"]:
            name = mate.get("mateName")
            if name in WANTED:
                rz[name] = math.degrees(mate.get("rotationZ", 0))

    return [rz.get(name) for name in WANTED]



def angle_to_duty(angle):
    """Convert a servo angle in degrees to a 16-bit duty value."""
    # wrap into -90..270 so e.g. 350 is treated as -10 (just past 0), not "past 180"
    angle = (angle + 90) % 360 - 90
    # out of range -> stop at whichever end is closer
    angle = max(0, min(180, angle))
    pulse = MIN_PULSE + angle / 180 * (MAX_PULSE - MIN_PULSE)
    pulse = max(MIN_PULSE, min(MAX_PULSE, pulse))
    return int(pulse * MAX_DUTY / PERIOD_MS)


def calibrate():
    """Jog each servo until the real arm matches Onshape, then save the offsets."""
    angles = getAngles(WANTED)
    for i in range(len(servos)):
        print("Onshape", WANTED[i], "=", angles[i])
        print("Type +N / -N to move, s when it matches Onshape")
        a = 90
        servos[i].duty_u16(angle_to_duty(a))
        while True:
            cmd = input("servo {} at {} > ".format(i + 1, a))
            if cmd == "s":
                break
            try:
                a = max(0, min(180, a + float(cmd)))
                servos[i].duty_u16(angle_to_duty(a))
            except ValueError:
                pass
        # undo the same math the main loop uses
        if INVERTS[i]:
            OFFSETS[i] = 180 - a - angles[i]
        else:
            OFFSETS[i] = a - angles[i]
        # check the joint's whole Onshape range fits in the servo's 0-180
        if RANGES[i]:
            ends = [r + OFFSETS[i] for r in RANGES[i]]
            if INVERTS[i]:
                ends = [180 - e for e in ends]
            lo, hi = min(ends), max(ends)
            shift = ((lo + hi) / 2 + 90) % 360 - 90 - (lo + hi) / 2   # same wrap as angle_to_duty
            lo, hi = lo + shift, hi + shift
            print("Joint range maps to servo {:.0f} to {:.0f}".format(lo, hi))
            if lo < 0 or hi > 180:
                print("  Outside 0-180, the arm will stop short at the ends.")
                print("  Ideal center is 90, yours is {:.0f}: re-seat the horn ~{:.0f} deg and recalibrate.".format(
                    (lo + hi) / 2, (lo + hi) / 2 - 90))
    with open("offsets.json", "w") as f:
        json.dump(OFFSETS, f)
    print("Saved offsets:", OFFSETS)


if CALIBRATE:
    calibrate()

while True:
    angles = getAngles(WANTED)
    print("Angles:", angles)

    for servo, angle, offset, invert in zip(servos, angles, OFFSETS, INVERTS):
        if angle is not None:
            a = angle + offset
            if invert:
                a = 180 - a
            servo.duty_u16(angle_to_duty(a))

    time.sleep(0.5)

