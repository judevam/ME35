import time
from machine import Pin, PWM

# Melody test -- cycles through the three marker melodies forever (Ctrl+C to stop).
# The notes and the player below are a COPY of the ones in lineFollow.py, so if you change a
# melody there, change it here too (or the other way round).

BUZZER_PIN = 23          # the Robo ESP32's built-in buzzer
BEEP_DUTY = 2000         # buzzer volume
PAUSE_MS = 1000          # silence between melodies

buzzer = PWM(Pin(BUZZER_PIN), freq=1000, duty_u16=0)

# ---- notes and player (same as lineFollow.py) ----
C4, D4, E4, F4, G4, A4, B4 = 262, 294, 330, 349, 392, 440, 494
C5, D5, E5, F5, G5, A5, B5 = 523, 587, 659, 698, 784, 880, 988
C6 = 1047
REST = 0
NOTE_GAP = 25            # ms of silence after each note so repeated notes are heard separately

melody = []              # the steps being played: (freq, ms)
melody_i = 0
melody_next = 0          # when to move on to the next step

def play_melody(notes, beat_ms):
    global melody, melody_i, melody_next
    steps = []
    for freq, beats in notes:
        ms = int(beats * beat_ms)
        if freq:
            steps.append((freq, ms - NOTE_GAP))
            steps.append((0, NOTE_GAP))
        else:
            steps.append((0, ms))
    melody = steps
    melody_i = 0
    melody_next = time.ticks_ms()
    buzzer.duty_u16(0)

def update_melody(now):
    global melody, melody_i, melody_next
    if not melody or time.ticks_diff(now, melody_next) < 0:
        return
    if melody_i >= len(melody):
        buzzer.duty_u16(0)
        melody = []
        return
    freq, ms = melody[melody_i]
    melody_i += 1
    if freq:
        buzzer.freq(freq)
        buzzer.duty_u16(BEEP_DUTY)
    else:
        buzzer.duty_u16(0)
    melody_next = time.ticks_add(now, ms)

# ---- melodies (same as lineFollow.py) ----
LA_CUCARACHA = [
    (C4, 1), (C4, 1), (C4, 1), (F4, 3), (A4, 2), (REST, 1),
    (C4, 1), (C4, 1), (C4, 1), (F4, 3), (A4, 2), (REST, 1),
    (F4, 1), (F4, 1), (E4, 1), (E4, 1), (D4, 1), (D4, 1), (C4, 4),
]

WILLIAM_TELL = [
    (G4, 1), (G4, 1), (G4, 2), (G4, 1), (G4, 1), (G4, 2),
    (C5, 1), (C5, 1), (C5, 2), (C5, 1), (C5, 1), (E5, 2),
    (G5, 1), (E5, 1), (C5, 3),
]

VALKYRIES = [
    (E5, 2), (E5, 1), (E5, 1), (A5, 3), (REST, 1),
    (E5, 2), (E5, 1), (E5, 1), (A5, 3), (REST, 1),
    (C6, 2), (A5, 1), (E5, 1), (A5, 4),
]

# name, notes, ms per beat -- the same tempos lineFollow.py uses (red, blue, green)
SONGS = [
    ("red: La Cucaracha", LA_CUCARACHA, 120),
    ("blue: William Tell", WILLIAM_TELL, 90),
    ("green: Ride of the Valkyries", VALKYRIES, 110),
]

try:
    while True:
        for name, notes, beat_ms in SONGS:
            print("Playing", name)
            play_melody(notes, beat_ms)
            while melody:                       # wait for it to finish
                update_melody(time.ticks_ms())
                time.sleep_ms(1)
            time.sleep_ms(PAUSE_MS)
finally:
    buzzer.duty_u16(0)                          # never leave the buzzer on
