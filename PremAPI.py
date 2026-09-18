import urequests
import secrets
import gc
import time
from machine import Pin, PWM

# ---------------------------------------------------------------------------
# EDIT THESE to match your wiring and belt calibration
# ---------------------------------------------------------------------------
PIN_SERVO_HOUR = 4        # servo driving the belt for the "hour" hand
PIN_SERVO_MINUTE = 18     # servo driving the belt for the "minute" hand
PIN_BUTTON = 34           # button that triggers "show next match" mode

# Pulse width (ns) at each end of belt travel. Swap min/max per servo if a
# belt runs backwards relative to the other.
SERVO_HOUR_MIN_NS = 500_000
SERVO_HOUR_MAX_NS = 2_500_000
SERVO_MINUTE_MIN_NS = 500_000
SERVO_MINUTE_MAX_NS = 2_500_000

DEBOUNCE_MS = 200
MATCH_DISPLAY_SECONDS = 10   # how long to hold the team positions before returning to clock mode
CLOCK_UPDATE_SECONDS = 10    # how often to nudge the hands while in clock mode

# Premier League clubs for the 2026-27 season, alphabetical -> index is that team's position along the belt.
# Update this list at the start of each season (promotions/relegations).
PREMIER_LEAGUE_TEAMS = sorted([
    "Arsenal", "Aston Villa", "AFC Bournemouth", "Brentford", "Brighton & Hove Albion",
    "Chelsea", "Coventry City", "Crystal Palace", "Everton", "Fulham",
    "Hull City", "Ipswich Town", "Leeds United", "Liverpool", "Manchester City",
    "Manchester United", "Newcastle United", "Nottingham Forest", "Sunderland", "Tottenham Hotspur",
])

# ---------------------------------------------------------------------------
# Servos
# ---------------------------------------------------------------------------
hour_servo = PWM(Pin(PIN_SERVO_HOUR), freq=50, duty_u16=0)
minute_servo = PWM(Pin(PIN_SERVO_MINUTE), freq=50, duty_u16=0)


def set_position(servo, fraction, min_ns, max_ns):
    """Drive a belt servo to `fraction` (0.0-1.0) of its travel range."""
    fraction = max(0.0, min(1.0, fraction))
    pulse_ns = int(min_ns + fraction * (max_ns - min_ns))
    servo.duty_ns(pulse_ns)


def set_hour_position(fraction):
    set_position(hour_servo, fraction, SERVO_HOUR_MIN_NS, SERVO_HOUR_MAX_NS)


def set_minute_position(fraction):
    set_position(minute_servo, fraction, SERVO_MINUTE_MIN_NS, SERVO_MINUTE_MAX_NS)


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
    one_week_later = now_ts + (7 * 24 * 60 * 60)
    date_from = format_date(time.gmtime(now_ts))
    date_to = format_date(time.gmtime(one_week_later))
    url = f"https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED&dateFrom={date_from}&dateTo={date_to}"
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
    """Map a team name to its 0.0-1.0 position along the belt (alphabetical order)."""
    target = normalize_team(team_name)
    for i, name in enumerate(PREMIER_LEAGUE_TEAMS):
        known = normalize_team(name)
        if known == target or known in target or target in known:
            return i / (len(PREMIER_LEAGUE_TEAMS) - 1)
    print("Unknown team, not in PREMIER_LEAGUE_TEAMS list:", team_name)
    return 0.5  # park in the middle if we don't recognize the name


def show_next_match(now_ts):
    result = get_next_match(now_ts)
    if result is None:
        return
    home, away = result
    set_hour_position(team_fraction(home))
    set_minute_position(team_fraction(away))


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


button.irq(trigger=Pin.IRQ_FALLING, handler=button_handler)


# ---------------------------------------------------------------------------
# Clock mode
# ---------------------------------------------------------------------------
def show_clock(utc_ts):
    t = time.gmtime(utc_ts)  # (year, month, mday, hour, minute, second, ...)
    hour, minute = t[3], t[4]
    hour_fraction = ((hour % 12) + minute / 60) / 12
    minute_fraction = minute / 60
    set_hour_position(hour_fraction)
    set_minute_position(minute_fraction)


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

while True:
    if match_requested:
        match_requested = False
        show_next_match(current_time())
        time.sleep(MATCH_DISPLAY_SECONDS)
    else:
        show_clock(current_time())
        time.sleep(CLOCK_UPDATE_SECONDS)
