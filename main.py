import sys
import os
import time
import datetime
import traceback
from PIL import Image
from jinja2 import Environment, FileSystemLoader
from html2image import Html2Image
from dotenv import load_dotenv
from fetch_departure_info import extract_board_data
from fetch_calendar import get_calendar_events
from fetch_weather import fetch_weather_data


# Justera import efter din skärmmodell
# try:
#     from waveshare_epd import epd7in5_V2 as epd_driver
# except ImportError:
#     epd_driver = None

epd_driver = None

load_dotenv()
STOP_AREA_GID = os.environ.get("STOP_AREA_GID")
ICS_URL = os.environ.get("ICS_URL")
LONGITUDE = os.environ.get("LONGITUDE")
LATITUDE = os.environ.get("LATITUDE")

DATA_FETCH_INTERVAL = 300 

def prepare_calendar_data(events):
    """
    Skapar en fast Mån-Sön vy för nuvarande vecka.
    Mappar ALLA ICS-events till strukturen som dashboard.html förväntar sig.
    """
    week_view = []
    now = datetime.datetime.now()
    today_date = now.date()
    
    start_of_week = today_date - datetime.timedelta(days=today_date.weekday())
    
    dagar_korta = ['M', 'T', 'O', 'T', 'F', 'L', 'S']

    for i in range(7):
        target_date = start_of_week + datetime.timedelta(days=i)
        
        day_struct = {
            'namn': dagar_korta[i],
            'events': [],  # NU EN LISTA istället för single event
            'is_today': (target_date == today_date)
        }
        
        if events:
            for e in events:
                try:
                    if hasattr(e.begin, 'to'):
                        local_start = e.begin.to('local')
                        local_end = e.end.to('local')
                    else:
                        local_start = e.begin.astimezone() if e.begin.tzinfo else e.begin
                        local_end = e.end.astimezone() if e.end.tzinfo else e.end

                    if local_start.date() == target_date:
                        day_struct['events'].append({
                            'name': e.name,
                            'start': local_start.hour + (local_start.minute / 60.0),
                            'end': local_end.hour + (local_end.minute / 60.0)
                        })
                        # TA BORT break här så vi fortsätter leta efter fler events!
                        
                except Exception as err:
                    print(f"Kunde inte läsa eventdata för {getattr(e, 'name', 'okänt')}: {err}")
                    continue

        week_view.append(day_struct)
    return week_view

def get_icon_name(symbol_code, hour):
    """
    Mappar väderkoder till Lucide-ikoner, med stöd för natt-ikoner.
    """
    try:
        code = int(symbol_code)
    except (ValueError, TypeError):
        return "cloud"

    # Definiera vad som är natt (t.ex. före 06:00 eller efter 21:00)
    # Du kan justera tiderna här
    is_night = (hour >= 21 or hour < 6)

    # --- KLART & HALVKLART (Här byter vi ikon på natten) ---
    if code == 1: 
        return "moon" if is_night else "sun"  # Måne eller Sol
        
    if code in [2, 3]: 
        return "cloud-moon" if is_night else "cloud-sun" # Moln+Måne eller Moln+Sol

    # --- ÖVRIGA (Regn/Snö/Dimma ser oftast likadana ut natt som dag) ---
    if code in [4, 5, 6]: return "cloud"
    if code == 7: return "cloud-fog"
    
    # Regn
    if code in [8, 18]: return "cloud-drizzle"
    if code in [9, 10, 19, 20]: return "cloud-rain"

    # Åska
    if code in [11, 21]: return "cloud-lightning"

    # Snöblandat
    if code in [12, 13, 14, 22, 23, 24]: return "cloud-hail"

    # Snö
    if code in [15, 16, 17, 25, 26, 27]: return "snowflake"

    return "cloud"

