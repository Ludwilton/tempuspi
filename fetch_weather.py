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
    temp = round(temp)
    return {"temp": temp, "symbol": symbol}
    
"""
Wsymb2 legend:
1	Klart
2	Lätt molnighet
3	Halvklart
4	Molnigt
5	Mycket moln
6	Mulet
7	Dimma
8	Lätta regnskurar
9	Regnskurar
10	Kraftiga regnskurar
11	Åskskurar
12	Lätt snöblandat regn	
13	snöblandat regn	
14	Kraftigt snöblandat regn	
15	Lätta snöbyar	
16	Snöbyar	
17	Kraftiga snöbyar	
18	Lätt regn	
19	Regn	
20	Kraftigt regn	
21	Åska	
22	Lätt snöblandat regn	
23	Snöblandat regn	
24	Kraftigt snöblandat regn	
25	Lätt snöfall	
26	Snöfall	
27	Kraftigt snöfall	
"""