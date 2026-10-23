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
| Shake head "no" (accelerometer on headphones) | Skip song | Head stops bobbing and drops down, red flash, short "blegh" buzz |
| Nod head "yes" | Happy head bob, sparkle lights |
| Joystick up/down | Volume +/- | Neopixels fill like a volume meter |
| Joystick left/right | Previous / next track | Quick light sweep left/right, head pauses then restarts bobbing at the new song's BPM |
| Joystick press | Play / pause | DC motor turntable stops / starts spinning |
| Scan a colored record on the color sensor (only while paused) | Start that record's playlist (red = dance, blue = chill, green = study, ...) | Head lifts up, lights switch to record color, turntable spins up, head starts bobbing to the beat |

Two distinct responses: shake vs. nod (accelerometer), and different colored records (color sensor).

### Outputs
- **Servo:** head can only move forward/back (motor placement), so it **head-bobs to the beat** of
  the current song while music plays, and holds still (head down) when paused
  - BPM comes from a separate API (Spotify's tempo/audio-features endpoint is deprecated):
    try ReccoBeats (free, no key, looks up by Spotify track ID) or GetSongBPM
  - Fallback if a song isn't found: a default BPM per playlist/record (e.g. dance = 125, chill = 85)
  - Bob timing: one bob per beat = 60 / BPM seconds; use time.ticks_ms() so the bob doesn't block
    the joystick/accelerometer/scanner code
  - Tempo only, not exact beat timing -- it will be on tempo but may be slightly off the downbeat
- **DC motor:** spins the turntable whenever a song is playing, stops when paused
- **Neopixels:** album-art color (song mood), volume meter, gesture feedback flashes
- **Buzzer:** very short reaction sounds only (don't play over the music)

### Turntable + record scanner
- **Turntable:** the DC motor spins a table whenever a song is playing and stops when paused.
  No sensor on it -- it's for show / personality.
- **Scanner:** a separate color sensor on the pet. Each "record" is a disk with a solid color
  (or colored label) -- one color per playlist.
- **Scanning only works at specific times** (when the music is paused / nothing is playing).
  While a song is playing, the scanner is ignored.
- Flow: **paused -> user scans a record -> KNN picks the color -> that playlist starts -> turntable starts spinning.**
- Add an **"empty"** class to the KNN (what the sensor sees with nothing in front of it) so it only
  reacts when a record is actually held up.
- Only accept a color after several matching readings in a row, so waving the record past doesn't
  pick the wrong playlist.
- Keep the sensor-to-record distance fixed (a small cradle/slot to hold the record against) and block
  outside light -- retrain the KNN in the final enclosure.

### Architecture
```
Headphones: accelerometer --(wire, I2C)--> ESP32 in pet
Pet ESP32 (MicroPython) --WiFi HTTPS--> Spotify Web API   (spotifyAPI.py -- working!)
```
- Login (OAuth) was done once by hand; the ESP32 uses the saved refresh token in secrets.py
  to get new access tokens on its own.
- Pet reacts locally right away (lights/servo), then sends the command -- hides WiFi lag.
- Spotify endpoints: next, previous, play/pause, volume, save track, start playlist, currently playing.
- BPM: when the song changes, look up the track ID's tempo (ReccoBeats/GetSongBPM) and set the head-bob speed.
- Song-mood lights: Spotify's audio-features endpoint is deprecated, so lights follow the record's
  color (album-art color would need a laptop helper -- optional stretch).

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
- **KNN color classification** for the playlist records (reuse demo_color_KNN.py / veml6040.py from Color Sensor Sorter)
- **CAD / Onshape** for the pet body, turntable, scanner, and records (digital twin optional: mirror head-bob angle)

### Parts
- ESP32, accelerometer, joystick, color sensor (VEML6040), 1 servo, 1 DC motor (+ driver), Neopixels, buzzer
- Colored records (one per playlist, 3D-printed or cardboard disks), turntable platter, scanner cradle for the color sensor, 3D-printed / cardboard body, headphone clip for the accelerometer

### Build order (de-risk first)
1. ~~Spotify auth + API calls from the ESP32~~ (done -- spotifyAPI.py)
2. Joystick -> volume / prev / next / play-pause
3. Scanner: color sensor + records + KNN (incl. "empty") -> playlists (only while paused); turntable spins while playing
4. Accelerometer gestures (log raw data while nodding/shaking, tune thresholds)
5. Personality: head-bob to BPM (test the BPM API first), turntable, lights, sounds
6. Body CAD, assembly, video, portfolio

### Open questions
- Which accelerometer module do we have -- accel only, or an IMU with a gyro? (A gyro makes shake detection trivial.)
- Wired vs. wireless headphone sensor?
- Name: Vinny / Bop / DJ Tempo?
