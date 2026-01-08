import os
import sys
from dotenv import load_dotenv
import requests
from datetime import datetime
from requests.auth import HTTPBasicAuth

load_dotenv()


def get_access_token(client_id=None, secret=None):
    client_id = client_id or os.environ.get("VASTTRAFIK_API_KEY")
    secret = secret or os.environ.get("VASTTRAFIK_SECRET")
    
    if not client_id or not secret:
        raise RuntimeError("VASTTRAFIK_API_KEY och VASTTRAFIK_SECRET saknas.")

    url = "https://ext-api.vasttrafik.se/token"
    auth = HTTPBasicAuth(client_id, secret)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}
    
    try:
        r = requests.post(url, headers=headers, data=data, auth=auth, timeout=10)
        r.raise_for_status()
        return r.json()["access_token"]
    except Exception as e:
        raise RuntimeError(f"Kunde inte hämta token: {e}")

def get_departures(access_token, stop_area_gid, time_span_in_minutes=180):
    url = f"https://ext-api.vasttrafik.se/pr/v4/stop-areas/{stop_area_gid}/departures"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    params = {
        "timeSpanInMinutes": time_span_in_minutes,
        "maxDeparturesPerLineAndDirection": 4, 
        "limit": 80,
        "offset": 0,
        "includeOccupancy": False,
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def format_time(dep_obj):
    """
    Hjälpfunktion för att skapa tidssträngar för displayen.
    Returnerar strängar som 'Nu', '5', '14:25' eller 'Inst'.
    """
    if not dep_obj:
        return ""
    
    if dep_obj['cancelled']:
        return "Inst"
    
    minutes = dep_obj['minutes']
    if minutes == 0:
        return "Nu"
    elif minutes < 60:
        return f"{minutes}"
    else:
        return dep_obj['abs_time']
    
def extract_board_data(stop_area_gid, filter_platforms=None):
    """
    Returnerar en tuple: (lista_med_avgångar, hållplatsnamn)
    """
    token = get_access_token()
    api_response = get_departures(token, stop_area_gid)
    now = datetime.now().astimezone()
    
    # om flera platformar på samma gid men vill endast visa en
    if isinstance(filter_platforms, str): 
        filter_platforms = [filter_platforms]

    stop_name = None
    if api_response.get('results'):
        raw_name = api_response['results'][0]['stopPoint']['name']

        stop_name = raw_name.replace(", Göteborg", "").strip()


    raw_departures = []

    for item in api_response.get('results', []):
        stop_point = item['stopPoint']
        platform = stop_point.get('platform', '?')
        if filter_platforms and platform not in filter_platforms:
            continue

        planned_str = item['plannedTime']
        estimated_str = item.get('estimatedTime') or planned_str
        estimated_time = datetime.fromisoformat(estimated_str)

        minutes_left = int((estimated_time - now).total_seconds() / 60)
        if minutes_left < 0: minutes_left = 0
        
        abs_time_str = estimated_time.strftime("%H:%M")

        departure_obj = {
            "minutes": minutes_left,
            "abs_time": abs_time_str,
            "cancelled": item.get('isCancelled', False),
            "platform": platform
        }

        service = item['serviceJourney']
        line_name = service['line']['shortName']
        destination = service['directionDetails']['shortDirection']
        via = service['directionDetails'].get('via')
        
        group_key = (line_name, destination, via)

        raw_departures.append({
            "key": group_key,
            "line": line_name,
            "destination": destination,
            "via": via,
            "platform": platform,
            "data": departure_obj
        })

    grouped_data = {}
    
    for dep in raw_departures:
        key = dep['key']
        if key not in grouped_data:
            display_dest = dep['destination']
            grouped_data[key] = {
                "line": dep['line'],
                "destination": display_dest,
                "platform": dep['platform'],
                "departures": []
            }
        grouped_data[key]['departures'].append(dep['data'])
    
    board_rows = []
    
    for key, group in grouped_data.items():
        sorted_deps = sorted(group['departures'], key=lambda x: x['minutes'])
        
        next_dep = sorted_deps[0] if len(sorted_deps) > 0 else None
        after_dep = sorted_deps[1] if len(sorted_deps) > 1 else None

        sort_minutes = next_dep['minutes'] if next_dep else 9999

        row = {
            "line": group['line'],
            "destination": group['destination'],
            "next": format_time(next_dep),
            "later": format_time(after_dep),
            "platform": group['platform'],
            "sort_time": sort_minutes
        }
        board_rows.append(row)

    def sort_logic(x):
        try:
            line_num = int(x['line'])
        except:
            line_num = 9999
        
        return (x['sort_time'], line_num)

    board_rows.sort(key=sort_logic)
    board_rows = board_rows[:5]
    return board_rows, stop_name

if __name__ == "__main__":
    TEST_GID = "9021014001960000" 
    access_token = get_access_token()
    STOP_AREA_GID = os.environ.get("STOP_AREA_GID")
    departures = get_departures(access_token,STOP_AREA_GID)
    
    print(departures)
    
    
    