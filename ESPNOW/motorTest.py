import time
from machine import PWM

# Motor test -- run this with the wheels OFF the ground.
# Watch which wheel moves and which way, and compare to the printed message.

SPEED = 40       # 0-100
RUN_TIME = 2     # seconds per step


class Motor:
    def __init__(self, m1, m2):
        self.M1 = PWM(m1, freq=500, duty_u16=0)
        self.M2 = PWM(m2, freq=500, duty_u16=0)
        self.stop()

    def stop(self):
        self.M1.duty_u16(0)
        self.M2.duty_u16(0)

    def start(self, direction=0, speed=50):
        if direction:
            self.M1.duty_u16(int(speed * 65535 / 100))
            self.M2.duty_u16(0)
        else:
            self.M1.duty_u16(0)
            self.M2.duty_u16(int(speed * 65535 / 100))


Motor1 = Motor(14, 27)
Motor2 = Motor(12, 13)


def step(message, m1_dir=None, m2_dir=None):
    # run the chosen motors (None = leave that motor off), then stop and pause
    print(message)
    if m1_dir is not None:
        Motor1.start(m1_dir, SPEED)
    if m2_dir is not None:
        Motor2.start(m2_dir, SPEED)
    time.sleep(RUN_TIME)
    Motor1.stop()
    Motor2.stop()
    time.sleep(1)


try:
    step("Motor1 only, direction 0", m1_dir=0)
    step("Motor1 only, direction 1", m1_dir=1)
    step("Motor2 only, direction 0", m2_dir=0)
    step("Motor2 only, direction 1", m2_dir=1)
    # same directions lineFollow.py uses -- both wheels should push the robot FORWARD
    step("Both together, Motor1 (right) dir 1 + Motor2 (left) dir 0 (lineFollow.py's forward)", 1, 0)
    print("Done")
finally:
    Motor1.stop()
    Motor2.stop()
