import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv


load_dotenv()
client_id = os.environ.get("SPOTIFY_CLIENT_ID")
client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI")

def get_spotify_data():
    try:
        auth_manager = SpotifyOAuth(
            scope="user-read-currently-playing",
            cache_path=".spotify_cache",
            open_browser=False,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)

        current = sp.current_user_playing_track()

        if not current or not current.get('item') or not current.get('is_playing'):
            return None
        
        artist_name = current['item']['artists'][0]['name']

        track_name = current['item']['name']

        images = current['item']['album']['images']
        image_url = None
        
        for img in images:
            if img['width'] == 300:
                image_url = img['url']
                break
        
        if not image_url and images:
            image_url = images[0]['url']
        album_name = current['item']['album']['name']
        is_playing = current['is_playing']
        
        return {
            "artist": artist_name,
            "track": track_name,
            "album": album_name,
            "image": image_url,
            "is_playing": is_playing
        }

    except Exception as e:
        print(f"Spotify-fel: {e}")
        return None


if __name__ == "__main__":
    data = get_spotify_data()
    
    print(data)
