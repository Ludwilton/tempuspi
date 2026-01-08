import sys
import os
import time
import datetime
import traceback
from PIL import Image
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
from fetch_departure_info import extract_board_data
from fetch_calendar import get_calendar_events
from fetch_weather import fetch_weather_data
from fetch_spotify import get_spotify_data
from playwright.sync_api import sync_playwright


# PI:
# from waveshare_epd import epd7in5_V2 as epd_driver


# Windows debug 
# CHROME_COMMAND = r"C:/Users/ludwi/Desktop/repos/chrome-headless-shell-win64/chrome-headless-shell.exe"
epd_driver = None
CHROME_COMMAND = "chromium/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"   
DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 800

load_dotenv()
STOP_AREA_GID = os.environ.get("STOP_AREA_GID")
ICS_URL = os.environ.get("ICS_URL")
LONGITUDE = os.environ.get("LONGITUDE")
LATITUDE = os.environ.get("LATITUDE")
platform = os.environ.get("DEPARTURE_PLATFORM")
DATA_FETCH_INTERVAL = 300
CALENDAR_FETCH_INTERVAL = 3600


NIGHT_MODE_START = 3
NIGHT_MODE_END = 5
NIGHT_MODE_SLEEP = 300


playwright_instance = None
browser_instance = None
page_instance = None

