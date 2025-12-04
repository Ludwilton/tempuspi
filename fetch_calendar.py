import requests
from ics import Calendar

def get_calendar_events(ics_url):
    response = requests.get(ics_url)
    response.raise_for_status()
    c = Calendar(response.text)
    events = list(c.timeline)
    return events


if __name__ == "__main__":
    from dotenv import load_dotenv
    import os  
    load_dotenv()
    
    ICS_URL = os.environ.get("ICS_URL")
    result =  get_calendar_events(ICS_URL)
    print(result)