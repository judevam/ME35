# DJude: the DJ desk pet

DJude is a small vinyl-record creature for ME 35. It sits on your desk and controls your Spotify while you work. It's a music snob: it bobs its head to songs while they play, and its turntable spins only when music is on.

## What it does

| Input | Action | DJude's reaction |
|---|---|---|
| Joystick up / down | Volume up / down | Changes the Spotify volume |
| Joystick right / left | Next / previous song | White flash |
| Joystick press | Play / pause | Turntable starts or stops, short beep |
| Scan a colored record (only while paused) | Starts that record's playlist | Head lifts, lights turn the record's color, turntable spins, head bobs |

| Record | Playlist | Head bob |
|---|---|---|
| Yellow | Sunny | 110 BPM |
| Blue | Chill | 85 BPM |
| Green | Dance | 125 BPM |

## Hardware

- Cytron Robo ESP32 running MicroPython
- Grove thumb joystick: X on pin 33, Y on pin 32
- VEML6040 color sensor: SDA on pin 21, SCL on pin 22
- Servo for the head: pin 4
- DC motor for the turntable: pins 12 and 13
- Built-in NeoPixels (pin 15) and buzzer (pin 23)

## Files

| File | What it is |
|---|---|
| `DJude.py` | Main program. Rename it to `main.py`, or add a `main.py` that runs `import DJude`, so it starts at power-up |
| `spotifyAPI.py` | WiFi connection and Spotify Web API calls: play, pause, skip, volume, playlists, now playing |
| `joystick.py` | Turns joystick readings into up, down, left, right and press events |
| `colorScanner.py` | KNN color classifier for the records. Run this file to train it; the colors are saved to `colors.json` |
| `veml6040.py` | Color sensor driver |
| `servoCalibrate.py` | Interactive helper for finding the head-bob servo angles |
| `accelerometer.py` | LIS3DH driver. Gestures aren't used yet |
| `plan.md` | Original concept and design notes |

## Setup

1. Make a `secrets.py` on the ESP32 with `RobotUser` and `RobotPwd` (the WiFi network name and password) and `Client_ID`, `Client_Secret` and `refresh_Token` (Spotify). This file is not committed to the repo.
2. Run `colorScanner.py` and follow the prompts to train the empty sensor and each record.
3. Run `servoCalibrate.py` to tune `HEAD_UP`, `HEAD_DOWN` and `HEAD_REST`, then copy the printed values into `DJude.py`.
4. Start Spotify on a laptop or phone (needs Spotify Premium), then run `DJude.py`.

## Class topics

- **APIs and WiFi:** the ESP32 calls the Spotify Web API directly over HTTPS, using a saved refresh token to get new access tokens.
- **KNN classification:** the color sensor tells the records apart, with an "empty" class so it reacts only when a record is held up.

## Not done yet

- Accelerometer gestures on the headphones: shake "no" to skip, nod "yes" to like
- Head-bob speed that matches each song's real BPM
