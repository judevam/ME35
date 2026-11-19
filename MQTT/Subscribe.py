import network
import time
from umqtt.simple import MQTTClient
import ssl
import secrets

# Wi-Fi credentials
SSID = secrets.SSID
PASSWORD = secrets.PWD

# MQTT settings
MQTT_BROKER = secrets.mqtt_url 
MQTT_PORT = secrets.port
#MQTT_USERNAME = secrets.mqtt_username 
#MQTT_PASSWORD = secrets.mqtt_password 
CLIENT_ID = "esp32_client"
TOPIC_PUB = "ME35/play"
TOPIC_SUB = "ME35/play"

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
        return True
    else:
        print("WiFi connection failed!")
        return False


def sub_cb(topic, msg):
    print(f"Received message on topic '{topic.decode()}' : '{msg.decode()}'")

def mqtt_connect():
    try:
        client = MQTTClient(
            client_id=CLIENT_ID,
            server=MQTT_BROKER,
            port=MQTT_PORT,
            #user=MQTT_USERNAME,
            #password=MQTT_PASSWORD,
            #ssl=True,  # Enable SSL
            ssl_params={'server_hostname': MQTT_BROKER}  # Important for certificate validation
        )
        client.set_callback(sub_cb)
        client.connect()
        client.subscribe(TOPIC_SUB) # change this to the topic you want to subscribe
        print("MQTT Connected successfully!")
        return client
    except OSError as e:
        print(f"MQTT Connection failed: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

if connect_wifi():
    client = mqtt_connect()
    if client:
        while True:
            try:
                client.check_msg()
                time.sleep(1)
            except Exception as e:
                print(f"Checking message failed: {e}")

    