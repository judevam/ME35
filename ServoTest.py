import time
from machine import Pin, PWM

# ---------------------------------------------------------------------------
# Standalone servo calibration rig - no wifi, no time sync, no API calls.
# Copy calibrated values (SERVO_*_MIN_NS/MAX_NS/OFFSET_DEG) into PremAPI.py
# once you're happy with them here.
# ---------------------------------------------------------------------------
PIN_SERVO_HOUR = 4        # servo driving the hour hand, geared 2:1 for a 360-degree sweep
PIN_SERVO_MINUTE = 5      # servo driving the minute hand, geared 2:1 for a 360-degree sweep

# Pulse width (ns) at each end of the servo's own travel (0-180 degrees on
# the servo itself), which the 2:1 gearing turns into a full 0-360 degree
# sweep of the clock hand. Swap min/max per servo if one runs backwards
# relative to the other.
SERVO_HOUR_MIN_NS = 500_000
SERVO_HOUR_MAX_NS = 2_500_000
SERVO_MINUTE_MIN_NS = 500_000
SERVO_MINUTE_MAX_NS = 2_500_000

# Calibration: degrees added to the commanded angle to correct for how the
# horn/gear landed when it was mounted. See calibrate_servos() below.
SERVO_HOUR_OFFSET_DEG = 40.0
SERVO_MINUTE_OFFSET_DEG = 50.0

# Calibration: multiplier on the commanded angle to correct a proportional
# under/over-rotation (e.g. the real gear ratio isn't exactly 2:1). Found by
# jogging to a known angle and comparing to the measured result:
#   scale = commanded_degrees / actual_measured_degrees
# e.g. jogged hour to 270, it actually landed at 250 -> 270/250 = 1.08.
SERVO_HOUR_SCALE = 1.08
SERVO_MINUTE_SCALE = 1.0

STEP_SECONDS = 1.5   # pause between each position during test_clock_hands()
TEAM_STEP_SECONDS = 2.0   # pause on each team during test_team_positions()

# Premier League clubs in physical clockwise order around the dial, starting
# from the marker nearest 12 o'clock. Must match PremAPI.py exactly.
PREMIER_LEAGUE_TEAMS = [
    "Manchester City", "Arsenal", "Hull City", "Chelsea", "Brentford",
    "Liverpool", "Newcastle United", "Everton", "Leeds United", "Brighton & Hove Albion",
    "Manchester United", "Sunderland", "Crystal Palace", "Ipswich Town", "AFC Bournemouth",
    "Nottingham Forest", "Tottenham Hotspur", "Aston Villa", "Fulham", "Coventry City",
]

# Calibration: degrees added to every team's dial position, to correct for
# how the printed face sits relative to true 12 o'clock. Found by pointing at
# team index 0 (Manchester City), measuring how far off true 12 it sits and
# which way, then setting this value the same way as the servo offsets.
TEAM_DIAL_OFFSET_DEG = 0.0

# ---------------------------------------------------------------------------
# Servos
# ---------------------------------------------------------------------------
hour_servo = PWM(Pin(PIN_SERVO_HOUR), freq=50, duty_u16=0)
minute_servo = PWM(Pin(PIN_SERVO_MINUTE), freq=50, duty_u16=0)

boot_ms = time.ticks_ms()


def log(msg):
    elapsed = time.ticks_diff(time.ticks_ms(), boot_ms) / 1000
    print("[t+{:6.1f}s] {}".format(elapsed, msg))


def set_position(servo, fraction, min_ns, max_ns, offset_deg, scale, label):
    """Point a geared, 360-degree servo to `fraction` (0.0-1.0) of a full turn,
    corrected by `scale` (proportional under/over-rotation) then shifted by
    `offset_deg` (to correct for how it was mounted)."""
    adjusted = (fraction * scale + offset_deg / 360.0) % 1.0
    pulse_ns = int(min_ns + adjusted * (max_ns - min_ns))
    servo.duty_ns(pulse_ns)
    log(f"{label} servo -> {adjusted * 360:.1f} deg (target {fraction * 360:.1f} deg, scale {scale:.3f}, offset {offset_deg:+.1f}, pulse {pulse_ns} ns)")


