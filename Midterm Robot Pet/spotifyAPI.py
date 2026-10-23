import network
import secrets
import time
import json
import gc
import urequests as requests


WIFI_SSID = secrets.Home
WIFI_PASS = secrets.HomePWD


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            time.sleep(0.5)
    print("Connected:", wlan.ifconfig())

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"

access_token = None

def refresh_token():
    # trade the refresh token for a new access token (lasts 1 hour)
    global access_token
    body = ("grant_type=refresh_token"
            "&refresh_token=" + secrets.refresh_Token +
            "&client_id=" + secrets.Client_ID +
            "&client_secret=" + secrets.Client_Secret)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(TOKEN_URL, data=body, headers=headers)
    if r.status_code == 200:
        access_token = r.json()["access_token"]
        print("Got access token")
    else:
        print("Token refresh failed:", r.status_code, r.text)
    r.close()


def spotify(method, path, body=None):
    # send one request to the Spotify API, refresh the token if it expired
    gc.collect()
    for attempt in range(2):
        headers = {"Authorization": "Bearer " + access_token}
        if body is None:
            data = None
            headers["Content-Length"] = "0"
        else:
            data = json.dumps(body)
            headers["Content-Type"] = "application/json"

        r = requests.request(method, API_URL + path, data=data, headers=headers)
        status = r.status_code
        result = None
        if status == 200 and method == "GET":
            result = r.json()
        elif status >= 400:
            print("Spotify error:", status, r.text)
        r.close()

        if status == 401 and attempt == 0:
            refresh_token()  # token expired, get a new one and try again
        else:
            return status, result


def next_song():
    return spotify("POST", "/me/player/next")


def prev_song():
    return spotify("POST", "/me/player/previous")


def play():
    return spotify("PUT", "/me/player/play")


def pause():
    return spotify("PUT", "/me/player/pause")


def set_volume(percent):
    percent = max(0, min(100, int(percent)))
    return spotify("PUT", "/me/player/volume?volume_percent=" + str(percent))


def play_playlist(playlist_uri):
    # playlist_uri looks like "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
    return spotify("PUT", "/me/player/play", {"context_uri": playlist_uri})


def like_song(track_uri):
    # needs the user-library-modify scope
    return spotify("PUT", "/me/library?uris=" + track_uri)


def now_playing():
    # returns (song, artist, image_url, track_uri, is_playing) or None if nothing is loaded
    status, data = spotify("GET", "/me/player/currently-playing")
    if status != 200 or data is None or data.get("item") is None:
        return None
    item = data["item"]
    song = item["name"]
    artist = item["artists"][0]["name"]
    images = item["album"]["images"]
    image_url = images[-1]["url"] if images else None  # smallest image
    track_uri = item["uri"]
    is_playing = data.get("is_playing", False)  # False when paused
    data = None
    gc.collect()
    return song, artist, image_url, track_uri, is_playing


def get_volume():
    # current Spotify volume 0-100, or None if no active device
    status, data = spotify("GET", "/me/player")
    if status != 200 or data is None or data.get("device") is None:
        return None
    return data["device"].get("volume_percent")


# quick test: run this file on the ESP32 with Spotify playing on your laptop
if __name__ == "__main__":
    connect_wifi()
    refresh_token()
    print("Now playing:", now_playing())
    time.sleep(2)
    print("Skipping...", next_song())
    time.sleep(2)
    print("Now playing:", now_playing())
