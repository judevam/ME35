from machine import PWM, Pin
import time
servo = PWM(Pin(4), freq=50, duty_u16=0)


#Using duty_ns
print("0 Degrees")
servo.duty_ns(500*1000)
time.sleep(1)
print("90 Degrees")
servo.duty_ns(int(1500*1000))
time.sleep(1)
print("180 Degrees")
servo.duty_ns(int(2500*1000))
time.sleep(1)
#Using duty_u16
max = 65,535
min = 0
# 0 = 0.5 ms
# 90 = 1.5 ms
#180 = 2.5 ms

# Frequency = 50Hz
#T = 1/50 = 20ms
#Therefore, 20 ms = 65535
print("0 Degrees")
servo.duty_u16(int(0.5*65535/20))
time.sleep(1)
print("90 Degrees")
servo.duty_u16(int(1.5*65535/20))
time.sleep(1)
print("180 Degrees")
servo.duty_u16(int(2.5*65535/20))
