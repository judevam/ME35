# Midterm -- ME 35 Desktop Pet Toy

## Requirements:
1. It has to have a name and a clear personality.
2. It has to help the owner in some meaningful way.
3. It has to respond in at least two distinct ways depending on what the user does (for example, tilting left vs. shaking, or red vs. yellow on the color sensor) or a combination of both.

## Constraints:

1. You will use at least one of the two new sensors in your product.
2. You will use at least one of the topics we have discussed in the class - you will include a section in the end of your portfolio entry to justify this.
3. You will not use more than one servo and one DC motor. You can use external buttons, LEDs, etc.

## Points:
1. Constraints (10 pts): uses at least one new sensor, uses a class topic, stays within motor limits.
2. Requirements (up to 15 pts): 2 pts for one, 7 pts for two, 15 pts for all three.
3. Portfolio (5 pts): Documents sources and libraries used, and justifies the class topic, pictures, videos, CAD files etc

## Sensors/hardware to use:
1. accelerometer
2. joystick
3. color sensor
4. dc motor
5. servo motor
6. Neopixel lights
7. Built in buzzers


# Jude's brainstorming


## Concept: the DJ pet
A little vinyl-record creature that sits on my desk and controls my Spotify (Premium) while I work.
Personality: a music snob with opinions -- vibes to songs it likes, acts disgusted when I skip.

**How it helps:** hands-free music control while studying -- skip, like, volume, and switch
playlists without leaving what I'm working on. Lights show the mood of the current song.

### Inputs -> actions -> reactions
| Input | Action | Pet reaction |
|---|---|---|
| Shake head "no" (accelerometer on headphones) | Skip song | Servo head turns away, red flash, short "blegh" buzz |
| Nod head "yes" | Like song (save to Liked Songs) | Happy head bob, sparkle lights |
| Joystick up/down | Volume +/- | Neopixels fill like a volume meter |
| Joystick left/right | Previous / next track | Head tilt toward that side |
| Joystick press | Play / pause | DC motor turntable stops / starts spinning |
| Color card on color sensor | Start playlist (red = hype, blue = chill, green = study, ...) | Head tilts curiously, lights switch to card color, record spins up |

Two distinct responses: shake vs. nod (accelerometer), and different color cards (color sensor).

### Outputs
- **Servo:** head (bob, turn away, tilt)
- **DC motor:** spinning record/turntable on its back while music plays
- **Neopixels:** album-art color (song mood), volume meter, gesture feedback flashes
- **Buzzer:** very short reaction sounds only (don't play over the music)

### Architecture
```
Headphones: accelerometer --(wire, I2C)--> ESP32 in pet
Pet ESP32 (MicroPython) --WiFi HTTP--> Laptop Python server (spotipy) --> Spotify Web API
                        <-- song info + album-art dominant color --
```
- Laptop server handles Spotify OAuth (too painful on the ESP32) and computes the album cover's
  dominant color (Spotify's audio-features/mood endpoint is deprecated for new apps).
- Pet reacts locally right away (lights/servo), then sends the command -- hides WiFi lag.
- Spotify endpoints: next, previous, play/pause, volume, save track, start playlist, currently playing.

### Gesture detection notes
- **Nod** (pitch) is easy: gravity shifts between axes -> look for down-then-up past a threshold.
- **Shake** is harder: turning your head side to side doesn't change gravity, so the accelerometer
  only sees the swing acceleration. Mount it on the ear cup (away from the rotation axis) and look
  for 2-3 alternating sign spikes on the front/back axis within ~1 s.
  - Fallback if unreliable: head *tilt* left/right (ear toward shoulder), which does change gravity.
- Require threshold + repeated reversals + ~1.5 s cooldown so normal head movement/walking doesn't trigger.
- Cable from headphones to pet: keep it short/flexible (I2C is fine at ~1 m at slow speed).
  Alternative: a second ESP32 on the headphones sending gestures over WiFi/ESP-NOW (no cable).

### Class topics to justify
- **APIs / WiFi client-server** (Spotify Web API + laptop bridge, builds on Clock project)
- **KNN color classification** for the playlist cards (reuse demo_color_KNN.py / veml6040.py from Color Sensor Sorter)
- **CAD / Onshape** for the pet body and turntable (digital twin optional: mirror head angle)

### Parts
- ESP32, accelerometer, joystick, color sensor (VEML6040), 1 servo, 1 DC motor (+ driver), Neopixels, buzzer
- Colored cards (one per playlist), 3D-printed / cardboard body, headphone clip for the accelerometer

### Build order (de-risk first)
1. Laptop server: spotipy auth + endpoints working from a test script
2. ESP32 -> server over WiFi (reuse Clock code): joystick volume/skip
3. Color cards + KNN -> playlists
4. Accelerometer gestures (log raw data while nodding/shaking, tune thresholds)
5. Personality: servo animations, turntable, album-color lights, sounds
6. Body CAD, assembly, video, portfolio

### Open questions
- Which accelerometer module do we have -- accel only, or an IMU with a gyro? (A gyro makes shake detection trivial.)
- Wired vs. wireless headphone sensor?
- Name: Vinny / Bop / DJ Tempo?
