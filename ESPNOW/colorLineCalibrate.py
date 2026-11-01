from machine import Pin, I2C
import time
import json
import veml6040
from colorScanner import normalize_rgb   # same r/w, g/w, b/w as DJude

# Line follower calibration -- two VEML6040 sensors
#   brightness (black line vs white paper) -> a threshold you set by hand below
#   color (red / green / blue / ...)       -> KNN on 4 numbers: the 3 color ratios + brightness
#
# Both VEML6040s have the SAME I2C address (0x10), so each sensor gets its own I2C bus.
#
# 1) Run this file and say "y" to calibrate thresholds. Follow the prompts (white, then black, for
#    each sensor), then copy the two printed thresholds into SETTINGS below.
# 2) Say "y" to train colors. For each label you SWEEP the sensor over the surface while it samples,
#    so the KNN sees a spread of readings (not one spot). Saves line_left.json and line_right.json.
# 3) In lineFollow.py:  sensors = LineSensors()  then  left, right = sensors.on_line()

# ---------------- PINS ----------------
LEFT_SDA, LEFT_SCL = 21, 22      # I2C bus 0
RIGHT_SDA, RIGHT_SCL = 26, 25    # I2C bus 1 -- wired this way around (scan found it here)

# ---------------- SETTINGS ----------------
# raw white-channel reading: BELOW the threshold = black line, ABOVE = white paper
LEFT_THRESHOLD = 252            # TODO: set from the numbers this file prints
RIGHT_THRESHOLD = 305           # TODO: set from the numbers this file prints
THRESHOLD_SAMPLES = 10          # readings averaged for each threshold

# what the KNN can answer. "white", "black" and "edge" mean "no color marker here".
# "edge" = the sensor half on / half off the tape -- the right sensor's normal view while driving
COLOR_LABELS = ["red", "green", "blue", "white", "black", "edge"]
LABEL_HELP = {
    "red": "the RED marker (slide back and forth, including its edges)",
    "green": "the GREEN marker (slide back and forth, including its edges)",
    "blue": "the BLUE marker (slide back and forth, including its edges)",
    "white": "plain WHITE paper (slide around)",
    "black": "the BLACK tape (slide along it, centered on it)",
    "edge": "the tape's EDGE (slide back and forth so it is half on, half off the tape)",
}
SAMPLES_PER_LABEL = 25          # readings per label; more = better but a slower KNN on the ESP32
SAMPLE_DELAY = 0.1              # seconds between readings while sweeping
K = 5
INTEGRATION_TIME = veml6040.IT_40MS    # how long each reading takes: 40, 80, 160 ... ms (shorter = faster)

# The KNN measures distance in 4 numbers. The color ratios only differ by a few hundredths
# between surfaces, so they are multiplied up; brightness (white channel) is divided down so
# black is ~1 and white ~2-3. Raise RATIO_WEIGHT to care more about color, lower it to care
# more about brightness. Retrain after changing either one.
RATIO_WEIGHT = 10
BRIGHTNESS_SCALE = 300


def k_nearest_neighbor(data, point, k=K):
    # same idea as DJude's KNN, written to be fast: the 4 differences are spelled out
    # and only the k closest samples are kept, instead of sorting every sample
    p0, p1, p2, p3 = point
    best = []                                   # (distance, label), at most k, closest first
    for d in data:
        a = p0 - d[0]
        b = p1 - d[1]
        c = p2 - d[2]
        e = p3 - d[3]
        dist = a * a + b * b + c * c + e * e
        if len(best) < k or dist < best[-1][0]:
            best.append((dist, d[4]))
            best.sort()
            if len(best) > k:
                best.pop()
    classes = [d[1] for d in best]
    return max(set(classes), key=classes.count)