def set_hour_position(fraction):
    set_position(hour_servo, fraction, SERVO_HOUR_MIN_NS, SERVO_HOUR_MAX_NS, SERVO_HOUR_OFFSET_DEG, SERVO_HOUR_SCALE, label="Hour")


def set_minute_position(fraction):
    set_position(minute_servo, fraction, SERVO_MINUTE_MIN_NS, SERVO_MINUTE_MAX_NS, SERVO_MINUTE_OFFSET_DEG, SERVO_MINUTE_SCALE, label="Minute")


# ---------------------------------------------------------------------------
# Test routines
# ---------------------------------------------------------------------------
def calibrate_servos():
    """Park both hands at fraction 0.0 (should be true 12 o'clock) and hold,
    so you can measure how far off each one physically sits.

    Measure each hand against the 12 o'clock mark: how many degrees off, and
    which way (clockwise/counter-clockwise). Update SERVO_HOUR_OFFSET_DEG /
    SERVO_MINUTE_OFFSET_DEG above with the correction, then run this again to
    confirm. Ctrl+C out of this once you've measured.
    """
    log("CALIBRATION: parking hour + minute hands at fraction 0.0 (true 12 o'clock)")
    set_hour_position(0.0)
    set_minute_position(0.0)
    log("Hands parked - measure the offset on each, then Ctrl+C when done")
    while True:
        time.sleep(1)


def probe_servo_range(servo, label, start_ns=300_000, end_ns=2_700_000, step_ns=100_000, step_seconds=1.0):
    """Sweep raw pulse widths on one servo, ignoring fraction/offset math, so
    you can find where it actually stalls/buzzes at each end.

    Watch/listen for the pulse width where it stops moving cleanly (grinds,
    buzzes, or the hand just stops). Set SERVO_*_MIN_NS/MAX_NS above a little
    inside those limits, so the fraction math never asks for a pulse the
    servo can't actually reach.
    """
    ns = start_ns
    while ns <= end_ns:
        servo.duty_ns(ns)
        log(f"{label} raw pulse -> {ns} ns")
        time.sleep(step_seconds)
        ns += step_ns


def test_clock_hands():
    """Sweep each hand through a few known positions end-to-end.

    Uses a continuously increasing fraction (0.0 -> 1.0) rather than wrapping
    back to 0.0 for the final "12"/"60" mark. Fraction 0.0 and 1.0 land on the
    same visual spot but are different physical servo angles (0 deg vs 180
    deg, since it's geared 2:1) - commanding 0.0 from mid-swing would yank
    the servo all the way backward instead of finishing the turn forward.
    """
    log("Sweeping hour hand through 12, 3, 6, 9, 12")
    for label, fraction in (("12", 0.0), ("3", 0.25), ("6", 0.5), ("9", 0.75), ("12", 1.0)):
        log(f"Hour hand target: {label} o'clock")
        set_hour_position(fraction)
        time.sleep(STEP_SECONDS)

    log("Sweeping minute hand through 15, 30, 45, 60")
    for label, fraction in (("15", 0.25), ("30", 0.5), ("45", 0.75), ("60", 1.0)):
        log(f"Minute hand target: {label}")
        set_minute_position(fraction)
        time.sleep(STEP_SECONDS)

    log("Test complete")


