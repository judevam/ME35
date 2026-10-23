from machine import Pin, ADC
import time

# Grove thumb joystick
# NOTE: use ADC1 pins only (32-39). ADC2 pins (like 25) stop working when WiFi is on.
X_PIN = 33
Y_PIN = 32

# Thresholds for 0-4095 readings -- run this file and check the printout, then adjust
LOW = 1000       # below this = pushed one way
HIGH = 2500      # above this = pushed the other way
PRESS = 3800     # the Grove joystick spikes X to max when you press it

REPEAT_MS = 300  # how often up/down repeats while held (for volume)


class Joystick:
    def __init__(self, x_pin=X_PIN, y_pin=Y_PIN):
        self.adc_x = ADC(Pin(x_pin))
        self.adc_y = ADC(Pin(y_pin))
        # full 0-3.3V range (default only reads up to ~1V and everything maxes out)
        self.adc_x.atten(ADC.ATTN_11DB)
        self.adc_y.atten(ADC.ATTN_11DB)
        self.last = None      # last direction we saw
        self.last_time = 0    # when we last sent an event

    def direction(self):
        # what the stick is doing right now: "press", "up", "down", "left", "right" or None
        x = self.adc_x.read()
        y = self.adc_y.read()
        if y > PRESS:
            return "press"
        if y > HIGH:
            return "up"
        if y < LOW:
            return "down"
        if x > HIGH:
            return "right"
        if x < LOW:
            return "left"
        return None

    def get_event(self):
        # call this often in your main loop -- returns an event once per push, or None
        d = self.direction()
        now = time.ticks_ms()
        event = None

        if d != self.last:
            # just moved to a new direction -> fire once
            event = d
            self.last_time = now
        elif d in ("up", "down") and time.ticks_diff(now, self.last_time) > REPEAT_MS:
            # holding up/down -> keep repeating so volume keeps changing
            event = d
            self.last_time = now

        self.last = d
        return event


# test: run this file and move the stick around
if __name__ == "__main__":
    js = Joystick()
    print("Move the stick and press it (Ctrl+C to stop)")
    while True:
        print("X:", js.adc_x.read(), " Y:", js.adc_y.read(), " ->", js.direction())
        time.sleep(0.2)