class LineSensor:
    def __init__(self, name, i2c_id, sda, scl, threshold):
        i2c = I2C(i2c_id, sda=Pin(sda), scl=Pin(scl), freq=400000)
        self.sensor = veml6040.VEML6040(i2c)
        self.sensor.set_integration_time(INTEGRATION_TIME)
        self.name = name
        self.threshold = threshold
        self.file = "line_" + name + ".json"
        self.color_data = []         # (ratio_r, ratio_g, ratio_b, brightness, label)
        self.rgbw = (0, 0, 0, 0)     # the most recent reading, so one read can be reused
        self.load()

    def update(self):
        # one trip over I2C -- brightness() and color() reuse the result if asked to
        self.rgbw = self.sensor.read_rgbw()

    def brightness(self):
        # raw white channel -- the number your P controller can use too
        self.update()
        return self.rgbw[3]

    def is_black(self):
        return self.brightness() < self.threshold

    def read_features(self):
        # the 4 numbers the KNN uses: color ratios (scaled up) + brightness
        r, g, b, w = self.rgbw
        x, y, z = normalize_rgb(r, g, b, w)
        return (x * RATIO_WEIGHT, y * RATIO_WEIGHT, z * RATIO_WEIGHT, w / BRIGHTNESS_SCALE)

    def average_brightness(self):
        total = 0
        for i in range(THRESHOLD_SAMPLES):
            total += self.brightness()
            time.sleep(0.1)
        return total / THRESHOLD_SAMPLES

    def calibrate_threshold(self):
        # average the brightness over white and over black, threshold = halfway between
        input("Put the " + self.name + " sensor over WHITE paper, press Enter...")
        white = self.average_brightness()
        input("Put the " + self.name + " sensor over the BLACK line, press Enter...")
        black = self.average_brightness()
        threshold = int((white + black) / 2)
        print(self.name, "white:", int(white), "black:", int(black), "-> threshold:", threshold)
        return threshold

    def color(self, fresh=True):
        # one of COLOR_LABELS: "red", "green", "blue", "white", "black" or "edge"
        # fresh=False reuses the reading from the last brightness()/update() call (no extra read)
        if not self.color_data:
            return None
        if fresh:
            self.update()
        return k_nearest_neighbor(self.color_data, self.read_features())

    def train(self):
        self.color_data = []
        print("=== Training", self.name, "sensor ===")
        for label in COLOR_LABELS:
            input("Get ready to sweep the " + self.name + " sensor over " + LABEL_HELP[label]
                  + ". Press Enter, then keep moving...")
            for i in range(SAMPLES_PER_LABEL):
                self.update()
                f = self.read_features()
                self.color_data.append(f + (label,))
                print("  ", label, [round(v, 2) for v in f])
                time.sleep(SAMPLE_DELAY)
        self.save()
        print("Saved", len(self.color_data), "samples to", self.file)

    def save(self):
        with open(self.file, "w") as f:
            json.dump(self.color_data, f)

    def load(self):
        try:
            with open(self.file) as f:
                data = [tuple(d) for d in json.load(f)]
        except OSError:
            print("No", self.file, "yet -- run colorLineCalibrate.py to train")
            return
        if all(len(d) == 5 for d in data):
            self.color_data = data
            print("Loaded", len(data), self.name, "color samples")
        else:
            print(self.file, "is in the old format -- retrain with colorLineCalibrate.py")


class LineSensors:
    # the pair of sensors for the robot
    def __init__(self):
        self.left = LineSensor("left", 0, LEFT_SDA, LEFT_SCL, LEFT_THRESHOLD)
        self.right = LineSensor("right", 1, RIGHT_SDA, RIGHT_SCL, RIGHT_THRESHOLD)

    def on_line(self):
        # (left_on_black, right_on_black)
        return self.left.is_black(), self.right.is_black()

    def train(self):
        self.left.train()
        self.right.train()

    def calibrate_thresholds(self):
        left = self.left.calibrate_threshold()
        right = self.right.calibrate_threshold()
        # the sensors are already running, so use the new values right away
        self.left.threshold = left
        self.right.threshold = right
        print("Copy these into the SETTINGS at the top of colorLineCalibrate.py:")
        print("LEFT_THRESHOLD =", left)
        print("RIGHT_THRESHOLD =", right)


# run this file to set the thresholds, train colors, then test
if __name__ == "__main__":
    sensors = LineSensors()
    if input("Calibrate black/white thresholds? (y/n) ") == "y":
        sensors.calibrate_thresholds()
    if input("Train colors? (y/n) ") == "y":
        sensors.train()
    print("Testing -- move the sensors over white, black, the edge and the markers (Ctrl+C to stop)")
    while True:
        print("L:", sensors.left.brightness(), sensors.left.color(),
              " R:", sensors.right.brightness(), sensors.right.color())
        time.sleep(0.3)
