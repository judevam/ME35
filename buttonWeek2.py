from machine import Pin
from time import ticks_ms, ticks_diff, sleep_ms
import neopixel

lights = neopixel.NeoPixel(Pin(15), 2)  # Pin 15, 2 LEDs

btn = Pin(34, Pin.IN, Pin.PULL_UP)
DEBOUNCE_MS = 200
last_press = 0

# Colors to cycle through on each press
COLORS = [
    (255, 0, 0),    # red
    (0, 255, 0),    # green
    (0, 0, 255),    # blue
    (255, 255, 0),  # yellow
    (0, 0, 0),      # off
]
color_index = 0
button_pressed = False  # flag set in ISR, handled in main loop

def button_handler(pin):
    global last_press, button_pressed
    now = ticks_ms()
    if ticks_diff(now, last_press) > DEBOUNCE_MS and pin.value() == 0:
        last_press = now
        button_pressed = True  # keep ISR short — no printing/sleeping here

btn.irq(trigger=Pin.IRQ_FALLING, handler=button_handler)

while True:
    if button_pressed:
        button_pressed = False
        color_index = (color_index + 1) % len(COLORS)
        r, g, b = COLORS[color_index]
        lights[0] = (r, g, b)
        lights[1] = (b, g, r)  # mirror the color on the second LED
        lights.write()
        print("Button pressed! Color:", COLORS[color_index])