import gc, time, urequests, neopixel
import secrets, sys, select
from machine import Pin, PWM

# ---------------------------------------------------------------------------
# EDIT
# ---------------------------------------------------------------------------
PIN_SERVO_HOUR = 4        # servo driving the hour hand, geared 2:1 for a 360-degree sweep
PIN_SERVO_MINUTE = 5      # servo driving the minute hand, geared 2:1 for a 360-degree sweep
PIN_NEOPIXEL = 17         # D15 - lights up while showing the time, off while showing PL matchup
NUM_NEOPIXELS = 1         # how many pixels are on that strip/ring
NEOPIXEL_MATCH_COLOR = (0, 255, 0)   # (R, G, B) color while showing a matchup
PIN_BUTTON = 13           # D34 on the robo board - button that triggers "show next match" mode
PIN_MANUAL_BUTTON = 32    # D13 - toggles manual "type an angle for the minute hand" mode

# Pulse width (ns) at each end of the servo's own travel (0-180 degrees on
# the servo itself), which the 2:1 gearing turns into a full 0-360 degree
# sweep of the clock hand. Swap min/max per servo if one runs backwards
# relative to the other.
SERVO_HOUR_MIN_NS = 500_000
SERVO_HOUR_MAX_NS = 2_500_000
SERVO_MINUTE_MIN_NS = 400_000
SERVO_MINUTE_MAX_NS = 2_600_000

# Calibration: degrees added to the commanded angle to correct for how the
# horn/gear landed when it was mounted. Set via calibrate_servos() — command
# fraction 0.0, measure how far off true 12 o'clock the hand sits and which
# way, then adjust this value and re-run calibrate_servos() to confirm. If
# nudging it the "obvious" direction makes it worse, this rig's gearing
# inverts rotation sense, so flip the sign instead.
SERVO_HOUR_OFFSET_DEG = 315.0

# Calibration: multiplier on the commanded angle to correct a proportional
# under/over-rotation (e.g. the real gear ratio isn't exactly 2:1). Found by
# jogging to a known angle (see ServoTest.py) and comparing to the measured
# result: scale = commanded_degrees / actual_measured_degrees.
SERVO_HOUR_SCALE = 1.0


DEBOUNCE_MS = 200
MATCH_DISPLAY_SECONDS = 10   # how long to hold the team positions before returning to clock mode
CLOCK_UPDATE_SECONDS = 10    # how often to nudge the hands while in clock mode
STARTUP_TEST_STEP_SECONDS = 1.5   # pause between each position during the startup hand test

# Premier League clubs in physical clockwise order around the dial, starting
# from the marker nearest 12 o'clock. This is NOT alphabetical - it matches
# how the teams are actually printed on the face. Update this if the face is
# ever redone (e.g. promotions/relegations changing which teams are on it).
PREMIER_LEAGUE_TEAMS = [
    "Manchester City", "Arsenal", "Hull City", "Chelsea", "Brentford",
    "Liverpool", "Newcastle United", "Everton", "Leeds United", "Brighton & Hove Albion",
    "Manchester United", "Sunderland", "Crystal Palace", "Ipswich Town", "AFC Bournemouth",
    "Nottingham Forest", "Tottenham Hotspur", "Aston Villa", "Fulham", "Coventry City",
]

# Calibration: degrees added to every team's dial position, to correct for
# how the printed face sits relative to true 12 o'clock (independent of the
# hour/minute servo mounting offsets above - this is about the face artwork,
# shared by both hands since they point at the same team ring). Found the
# same way as the servo offsets: point at team index 0 (first team above),
# measure how far off true 12 it sits and which way, then adjust.
TEAM_DIAL_OFFSET_DEG = 0.0

# ---------------------------------------------------------------------------
# Servos + LEDs
# ---------------------------------------------------------------------------
hour_servo = PWM(Pin(PIN_SERVO_HOUR), freq=50, duty_u16=0)
minute_servo = PWM(Pin(PIN_SERVO_MINUTE), freq=50, duty_u16=0)
mode_pixels = neopixel.NeoPixel(Pin(PIN_NEOPIXEL), NUM_NEOPIXELS)

def set_mode_led(on):
    color = NEOPIXEL_MATCH_COLOR if on else (0, 0, 0)
    for i in range(NUM_NEOPIXELS):
        mode_pixels[i] = color
    mode_pixels.write()


def log(msg):
    t = time.gmtime(current_time())
    print("[{:02d}:{:02d}:{:02d}] {}".format(t[3], t[4], t[5], msg))


