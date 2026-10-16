import time
import math
from machine import Pin, PWM
from LEDpath import points

# --- Arm geometry ---
L1 = 5.5          # upper arm length
L2 = 5.5          # forearm length

# --- Servo settings ---
MAX_DUTY = 65535
PERIOD_MS = 20    # 50 Hz -> 20 ms period
MIN_PULSE = 0.5   # ms at 0 degrees
MAX_PULSE = 2.5   # ms at 180 degrees
OFFSET1 = 0       # degrees, adjust so arm 1 stays within 0-180
OFFSET2 = 0       # degrees, adjust so arm 2 stays within 0-180

STEP_DELAY = 0.05  # seconds between points
PAUSE = 0.5        # seconds between shapes
SETTLE = 1.0       # seconds to let the arm reach the start point before drawing

# --- Path scaling ---
SCALE = 5 / 12
X_SHIFT = 12

# --- Hardware ---
led_Y = Pin(18, Pin.OUT)
led_G = Pin(19, Pin.OUT)

pwm1 = PWM(Pin(4), freq=50)
pwm2 = PWM(Pin(5), freq=50)

scaled_points = [((x - X_SHIFT) * SCALE, y * SCALE) for x, y in points]


def angle_to_duty(angle):
    """Convert a servo angle in degrees to a 16-bit duty value."""
    if angle < 0 or angle > 180:
        print("Warning: angle out of range, clamping:", angle)
    pulse = MIN_PULSE + angle / 180 * (MAX_PULSE - MIN_PULSE)
    pulse = max(MIN_PULSE, min(MAX_PULSE, pulse))
    return int(pulse * MAX_DUTY / PERIOD_MS)


def inverse_kinematics(x, y):
    """Return (theta1, theta2) in degrees, or None if the point is unreachable."""
    r = math.sqrt(x * x + y * y)
    if not (abs(L1 - L2) <= r <= L1 + L2):
        return None

    cos_t2 = (x * x + y * y - L1 * L1 - L2 * L2) / (2 * L1 * L2)
    cos_t2 = max(-1.0, min(1.0, cos_t2))
    t2 = math.acos(cos_t2)  # use -math.acos(...) if your drawing comes out mirrored

    t1 = math.atan2(y, x) - math.atan2(L2 * math.sin(t2), L1 + L2 * math.cos(t2))

    return math.degrees(t1), math.degrees(t2)


def go_to_start():
    """Move to the first reachable point with the LEDs off and let the arm settle."""
    led_Y.off()
    led_G.off()
    for x, y in scaled_points:
        angles = inverse_kinematics(x, y)
        if angles is not None:
            theta1, theta2 = angles
            pwm1.duty_u16(angle_to_duty(theta1 + OFFSET1))
            pwm2.duty_u16(angle_to_duty(theta2 + OFFSET2))
            time.sleep(SETTLE)
            return


def star(led):
    """Trace the whole path once with the given LED lit."""
    for x, y in scaled_points:
        angles = inverse_kinematics(x, y)

        if angles is None:
            print("Unreachable point:", x, y)
            led.off()  # "lift the pen" over unreachable points
            continue

        led.on()
        theta1, theta2 = angles
        pwm1.duty_u16(angle_to_duty(theta1 + OFFSET1))
        pwm2.duty_u16(angle_to_duty(theta2 + OFFSET2))
        time.sleep(STEP_DELAY)

    led.off()  # pass finished


try:
    go_to_start()
    star(led_Y)
    go_to_start()
    time.sleep(PAUSE)
    star(led_G)
except KeyboardInterrupt:
    pass
finally:
    led_Y.off()
    led_G.off()
    go_to_start()  # park at the start point so the next run begins in the same place
    pwm1.deinit()
    pwm2.deinit()