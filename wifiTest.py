import connect_wifi
 
 #ON REPL you can type wlan.isconnected() hit ENTER. it will return True

ISS_URL = "http://api.open-notify.org/iss-now.json"

response = urequests.get(ISS_URL)
data = response.json()
response.close()

print(data)

weather_URL = "https://api.open-meteo.com/v1/forecast"
reply = urequests.get(weather_URL)
print(reply.json()['forecast'])