def set_position(servo, fraction, min_ns, max_ns, offset_deg, scale, label):
    """Point a geared, 360-degree servo to `fraction` (0.0-1.0) of a full turn,
    corrected by `scale` (proportional under/over-rotation) then shifted by
    `offset_deg` (to correct for how it was mounted)."""
    adjusted = (fraction * scale + offset_deg / 360.0) % 1.0
    pulse_ns = int(min_ns + adjusted * (max_ns - min_ns))
    servo.duty_ns(pulse_ns)
    log(f"{label} servo -> {adjusted * 360:.1f} deg (target {fraction * 360:.1f} deg, scale {scale:.3f}, offset {offset_deg:+.1f})")


def set_hour_position(fraction):
    set_position(hour_servo, fraction, SERVO_HOUR_MIN_NS, SERVO_HOUR_MAX_NS, SERVO_HOUR_OFFSET_DEG, SERVO_HOUR_SCALE, label="Hour")


# Minute servo calibration, fitted from measurements at offset 0, scale 1.0,
# pulse range 500_000-2_500_000 ns. Cubic: measured hand angle (degrees
# clockwise from 12, unwrapped so it runs 96 -> 486) as a function of the
# commanded angle 0-360. Coefficients are highest power first.
MINUTE_CAL = (5.509462785e-06, -2.713054037e-03, 1.368683763, 89.345574)

# The servo sweeps ~390 deg, so dial angles ~96-126 deg can be reached two
# ways. The hand has to unwind once per lap; this is the dial angle where it
# does. Kept mid-overlap so it stays away from the servo's unreliable end stops.
MINUTE_UNWIND_DEG = 111.0


def poly_eval(coeffs, x):
    r = 0.0
    for c in coeffs:
        r = r * x + c
    return r


def command_for_angle(target_deg, coeffs, unwind_deg):
    """Command angle (0-360) that makes the hand point at target_deg
    (degrees clockwise from true 12 o'clock). Inverts the cubic by bisection."""
    t = target_deg % 360.0
    if t < unwind_deg:
        t += 360.0                      # use the "second lap" end of the servo's travel
    low, high = 0.0, 360.0
    if t <= poly_eval(coeffs, low):
        return low
    if t >= poly_eval(coeffs, high):
        return high
    for _ in range(30):
        mid = (low + high) / 2
        if poly_eval(coeffs, mid) < t:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def set_minute_position(fraction):
    target = fraction * 360.0
    cmd = command_for_angle(target, MINUTE_CAL, MINUTE_UNWIND_DEG)
    pulse_ns = int(SERVO_MINUTE_MIN_NS + (cmd / 360.0) * (SERVO_MINUTE_MAX_NS - SERVO_MINUTE_MIN_NS))
    minute_servo.duty_ns(pulse_ns)
    log(f"Minute servo -> dial {target:.1f} deg (command {cmd:.1f} deg, {pulse_ns} ns)")


# Button and handler
manual_button = Pin(PIN_MANUAL_BUTTON, Pin.IN, Pin.PULL_UP)
last_manual_press = 0
manual_requested = False

def manual_button_handler(pin):
    global last_manual_press, manual_requested
    now = time.ticks_ms()
    if time.ticks_diff(now, last_manual_press) > DEBOUNCE_MS and pin.value() == 0:
        last_manual_press = now
        manual_requested = True


manual_button.irq(trigger=Pin.IRQ_FALLING, handler=manual_button_handler)


# ---------------------------------------------------------------------------
# Wifi / time
# ---------------------------------------------------------------------------
def wifi_connect():
    import network
    sta_if = network.WLAN(network.WLAN.IF_STA)
    sta_if.active(False)
    time.sleep(1)
    sta_if.active(True)
    time.sleep(1)
    try:
        sta_if.disconnect()
    except OSError:
        pass
    time.sleep(0.5)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.connect(secrets.SSID, secrets.PWD)
        while not sta_if.isconnected():
            pass
    print('network config:', sta_if.ipconfig('addr4'))


def get_utc_now(max_retries=3):
    """Fetch current local (America/New_York) time from TimeAPI.io. Returns an epoch-like value or None."""
    url = "https://timeapi.io/api/time/current/zone?timeZone=America/New_York"
    for attempt in range(1, max_retries + 1):
        try:
            response = urequests.get(url)
            if response.status_code == 200:
                data = response.json()
                response.close()
                t = time.mktime((
                    data['year'], data['month'], data['day'],
                    data['hour'], data['minute'], data['seconds'],
                    0, 0
                ))
                print("Time synced from TimeAPI.io:", data['dateTime'])
                return t
            else:
                print(f"TimeAPI attempt {attempt} bad status: {response.status_code}")
                response.close()
        except OSError as e:
            print(f"TimeAPI attempt {attempt} failed: {e}")
        time.sleep(2)
    print("TimeAPI.io failed after retries — using unsynced clock")
    return None


