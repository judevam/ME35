from machine import Pin
import time

# Button test -- run this on the REMOTE board.
# Watch the printout with the buttons untouched, then pressed.
#   0 untouched, 1 pressed  -> active-high button (module with its own resistor)
#   1 untouched, 0 pressed  -> button to ground (what Remote.py assumes)

BTN_A_PIN = 19
BTN_B_PIN = 5

a = Pin(BTN_A_PIN, Pin.IN, Pin.PULL_UP)
b = Pin(BTN_B_PIN, Pin.IN, Pin.PULL_UP)

print("Press and release each button (Ctrl+C to stop)")
while True:
    print("A:", a.value(), " B:", b.value())
    time.sleep(0.3)
