import servo , time
from machine import Pin
servo1 = Servo(Pin(5)) # change this
servo2 = Servo(Pin(4)) # and this

servo1.write_angle(0)
servo2.write_angle(0)

time.sleep(0.05)

servo1.write_angle(30)
servo2.write_angle(60)