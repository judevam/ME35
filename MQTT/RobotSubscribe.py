import network
import time
from umqtt.simple import MQTTClient
import secrets
from machine import Pin, PWM
import neopixel
import json

# Wi-Fi credentials
SSID = secrets.RobotUser
PASSWORD = secrets.RobotPwd

# MQTT settings
print(secrets.mqtt_url)
print(secrets.port)
MQTT_BROKER = secrets.mqtt_url 
MQTT_PORT = secrets.port
#MQTT_USERNAME = secrets.mqtt_username 
#MQTT_PASSWORD = secrets.mqtt_password 
CLIENT_ID = "esp32_robot_Jude"
TOPIC_SUB = ["ME35/speed","ME35/direction","ME35/led/0","ME35/led/1"]

speed = 20
direction = "stop"                        # last direction command received
NEOPIXEL_PIN = 15 
NUM_PIXELS = 2
pixels = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)

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


right_motor = Motor(14, 27)               
left_motor = Motor(13, 12)              


def drive(l, r):                          # -100..100 each, positive = forward
    right_motor.run(r)
    left_motor.run(l)


drive(0, 0)                               # make sure motors are off at startup
pixels.fill((0, 0, 0))                    # make sure pixels are off at startup
pixels.write()

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(SSID, PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
        
    if wlan.isconnected():
        print("WiFi Connected! IP:", wlan.ifconfig()[0])
        blink_green()
        return True
    else:
        print("WiFi connection failed!")
        return False
    
def set_pixel(index, msg):
    try:
        d = json.loads(msg)
        r = max(0, min(255, int(d.get("r", 0))))
        g = max(0, min(255, int(d.get("g", 0))))
        b = max(0, min(255, int(d.get("b", 0))))
        print(r,g,b)
        pixels[index] = (r, g, b)
        pixels.write()
    except Exception as e:
        print("Bad LED message:", msg, e)

def apply_direction():
    # Drive according to the current direction and speed
    if direction == "left":
        drive(-speed, speed)
    elif direction == "right":
        drive(speed, -speed)
    elif direction == "forward":
        drive(speed, speed)
    elif direction == "backward":
        drive(-speed, -speed)
    else:
        drive(0, 0)                       # "stop" or anything unknown

def sub_cb(topic, msg):
    global speed, direction
    topic = topic.decode()
    msg = msg.decode()
    print(f"Received message on topic '{topic}' : '{msg}'")
    if topic == "ME35/speed":
        try:
            speed = max(0, min(100, int(msg)))
            if direction != "stop":
                apply_direction()         # robot is moving: update speed right away
        except ValueError:
            print("Bad speed value:", msg)
    elif topic == "ME35/direction":
        direction = msg
        apply_direction()
    elif topic == "ME35/led/0":
        set_pixel(0,msg)
    elif topic == "ME35/led/1":
        set_pixel(1,msg)

def mqtt_connect():
    try:
        client = MQTTClient(
            client_id=CLIENT_ID,
            server=MQTT_BROKER,
            port=MQTT_PORT,
            keepalive=30,
            #user=MQTT_USERNAME,
            #password=MQTT_PASSWORD,
            #ssl=True,  # Enable SSL
            #ssl_params={'server_hostname': MQTT_BROKER}  # Important for certificate validation
        )
        client.set_callback(sub_cb)
        client.connect()
        for topic in TOPIC_SUB:
            client.subscribe(topic) # change this to the topic you want to subscribe
        print("MQTT Connected successfully!")
        blink_green()
        return client
    except OSError as e:
        print(f"MQTT Connection failed: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def blink_red(times=5):
    for _ in range(times):                # each blink is 0.6 s, so 5 blinks = 3 s
        pixels.fill((50, 0, 0))           # both pixels red (kept dim)
        pixels.write()
        time.sleep(0.3)
        pixels.fill((0, 0, 0))
        pixels.write()
        time.sleep(0.3)


def blink_green(times=3):
    for _ in range(times):                # each blink is 0.6 s, so 5 blinks = 3 s
        pixels.fill((0, 50, 0))           # both pixels red (kept dim)
        pixels.write()
        time.sleep(0.3)
        pixels.fill((0, 0, 0))
        pixels.write()
        time.sleep(0.3)


client = None
last_ping = time.time()

while True:
    if client is None:
        # Not connected: motors off, blink red, then try to reconnect
        drive(0, 0)
        blink_red()
        if connect_wifi():
            client = mqtt_connect()
            if client:
                pixels.fill((0, 0, 0))    # connected: turn pixels off
                pixels.write()
                last_ping = time.time()
        continue

    try:
        client.check_msg()
        if time.time() - last_ping > 10:  # keep the connection alive and detect drops
            client.ping()
            last_ping = time.time()
        time.sleep(0.1)
    except Exception as e:
        print(f"Connection lost: {e}")
        drive(0, 0)
        direction = "stop"                # so a later speed message doesn't restart the motors
        client = None

    