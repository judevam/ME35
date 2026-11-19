from machine import Pin, ADC, PWM
import time

# Joystick on GPIO36 (X) and GPIO39 (Y) -- both are input-only ADC1 pins, fine for analog
# Servo signal on GPIO4
adc_x = ADC(Pin(36))
adc_y = ADC(Pin(39))
adc_x.atten(ADC.ATTN_11DB)   # full 0-3.3V range
adc_y.atten(ADC.ATTN_11DB)

servo = PWM(Pin(4), freq=50)


def set_angle(angle):
    # 0-180 degrees -> 0.5ms-2.5ms pulse out of a 20ms period
    angle = max(0, min(180, angle))
    pulse_us = 500 + (angle / 180) * 2000
    servo.duty_u16(int(pulse_us / 20000 * 65535))


while True:
    x = adc_x.read()   # 0-4095
    y = adc_y.read()
    angle = (x - 800) * 180 // (2900 - 800)   # X range 800-2900 -> 0-180 deg (clamped in set_angle)
    set_angle(angle)
    print("X:", x, "Y:", y, "angle:", angle)
    time.sleep(0.05)
