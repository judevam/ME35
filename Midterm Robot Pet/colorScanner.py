from machine import Pin, I2C
import time
import math
import json
import veml6040

# Record scanner -- VEML6040 color sensor + KNN (from the Color Sensor Sorter)
#
# 1) Train once: run this file, follow the prompts in the shell. Saves colors.json on the ESP32.
# 2) In the main program: scanner = ColorScanner(), then call scanner.scan() in the loop.

# one entry per record + "empty" (what the sensor sees with nothing in front of it)
LABELS = ["empty", "yellow", "blue", "green"]

# which playlist each record starts -- copy the ID from Spotify: playlist -> Share -> Copy link
PLAYLISTS = {
    "yellow":   "spotify:playlist:3ok1l9Nwnlp69cvqVSUOT5",   # sunny
    "blue":  "spotify:playlist:4VCq8Q3RwOhogaCX72qVsW",   # jazz
    "green": "spotify:playlist:3bwVvRCjxaif9uXtvMfnw2",   # dance
}

SAMPLES_PER_LABEL = 10   # training readings per record
K = 3                    # neighbors to vote
STABLE_COUNT = 3         # same color this many reads in a row before we accept it
DATA_FILE = "colors.json"


def normalize_rgb(r, g, b, w):
    # divide by white so brightness/distance matters less, only the color
    if w == 0:
        return 0, 0, 0
    return r / w, g / w, b / w


def k_nearest_neighbor(data, x, y, z, k=K):
    distances = []
    for d in data:
        dist = math.sqrt((x - d[0]) ** 2 + (y - d[1]) ** 2 + (z - d[2]) ** 2)
        distances.append([dist, d[3]])
    distances.sort()
    classes = [d[1] for d in distances[:k]]
    return max(set(classes), key=classes.count)


class ColorScanner:
    def __init__(self, sda=21, scl=22):
        i2c = I2C(0, sda=Pin(sda), scl=Pin(scl), freq=400000)
        self.sensor = veml6040.VEML6040(i2c)
        # shorter than the driver's default 1280 ms so scans feel quick
        self.sensor.set_integration_time(veml6040.IT_160MS)
        self.data = []
        self.last = None
        self.count = 0
        self.load()

    def read(self):
        r, g, b, w = self.sensor.read_rgbw()
        return normalize_rgb(r, g, b, w)

    def classify(self):
        # what color the sensor sees right now
        if not self.data:
            return None
        x, y, z = self.read()
        return k_nearest_neighbor(self.data, x, y, z)

    def scan(self):
        # call in the main loop -- returns a record color ONCE when a record is held up,
        # otherwise None. Ignores "empty".
        color = self.classify()
        if color == self.last:
            self.count += 1
        else:
            self.last = color
            self.count = 1
        if self.count == STABLE_COUNT and color != "empty":
            return color
        return None

    def train(self):
        self.data = []
        for label in LABELS:
            if label == "empty":
                input("Hold NOTHING in front of the sensor, press Enter...")
            else:
                input("Hold the " + label + " record on the sensor, press Enter...")
            for i in range(SAMPLES_PER_LABEL):
                x, y, z = self.read()
                self.data.append((x, y, z, label))
                print("  ", label, round(x, 3), round(y, 3), round(z, 3))
                time.sleep(0.2)
        self.save()
        print("Saved", len(self.data), "samples to", DATA_FILE)

    def save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f)

    def load(self):
        try:
            with open(DATA_FILE) as f:
                self.data = [tuple(d) for d in json.load(f)]
            print("Loaded", len(self.data), "color samples")
        except OSError:
            print("No", DATA_FILE, "yet -- run colorScanner.py to train")


# run this file to train, then test
if __name__ == "__main__":
    scanner = ColorScanner()
    if input("Train new colors? (y/n) ") == "y":
        scanner.train()
    print("Testing -- hold records up to the sensor (Ctrl+C to stop)")
    while True:
        color = scanner.scan()
        if color:
            print("Scanned:", color, "->", PLAYLISTS.get(color))
        time.sleep(0.2)
