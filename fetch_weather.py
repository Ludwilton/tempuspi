import requests
import os
from dotenv import load_dotenv
load_dotenv()

LATITUDE= os.environ.get("LATITUDE")
LONGITUDE = os.environ.get("LONGITUDE")

def fetch_weather_data(lat,lon):
    url = f"https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/{lon}/lat/{lat}/data.json"
    
    response = requests.get(url)
    data = response.json()
    
    params = data['timeSeries'][0]['parameters']
    
    temp = next((item['values'][0] for item in params if item['name'] == 't'), None)
    symbol = next((item['values'][0] for item in params if item['name'] == 'Wsymb2'), None)
    
    return {"temp": temp, "symbol": symbol}
    
weather=fetch_weather_data(lat=LATITUDE, lon=LONGITUDE)
print(weather)


"""
1	Klart	Himlen är fri från moln
2	Lätt molnighet	Nästan klart, lite moln
3	Halvklart	Blandat sol och moln
4	Molnigt	Mer moln än sol
5	Mycket moln	Himlen täckt av moln (men inte "tjockt")
6	Mulet	Helt grått och tjockt molntäcke
7	Dimma	Sikt reducerad
8	Lätta regnskurar	Korta perioder av lätt regn
9	Regnskurar	Korta perioder av vanligt regn
10	Kraftiga regnskurar	Korta perioder av ösregn
11	Åskskurar	Regnskurar med åska
12	Lätta byar av snöblandat regn	
13	Byar av snöblandat regn	
14	Kraftiga byar av snöblandat regn	
15	Lätta snöbyar	
16	Snöbyar	
17	Kraftiga snöbyar	
18	Lätt regn	Ihållande lätt regn
19	Regn	Ihållande regn
20	Kraftigt regn	Ihållande ösregn
21	Åska	Ihållande regn med åska
22	Lätt snöblandat regn	Ihållande
23	Snöblandat regn	Ihållande
24	Kraftigt snöblandat regn	Ihållande
25	Lätt snöfall	Ihållande
26	Snöfall	Ihållande
27	Kraftigt snöfall	Ihållande
"""