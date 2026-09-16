import urequests
import secrets
import gc
import time

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
    """Fetch current UTC time from TimeAPI.io. Returns a time tuple or None."""
    url = "https://timeapi.io/api/time/current/zone?timeZone=America/New_York"
    for attempt in range(1, max_retries + 1):
        try:
            response = urequests.get(url)
            if response.status_code == 200:
                data = response.json()
                response.close()
                # data example: {'year':2026,'month':9,'day':16,'hour':...}
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

print(time.gmtime())

wifi_connect()

now_ts = get_utc_now()
if now_ts is None:
    now_ts = time.time()  # fallback to board's own clock

gc.collect()

one_week_later = now_ts + (7 * 24 * 60 * 60)

date_from = format_date(time.gmtime(now_ts))
date_to = format_date(time.gmtime(one_week_later))

url = f"https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED&dateFrom={date_from}&dateTo={date_to}"
headers = {'X-Auth-Token': secrets.FOOTBALL_API_TOKEN}

response = urequests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    matches = data['matches']
    response.close()
    if matches:
        next_match = matches[0]
        home = next_match['homeTeam']['name']
        away = next_match['awayTeam']['name']
        kickoff = next_match['utcDate']
        print(f"Next PL match: {home} vs {away} at {kickoff} UTC")
    else:
        print("No scheduled matches in the next week.")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
    response.close()