def prepare_calendar_data(events):
    """
    Skapar en fast Mån-Sön vy för nuvarande vecka.
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
            'events': [],
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
                        
                except Exception as err:
                    print(f"Kunde inte läsa eventdata för {getattr(e, 'name', 'okänt')}: {err}")
                    continue

        week_view.append(day_struct)
    return week_view

def get_icon_name(symbol_code, hour):
    """
    Mappar väderkoder till Lucide-ikoner.
    """
    try:
        code = int(symbol_code)
    except (ValueError, TypeError):
        return "cloud"
    is_night = (hour >= 21 or hour < 6)
    if code == 1: 
        return "moon" if is_night else "sun"
    if code in [2, 3]: 
        return "cloud-moon" if is_night else "cloud-sun"
    if code in [4, 5, 6]: return "cloud"
    if code == 7: return "cloud-fog"
    if code in [8, 18]: return "cloud-drizzle"
    if code in [9, 10, 19, 20]: return "cloud-rain"
    if code in [11, 21]: return "cloud-lightning"
    if code in [12, 13, 14, 22, 23, 24]: return "cloud-hail"
    if code in [15, 16, 17, 25, 26, 27]: return "snowflake"

    return "cloud"


def init_browser():
    global playwright_instance, browser_instance, page_instance
    
    print("Startar browser...")
    start = time.time()
    
    playwright_instance = sync_playwright().start()
    if epd_driver is None:
        browser_instance = playwright_instance.chromium.launch(
            headless=True,
            executable_path=CHROME_COMMAND,
            args=[
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
    else:
        browser_instance = playwright_instance.chromium.launch(
        headless=True,
        executable_path='/usr/bin/chromium-headless-shell',
        args=[
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ]
    )
    page_instance = browser_instance.new_page(
        viewport={'width': DISPLAY_WIDTH, 'height': DISPLAY_HEIGHT}
    )
    
    print(f"browser startup: {time.time()-start:.1f}s")


def take_screenshot_playwright(html_file_path, output_file_path):
    """screenshot med Playwright - browser stannar igång mellan anrop"""
    global page_instance
    
    try:
        start_time = time.time()
        abs_html_path = os.path.abspath(html_file_path)
        target_url = f"file://{abs_html_path}"
        
        page_instance.goto(target_url, wait_until='networkidle', timeout=10000)
        page_instance.screenshot(path=output_file_path, type='png')
        
        elapsed = time.time() - start_time
        print(f"screenshot: {elapsed:.1f}s")
        
        return True
        
    except Exception as e:
        print(f"Screenshot-fel: {e}")
        return False


def cleanup_browser():
    """Stäng browser vid avslut"""
    global playwright_instance, browser_instance, page_instance
    
    if page_instance:
        page_instance.close()
    if browser_instance:
        browser_instance.close()
    if playwright_instance:
        playwright_instance.stop()


def is_night_mode(current_hour):
    return NIGHT_MODE_START <= current_hour < NIGHT_MODE_END

    
def main():
    if epd_driver:
        epd = epd_driver.EPD()
        epd.init()
        epd.Clear()
    else:
        epd = None

    init_browser()

    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('dashboard_orig.html')
    
    cached_departures = []
    cached_events = []
    cached_weather = {'temp': '--', 'symbol': 'na'}
    last_data_fetch = 0
    last_calendar_fetch = 0
    
    try:
        while True:
            loop_start = time.time()
            now = datetime.datetime.now()
            
            if is_night_mode(now.hour):
                print(f"[{now.strftime('%H:%M')}] Nattläge - sover i {NIGHT_MODE_SLEEP}s...")
                if epd:
                    epd.sleep()
                time.sleep(NIGHT_MODE_SLEEP)
                continue

            start = time.time()
            print("Hämtar bussdata...")
            try:
                cached_departures, cached_stop_name = extract_board_data(
                    stop_area_gid=STOP_AREA_GID, 
                    filter_platforms=platform
                )
                print(f"Bussdata: {time.time()-start:.1f}s")
            except Exception as e: 
                print(f"Avgångsfel: {e}")

            if time.time() - last_calendar_fetch > CALENDAR_FETCH_INTERVAL or last_calendar_fetch == 0:
                start = time.time()
                print("Hämtar kalender...")
                try:
                    cached_events = get_calendar_events(ICS_URL)
                    print(f"Kalender: {time.time()-start:.1f}s")
                except Exception as e: 
                    print(f"Kalenderfel: {e}")
                last_calendar_fetch = time.time()

            if time.time() - last_data_fetch > DATA_FETCH_INTERVAL or last_data_fetch == 0:
                start = time.time()
                print("Hämtar väder...")
                try:
                    cached_weather = fetch_weather_data(lat=LATITUDE, lon=LONGITUDE)
                    print(f"Väder: {time.time()-start:.1f}s")
                except Exception as e: 
                    print(f"Väderfel: {e}")
                last_data_fetch = time.time()

            start = time.time()
            calendar_view = prepare_calendar_data(cached_events)
            
            dagar_sv = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
            manader_sv = ["Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
            dag_namn = dagar_sv[now.weekday()]
            manad_namn = f"{now.day} {manader_sv[now.month-1]}"
            sym_kod = cached_weather.get('symbol', '1')
            ikon_namn = get_icon_name(sym_kod, now.hour)
            
            start = time.time()
            print("Hämtar Spotify...")
            try:
                spotify_status = get_spotify_data()
                print(f"⏱️  Spotify: {time.time()-start:.1f}s")
            except Exception as e:
                print(f"Kunde inte hämta Spotify: {e}")
                spotify_status = None
                
            start = time.time()
            print(f"Renderar HTML...")
            
            html_content = template.render(
                hallplats_namn=cached_stop_name,
                datum_dag=dag_namn,
                datum_manad=manad_namn,
                klockslag=now.strftime("%H:%M"),
                vader_temp=cached_weather.get('temp', '--'),
                vader_symbol=cached_weather.get('symbol', '1'),
                vader_ikon=ikon_namn,
                kalender_dagar=calendar_view,
                avgangar=cached_departures,
                spotify=spotify_status
            )

            html_filename = "renderad_sida.html"
            image_filename = "display_buffer.png"

            with open(html_filename, "w", encoding='utf-8') as f:
                f.write(html_content)
            
            success = take_screenshot_playwright(html_filename, image_filename)
            
            if success and os.path.exists(image_filename):
                start = time.time()
                img = Image.open(image_filename)
                img_bw = img.convert("1")

                if epd:
                    buffer = epd.getbuffer(img_bw)
                    
                    if now.minute == 0 and now.second < 10:
                        print("Full refresh med Clear...")
                        epd.init()
                        epd.Clear()
                        epd.display(buffer)
                    else:
                        print("Uppdaterar display...")
                        epd.init_part()
                        epd.display(buffer)

                    epd.sleep()
                    print(f"display: {time.time()-start:.1f}s")
                else:
                    print(f"Simulering klar: {len(cached_departures)} bussar hittades. Bild sparad som {image_filename}")
            else:
                print("Kunde inte generera bild, hoppar över skärmuppdatering.")

            total_time = time.time() - loop_start
            print(f"total tid: {total_time:.1f}s\n")

            now_after_update = datetime.datetime.now()
            seconds_until_next_minute = 60 - now_after_update.second
            
            if seconds_until_next_minute < 1:
                seconds_until_next_minute += 60
            
            print(f"Väntar {seconds_until_next_minute}s till nästa minut...")
            time.sleep(seconds_until_next_minute)

    except KeyboardInterrupt:
        print("Avslutar...")
        cleanup_browser()
        if epd:
            epd.init()
            epd.Clear()
            epd.sleep()
    except Exception as e:
        cleanup_browser()
        traceback.print_exc()

if __name__ == "__main__":
    main()