def format_date(t):
    return "{:04d}-{:02d}-{:02d}".format(t[0], t[1], t[2])


# ---------------------------------------------------------------------------
# Football API
# ---------------------------------------------------------------------------
def get_next_match(now_ts):
    """Return (home_name, away_name) for the next scheduled PL match, or None."""
    one_week_later = now_ts + (21 * 24 * 60 * 60)
    date_from = format_date(time.gmtime(now_ts))
    date_to = format_date(time.gmtime(one_week_later))
    url = f"https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED,TIMED&dateFrom={date_from}&dateTo={date_to}"
    headers = {'X-Auth-Token': secrets.FOOTBALL_API_TOKEN}

    try:
        response = urequests.get(url, headers=headers)
    except OSError as e:
        print("Match request failed:", e)
        return None

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        response.close()
        return None

    data = response.json()
    matches = data['matches']
    response.close()

    if not matches:
        print("No scheduled matches in the next week.")
        return None

    next_match = matches[0]
    home = next_match['homeTeam']['name']
    away = next_match['awayTeam']['name']
    print(f"Next PL match: {home} vs {away} at {next_match['utcDate']} UTC")
    return home, away


def normalize_team(name):
    name = name.lower().replace("&", "and")
    for suffix in (" fc", " afc"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def team_fraction(team_name):
    """Map a team name to its 0.0-1.0 position around the dial (physical clockwise order).

    Divides by len(teams), not len(teams) - 1: this is a circular dial, so
    fraction 0.0 and 1.0 are the same physical spot. Dividing by the count
    (not count - 1) spaces all 20 teams evenly around the full circle without
    the first and last team landing on top of each other. TEAM_DIAL_OFFSET_DEG
    then shifts the whole ring to match where it actually sits on the face.
    """
    target = normalize_team(team_name)
    for i, name in enumerate(PREMIER_LEAGUE_TEAMS):
        known = normalize_team(name)
        if known == target or known in target or target in known:
            return (i / len(PREMIER_LEAGUE_TEAMS) + TEAM_DIAL_OFFSET_DEG / 360.0) % 1.0
    print("Unknown team, not in PREMIER_LEAGUE_TEAMS list:", team_name)
    return 0.5  # park in the middle if we don't recognize the name


def show_next_match(now_ts):
    """Hour hand points at the home team, minute hand points at the away team.
    LED is off from the moment the button press is handled until we're done."""
    log("Match button -> requesting next match")
    set_mode_led(False)              # LED off = match requested (instant visual feedback)
    gc.collect()
    try:
        result = get_next_match(now_ts)
    except Exception as e:           # MemoryError, bad JSON, etc. must not kill the clock loop
        print("Match lookup failed:", repr(e))
        result = None
    gc.collect()

    if result is None:
        log("No match data -> back to clock")
        set_mode_led(True)
        return

    home, away = result
    log(f"Showing matchup: {home} (hour hand) vs {away} (minute hand)")
    set_hour_position(team_fraction(home))
    set_minute_position(team_fraction(away))
    time.sleep(MATCH_DISPLAY_SECONDS)
    set_mode_led(True)
    log("Matchup display done -> returning to clock")
    
# ---------------------------------------------------------------------------
# Button (ISR sets a flag, main loop does the actual work)
# ---------------------------------------------------------------------------
button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_UP)
last_press = 0
match_requested = False


def button_handler(pin):
    global last_press, match_requested
    now = time.ticks_ms()
    if time.ticks_diff(now, last_press) > DEBOUNCE_MS and pin.value() == 0:
        last_press = now
        match_requested = True
        print("match request")


button.irq(trigger=Pin.IRQ_FALLING, handler=button_handler)



# ---------------------------------------------------------------------------
# Clock mode - normal two-hand clock
# ---------------------------------------------------------------------------
def show_clock(utc_ts):
    t = time.gmtime(utc_ts)  # (year, month, mday, hour, minute, second, ...)
    hour, minute = t[3], t[4]
    hour_fraction = ((hour % 12) + minute / 60) / 12
    minute_fraction = minute / 60
    log("Clock update -> {:d}:{:02d}".format(hour % 12 or 12, minute))
    set_hour_position(hour_fraction)
    set_minute_position(minute_fraction)


