#Examples of dictionaries
#data = {"key":"Hello"} 
#print(data["key"])

#data1 = {"key1" : "world", "key2" : "value2"}
#print(data1["key1"])

#data2 = [{"key1" : "I'm alive", "key2" : "B"}, {"key1" : "BOOM", "key2" : "D"}]
#print(data2[1]["key1"])

robot = {
    "name": "Dragonfly",
    "position": {
        "x": 3,
        "y": 10
    }
}

sensor = {
    "type": "distance",
    "value": 35
}

print(sensor.get("value"))
print(sensor.get("unit", "cm"))

print(robot["name"])
print(robot["position"]["x"])
print(robot["position"]["y"])

import json

json_text = """
{
    "robot": "ESP32 Rover",
    "speed": 45,
    "active": true
}
"""

data = json.loads(json_text)

print(data["robot"])
print(data["speed"])
print(data["active"])


import json

json_text = """
{
    "location": {
        "latitude": 42.36,
        "longitude": -71.06
    },
    "timestamp": 1789500000
}
"""

data = json.loads(json_text)

latitude = data["location"]["latitude"]
longitude = data["location"]["longitude"]

print("Latitude:", latitude)
print("Longitude:", longitude)

json_text = """
{
    "readings": [
        {"sensor": "temperature", "value": 23.5},
        {"sensor": "distance", "value": 42},
        {"sensor": "light", "value": 680}
    ]
}
"""

data = json.loads(json_text)

for reading in data["readings"]:
    print(reading["sensor"], reading["value"])