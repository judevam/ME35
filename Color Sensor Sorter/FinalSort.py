from machine import Pin, I2C, PWM
import time
import math

servo = PWM(Pin(5), freq=50, duty_u16=0)
tilt_servo = PWM(Pin(4), freq=50, duty_u16=0)

# bucket 1-4 -> servo angle, spread evenly across a narrower sweep
BUCKET_ANGLE_MIN = 10
BUCKET_ANGLE_MAX = 100
BUCKET_ANGLES = {
    1: BUCKET_ANGLE_MIN,
    2: BUCKET_ANGLE_MIN + (BUCKET_ANGLE_MAX - BUCKET_ANGLE_MIN) / 3,
    3: BUCKET_ANGLE_MIN + 2 * (BUCKET_ANGLE_MAX - BUCKET_ANGLE_MIN) / 3,
    4: BUCKET_ANGLE_MAX,
}

def tilt_back():
    us = int(500 + (120 / 180) * (2500 - 500))
    tilt_servo.duty_ns(us * 1000)
def tilt_foreward():
    us = int(500 + (60 / 180) * (2500 - 500))
    tilt_servo.duty_ns(us * 1000)

def angle_to_duty_ns(angle):
    us = 500 + (angle / 180) * (2500 - 500)
    return int(us * 1000)

def move_to_bucket(bucket):
    angle = BUCKET_ANGLES.get(bucket)
    if angle is None:
        return
    servo.duty_ns(angle_to_duty_ns(angle))

button_Play = Pin(34, Pin.IN, Pin.PULL_UP)
button_Train = Pin(35, Pin.IN, Pin.PULL_UP)

i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=400000)

print(i2c.scan())
import time


DEBOUNCE_MS = 200
last_press = 0

pressed_flag = False
STATE_PLAY = False
STATE_TRAIN = True

def playButton(p):
    global STATE_PLAY
    global STATE_TRAIN
    STATE_PLAY = True
    STATE_TRAIN = False


def trainButton(p):
    global pressed_flag
    global STATE_TRAIN
    STATE_TRAIN = True
    pressed_flag = True

    
button_Train.irq(trigger=Pin.IRQ_RISING, handler=trainButton)
button_Play.irq(trigger=Pin.IRQ_RISING, handler=playButton)



import veml6040
sensor = veml6040.VEML6040(i2c)

sensor.trigger_measurement()
   
def normalize_rgb(r, g, b, w):
    if w == 0:
        return 0, 0, 0
    return r / w, g / w, b / w

def k_nearest_neighbor(x,y,z, k =1):
    distances = []
    for index, d in enumerate(data):
        dist = math.sqrt((x-d[0])**2+(y-d[1])**2+(z-d[2])**2)
        distances.append([dist,d[3]])
    
    distances.sort()
    distances = distances[:k] #get k distances
    classes = []
    for dist in distances:
        classes.append(dist[1])
    ##print("k classes", classes)
    most_number_of_closest_classes = max(set(classes), key = classes.count)
    ##print("max classes ", most_number_of_closest_classes)
    
    return most_number_of_closest_classes


       
data = []
color = 0
index = 0

while True:
    tilt_back()
    time.sleep(0.3)
    red, green, blue, white = sensor.read_rgbw()
    if(STATE_TRAIN and pressed_flag):
        tilt_back()
        print(red, green, blue, white)
        index = index+1
        if index <= 5:
            color = 1
        elif index >5 and index<10:
            color = 2
        elif index >10 and index<15:
            color = 3
        elif index >15 and index<20:
            color = 4
        else:
            pass

        nr, ng, nb = normalize_rgb(red, green, blue, white)
        data.append((nr, ng, nb, color))
        pressed_flag = False

    if(STATE_PLAY):
        nr, ng, nb = normalize_rgb(red, green, blue, white)
        what_class = k_nearest_neighbor(nr, ng, nb, 3)
        print("Color: " + str(what_class))
        move_to_bucket(what_class)
        time.sleep(0.3)
        tilt_foreward()
        time.sleep(0.3)
        STATE_PLAY = False
    time.sleep(0.1)