def main():
    if epd_driver:
        epd = epd_driver.EPD()
        epd.init()
        epd.Clear()
    else:
        epd = None

    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('dashboard.html')
    
    # På Raspberry Pi brukar sökvägen vara:
    # browser_executable='/usr/bin/chromium-browser'
    hti = Html2Image(
        size=(480, 800),browser_executable="C:/Users/ludwi/Desktop/repos/chrome-headless-shell-win64/chrome-headless-shell.exe",
        custom_flags=[
            '--force-device-scale-factor=1', 
            '--hide-scrollbars',
            '--disable-gpu',
            '--no-sandbox',
            '--virtual-time-budget=3000'  # Add 2 second delay for rendering
        ]
    )
    # Fix for Chrome 128+ compatibility
#
    
    cached_departures = []
    cached_events = []
    cached_weather = {'temp': '--', 'symbol': 'na'}
    last_data_fetch = 0
    
    try:
        while True:
            now = datetime.datetime.now()
            
            # --- 1. Hämta bussdata ---
            print("Hämtar bussdata...")
            try:
                # OBS: Nu packar vi upp TVÅ värden från funktionen
                cached_departures, cached_stop_name = extract_board_data(
                    stop_area_gid=STOP_AREA_GID, 
                    filter_platforms= ['A'] # Eller ta bort filtret om du vill se allt
                )
            except Exception as e: 
                print(f"Avgångsfel: {e}")

            # --- 2. Hämta data som ändras sällan (Väder & Kalender) ---
            # Detta körs var 5:e minut (DATA_FETCH_INTERVAL)
            if time.time() - last_data_fetch > DATA_FETCH_INTERVAL or last_data_fetch == 0:
                print("Hämtar väder och kalender...")

                try:
                    cached_events = get_calendar_events(ICS_URL)
                except Exception as e: print(f"Kalenderfel: {e}")

                try:
                    cached_weather = fetch_weather_data(lat=LATITUDE, lon=LONGITUDE)
                except Exception as e: print(f"Väderfel: {e}")
                
                last_data_fetch = time.time()

            calendar_view = prepare_calendar_data(cached_events)
            
            dagar_sv = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
            manader_sv = ["Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
            
            dag_namn = dagar_sv[now.weekday()]
            manad_namn = f"{now.day} {manader_sv[now.month-1]}"
            sym_kod = cached_weather.get('symbol', '1')
            ikon_namn = get_icon_name(sym_kod, now.hour)
            print(f"Renderar HTML ({now.strftime('%H:%M')})...")

            html_content = template.render(
                hallplats_namn=cached_stop_name,
                datum_dag=dag_namn,
                datum_manad=manad_namn,
                klockslag=now.strftime("%H:%M"),
                vader_temp=cached_weather.get('temp', '--'),
                vader_symbol=cached_weather.get('symbol', '1'),
                vader_ikon=ikon_namn,
                kalender_dagar=calendar_view,
                avgangar=cached_departures
            )

            with open("renderad_sida.html", "w", encoding='utf-8') as f:
                f.write(html_content)
            
            hti.screenshot(html_file='renderad_sida.html', save_as='display_buffer.png')
            time.sleep(0.5)
            img = Image.open('display_buffer.png')
            # img = img.rotate(90, expand=True) # Avkommentera om skärmen sitter roterad
            img_bw = img.convert("1")

            # --- 4. Uppdatera skärmen ---
            if epd:
                buffer = epd.getbuffer(img_bw)
                
                # Full refresh vid hel timme (minskar ghosting)
                # Även bra att göra en full refresh vid midnatt (00:00) eller 03:00
                if now.minute == 0 and now.second < 10:
                    print("Full refresh...")
                    epd.init()
                    epd.display(buffer)
                else:
                    print("Partial refresh...")
                    epd.init_part()
                    epd.display_Partial(buffer)
                
                epd.sleep()
            else:
                print(f"Simulering klar: {len(cached_departures)} bussar hittades.")

            seconds_to_sleep = 60 - datetime.datetime.now().second
            time.sleep(seconds_to_sleep + 1) 

    except KeyboardInterrupt:
        print("Avslutar...")
        if epd:
            epd.init()
            epd.Clear()
            epd.sleep()
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    main()