def test_clock_hands():
    """One-time startup sanity check: sweep each hand through a few known positions.

    Uses a continuously increasing fraction (0.0 -> 1.0) rather than wrapping
    back to 0.0 for the final "12"/"60" mark. Fraction 0.0 and 1.0 land on the
    same visual spot but are different physical servo angles (0 deg vs 180 deg,
    since it's geared 2:1) - commanding 0.0 from mid-swing would yank the
    servo all the way backward instead of finishing the turn forward.
    """
    log("Startup test: sweeping hour hand through 12, 3, 6, 9, 12")
    for label, fraction in (("12", 0.0), ("3", 0.25), ("6", 0.5), ("9", 0.75), ("12", 1.0)):
        log(f"Hour hand target: {label} o'clock")
        set_hour_position(fraction)
        time.sleep(STARTUP_TEST_STEP_SECONDS)

    log("Startup test: sweeping minute hand through 15, 30, 45, 60")
    for label, fraction in (("15", 0.25), ("30", 0.5), ("45", 0.75), ("60", 1.0)):
        log(f"Minute hand target: {label}")
        set_minute_position(fraction)
        time.sleep(STARTUP_TEST_STEP_SECONDS)

    log("Startup test complete")


def calibrate_servos():
    """Park both hands at fraction 0.0 (should be true 12 o'clock) and hold,
    so you can measure how far off each one physically sits.

    Usage: temporarily call this instead of test_clock_hands() in Main below,
    flash it, then measure each hand against the 12 o'clock mark:
      - How many degrees off is it, and which way (clockwise/counter-clockwise)?
    Report those two numbers and I'll set SERVO_HOUR_OFFSET_DEG /
    SERVO_MINUTE_OFFSET_DEG for you. Ctrl+C out of this once you've measured.
    """
    log("CALIBRATION: parking hour + minute hands at fraction 0.0 (true 12 o'clock)")
    set_hour_position(0.0)
    set_minute_position(0.0)
    log("Hands parked - measure the offset on each, then Ctrl+C and report back")
    while True:
        time.sleep(1)


def probe_servo_range(servo, label, start_ns=300_000, end_ns=2_700_000, step_ns=100_000, step_seconds=1.0):
    """Sweep raw pulse widths on one servo, ignoring fraction/offset math, so
    you can find where it actually stalls/buzzes at each end.

    Usage: temporarily call e.g. probe_servo_range(hour_servo, "Hour") instead
    of test_clock_hands() in Main below. Watch/listen for the pulse width
    where it stops moving cleanly (grinds, buzzes, or the hand just stops).
    Report the ns value at each end and I'll set SERVO_HOUR_MIN_NS/MAX_NS (or
    the minute equivalents) a little inside those limits, so the fraction
    math never asks for a pulse the servo can't actually reach.
    """
    ns = start_ns
    while ns <= end_ns:
        servo.duty_ns(ns)
        log(f"{label} raw pulse -> {ns} ns")
        time.sleep(step_seconds)
        ns += step_ns

def manual_angle_mode():
    """Prompt over serial for an angle (0-360) and move the minute hand there.
    Keeps prompting until the D13 button is pressed again."""
    global manual_requested
    manual_requested = False  # consume the press that got us here

    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)

    log("MANUAL MODE: press D13 again to exit")
    #prompt = "Hour hand angle (0-360): "
    prompt = "Minute hand angle (0-360): "
    print(prompt, end="")
    buf = ""

    while not manual_requested:
        if not poller.poll(50):   # wait up to 50 ms for a keystroke, then re-check the button
            continue
        ch = sys.stdin.read(1)
        if ch not in ("\r", "\n"):
            buf += ch
            continue

        text = buf.strip()
        buf = ""
        if not text:
            continue  # ignore blank lines (also swallows the \n of a \r\n pair)

        try:
            angle = float(text)
        except ValueError:
            print("Not a number: {!r}".format(text))
            print(prompt, end="")
            continue

        if not 0 <= angle <= 360:
            print("Out of range (must be 0-360)")
        else:
            set_minute_position(angle / 360.0)            
            #set_hour_position(angle / 360.0)
        print(prompt, end="")

    poller.unregister(sys.stdin)
    manual_requested = False
    print()
    log("Manual mode done -> returning to clock")


def wait_or_button(seconds):
    end = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        if match_requested or manual_requested:
            return
        time.sleep_ms(50)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print(time.gmtime())

wifi_connect()

now_ts = get_utc_now()
if now_ts is None:
    now_ts = time.time()  # fallback to board's own clock

sync_ticks = time.ticks_ms()


def current_time():
    return now_ts + time.ticks_diff(time.ticks_ms(), sync_ticks) // 1000


gc.collect()

test_clock_hands()

#calibrate_servos()

#probe_servo_range(minute_servo, "Minute", 300_000, 2_700_000)

set_mode_led(True)

while True:
    if manual_requested:
        manual_angle_mode()
    elif match_requested:
        match_requested = False
        show_next_match(current_time())
        match_requested = False      # ignore presses made during the display
    else:
        show_clock(current_time())
        wait_or_button(CLOCK_UPDATE_SECONDS)