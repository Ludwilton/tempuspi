import requests
from ics import Calendar

def get_calendar_events(ics_url):
    events = []
    for cal in ics_url.split(","):
        response = requests.get(cal)
        response.raise_for_status()
        c = Calendar(response.text)
        events.extend(list(c.timeline))
    return events


if __name__ == "__main__":
    from dotenv import load_dotenv
    import os  
    load_dotenv()
    ICS_URL = os.environ.get("ICS_URL")
    result =  get_calendar_events(ICS_URL)
    print(result)