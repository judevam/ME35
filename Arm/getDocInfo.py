import network, time, gc
import urequests, ubinascii
import mysecrets
import math
from machine import Pin, PWM

WIFI_SSID = mysecrets.SSID
WIFI_PASS = mysecrets.PWD
ACCESS_KEY = mysecrets.OS_A
SECRET_KEY = mysecrets.OS_S

DID = "8fc929adacefe8180b9633d1"
WID = "41f2efbb9f94fd1a20e944c6"
EID = "d82f45c883dbe54c46cebce4"

# --- Servo settings ---
MAX_DUTY = 65535
PERIOD_MS = 20    # 50 Hz -> 20 ms period
MIN_PULSE = 0.5   # ms at 0 degrees
MAX_PULSE = 2.5   # ms at 180 degrees
OFFSET1 = 100
OFFSET2 = 30
INVERT1 = True
INVERT2 = False    # set True on the servo that moves the wrong way

OFFSETS = [OFFSET1, OFFSET2]
INVERTS = [INVERT1, INVERT2]

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
    if angle < 0 or angle > 180:
        print("Warning: angle out of range, clamping:", angle)
    pulse = MIN_PULSE + angle / 180 * (MAX_PULSE - MIN_PULSE)
    pulse = max(MIN_PULSE, min(MAX_PULSE, pulse))
    return int(pulse * MAX_DUTY / PERIOD_MS)

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
            