def team_fraction(team_name):
    """Map a team name to its 0.0-1.0 position around the dial (physical
    clockwise order, see PREMIER_LEAGUE_TEAMS). Divides by len(teams), not
    len(teams) - 1, since this is a circular dial where fraction 0.0 and 1.0
    are the same physical spot. TEAM_DIAL_OFFSET_DEG shifts the whole ring to
    match where it actually sits on the face."""
    target = team_name.lower()
    for i, name in enumerate(PREMIER_LEAGUE_TEAMS):
        if name.lower() == target:
            return (i / len(PREMIER_LEAGUE_TEAMS) + TEAM_DIAL_OFFSET_DEG / 360.0) % 1.0
    raise ValueError(f"Unknown team: {team_name!r}. Options: {PREMIER_LEAGUE_TEAMS}")


def test_team_positions(servo_name="both"):
    """Step both hands through every team position in order, so you can check
    each one lands on the right marker on the physical dial.

    servo_name: "hour", "minute", or "both" (default - useful since both
    hands share the same 20 team markers on one face).
    """
    log(f"Sweeping {len(PREMIER_LEAGUE_TEAMS)} team positions ({servo_name})")
    for i, team in enumerate(PREMIER_LEAGUE_TEAMS):
        fraction = (i / len(PREMIER_LEAGUE_TEAMS) + TEAM_DIAL_OFFSET_DEG / 360.0) % 1.0
        log(f"Team #{i}: {team} (target {fraction * 360:.1f} deg)")
        if servo_name in ("hour", "both"):
            set_hour_position(fraction)
        if servo_name in ("minute", "both"):
            set_minute_position(fraction)
        time.sleep(TEAM_STEP_SECONDS)
    log("Team position sweep complete")


def point_at_team(servo_name, team_name):
    """Point one hand at a single named team, for checking/fine-tuning one
    marker at a time instead of sweeping through all 20."""
    fraction = team_fraction(team_name)
    if servo_name == "hour":
        set_hour_position(fraction)
    else:
        set_minute_position(fraction)


def jog(servo_name, degrees):
    """Nudge one hand to an exact angle (0-360) for fine-tuning by hand."""
    servo = hour_servo if servo_name == "hour" else minute_servo
    offset = SERVO_HOUR_OFFSET_DEG if servo_name == "hour" else SERVO_MINUTE_OFFSET_DEG
    scale = SERVO_HOUR_SCALE if servo_name == "hour" else SERVO_MINUTE_SCALE
    min_ns = SERVO_HOUR_MIN_NS if servo_name == "hour" else SERVO_MINUTE_MIN_NS
    max_ns = SERVO_HOUR_MAX_NS if servo_name == "hour" else SERVO_MINUTE_MAX_NS
    label = "Hour" if servo_name == "hour" else "Minute"
    set_position(servo, (degrees % 360) / 360.0, min_ns, max_ns, offset, scale, label)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
MENU = """
Servo test menu:
  1) calibrate_servos()       - home both hands to fraction 0.0, hold
  2) probe hour servo range   - raw pulse sweep on the hour servo
  3) probe minute servo range - raw pulse sweep on the minute servo
  4) test_clock_hands()       - sweep both hands through known clock positions
  5) jog hour to N degrees    - fine-tune a single angle
  6) jog minute to N degrees  - fine-tune a single angle
  7) test_team_positions()    - sweep both hands through all 20 team markers
  8) point at one team        - point a single hand at one named team
  q) quit
"""

while True:
    print(MENU)
    choice = input("> ").strip().lower()
    try:
        if choice == "1":
            calibrate_servos()
        elif choice == "2":
            probe_servo_range(hour_servo, "Hour")
        elif choice == "3":
            probe_servo_range(minute_servo, "Minute")
        elif choice == "4":
            test_clock_hands()
        elif choice == "5":
            jog("hour", float(input("degrees> ")))
        elif choice == "6":
            jog("minute", float(input("degrees> ")))
        elif choice == "7":
            test_team_positions()
        elif choice == "8":
            hand = input("hand (hour/minute)> ").strip().lower()
            point_at_team(hand, input("team name> ").strip())
        elif choice == "q":
            break
    except KeyboardInterrupt:
        print("\n(interrupted, back to menu)")
    except ValueError as e:
        print(e)
