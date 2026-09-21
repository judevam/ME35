import time
from machine import Pin, PWM

# ---------------------------------------------------------------------------
# Standalone servo calibration rig - no wifi, no time sync, no API calls.
# Copy calibrated values into PremAPI.py once you're happy with them here:
# SERVO_HOUR_MIN_NS/MAX_NS/OFFSET_DEG/SCALE for the hour hand, and the whole
# MINUTE_CALIBRATION table for the minute hand.
# ---------------------------------------------------------------------------
PIN_SERVO_HOUR = 4        # servo driving the hour hand, geared 2:1 for a 360-degree sweep
PIN_SERVO_MINUTE = 5      # servo driving the minute hand, geared 2:1 for a 360-degree sweep

# Pulse width (ns) at each end of the servo's own travel (0-180 degrees on
# the servo itself), which the 2:1 gearing turns into a full 0-360 degree
# sweep of the clock hand. Swap min/max per servo if one runs backwards
# relative to the other.
SERVO_HOUR_MIN_NS = 500_000
SERVO_HOUR_MAX_NS = 2_500_000

# Calibration: degrees added to the commanded angle to correct for how the
# horn/gear landed when it was mounted. See calibrate_servos() below.
# Only used for the hour servo - the minute servo's calibration is the
# MINUTE_CALIBRATION table below instead.
SERVO_HOUR_OFFSET_DEG = 315.0

# Calibration: multiplier on the commanded angle to correct a proportional
# under/over-rotation (e.g. the real gear ratio isn't exactly 2:1). Found by
# jogging to a known angle and comparing to the measured result:
#   scale = commanded_degrees / actual_measured_degrees
# e.g. jogged hour to 270, it actually landed at 250 -> 270/250 = 1.08.
# Only used for the hour servo now - the minute servo's response turned out
# to be non-linear (see MINUTE_CALIBRATION below), so a single scale number
# can't describe it and it uses a measured table + interpolation instead.
SERVO_HOUR_SCALE = 1.0

# Calibration table for the minute servo: measured (minute-mark, pulse ns)
# points from raw-pulse probing (see probe_servo_range / set_raw_pulse),
# since it takes progressively more ns per minute as the pulse gets longer -
# not a straight line. The floor of this servo's pulse range (~300,000ns)
# lands at minute 13, not minute 0, so minutes 0-13 are unreachable on this
# lap; they're reached instead by continuing a bit past a full turn, which is
# why the table goes up to "minute 75" (= minute 15 of the next lap around).
# Re-measure and update this if the servo/gearing/mounting ever changes.
MINUTE_CALIBRATION = [
    (13, 300_000),
    (15, 390_000),
    (30, 850_000),
    (45, 1_450_000),
    (60, 2_000_000),
    (75, 2_450_000),
]

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


def interpolate_ns(table, x):
    """Piecewise-linear lookup: find where x falls between two calibrated
    (x, ns) points and interpolate, instead of assuming one straight line
    across the whole range like set_position does."""
    for (x0, ns0), (x1, ns1) in zip(table, table[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return ns0 + t * (ns1 - ns0)
    return table[0][1] if x < table[0][0] else table[-1][1]


def set_minute_position(fraction):
    """Point the minute hand using the measured MINUTE_CALIBRATION table
    instead of a straight-line formula. Minutes 0-13 fall below this servo's
    real pulse floor, so they're looked up as "minute + 60" instead - reached
    by continuing a bit past a full turn rather than a low pulse."""
    minute = fraction * 60
    low_minute = MINUTE_CALIBRATION[0][0]
    if minute < low_minute:
        minute += 60
    pulse_ns = int(interpolate_ns(MINUTE_CALIBRATION, minute))
    minute_servo.duty_ns(pulse_ns)
    log(f"Minute servo -> target {fraction * 360:.1f} deg ({fraction * 60:.1f} min), pulse {pulse_ns} ns")


# ---------------------------------------------------------------------------
# Test routines
# ---------------------------------------------------------------------------
def calibrate_servos():
    """Park both hands at fraction 0.0 (should be true 12 o'clock) and hold,
    so you can measure how far off each one physically sits.

    Measure each hand against the 12 o'clock mark: how many degrees off, and
    which way (clockwise/counter-clockwise). Update SERVO_HOUR_OFFSET_DEG (for
    the hour hand) or the first MINUTE_CALIBRATION point (for the minute
    hand) with the correction, then run this again to confirm. Ctrl+C out of
    this once you've measured.
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


def set_raw_pulse(servo, ns):
    """Set one exact pulse width directly, no fraction/offset/scale math at
    all. For pinning down precise ns values (e.g. exactly where true 12
    o'clock or a specific minute mark lands) tighter than probe_servo_range's
    fixed step size lets you."""
    servo.duty_ns(ns)
    log(f"Raw pulse -> {ns} ns")


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
    fraction = (degrees % 360) / 360.0
    if servo_name == "hour":
        set_hour_position(fraction)
    else:
        set_minute_position(fraction)


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
  9) set raw pulse (ns)       - dial in one exact pulse width, no math at all
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
        elif choice == "9":
            hand = input("hand (hour/minute)> ").strip().lower()
            servo = hour_servo if hand == "hour" else minute_servo
            set_raw_pulse(servo, int(input("pulse ns> ")))
        elif choice == "q":
            break
    except KeyboardInterrupt:
        print("\n(interrupted, back to menu)")
    except ValueError as e:
        print(e)
