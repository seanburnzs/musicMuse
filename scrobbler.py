"""
Spotify scrobbler script that fetches recently played tracks and stores them in the database.
Can be set up as a scheduled task to keep listening history up to date.
"""
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables from .env
load_dotenv()

# Spotify credentials and scope
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
SCOPE = "user-read-recently-played"

# Database connection parameters
# Check for DATABASE_URL environment variable (Railway/production)
if "DATABASE_URL" in os.environ:
    # Parse the DATABASE_URL
    db_url = urlparse(os.environ["DATABASE_URL"])
    DB_PARAMS = {
        "dbname": db_url.path[1:],  # Remove leading slash
        "user": db_url.username,
        "password": db_url.password,
        "host": db_url.hostname,
        "port": db_url.port
    }
else:
    # Local development fallback
    DB_PARAMS = {
        "dbname": os.getenv("PGDATABASE", "musicmuse_db"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD"),
        "host": os.getenv("PGHOST", "localhost"),
        "port": os.getenv("PGPORT", 5432)
    }

# Initialize Spotipy client with OAuth
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope=SCOPE,
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI
))

def get_recently_played():
    """Fetch the most recent 50 tracks played by the user."""
    results = sp.current_user_recently_played(limit=50)
    return results.get("items", [])

def get_db_connection():
    """
    Establish a connection to the PostgreSQL database.
    Falls back to 'railway' database if the specified database doesn't exist in production.
    """
    try:
        return psycopg2.connect(**DB_PARAMS)
    except psycopg2.OperationalError as e:
        # If the specified database doesn't exist in production, fall back to 'railway'
        if "DATABASE_URL" in os.environ and "does not exist" in str(e):
            fallback_params = DB_PARAMS.copy()
            fallback_params["dbname"] = "railway"
            return psycopg2.connect(**fallback_params)
        raise

def get_or_create_artist(cur, artist_name):
    """Ensure an artist exists in the artists table and return its ID."""
    cur.execute("SELECT artist_id FROM artists WHERE artist_name = %s;", (artist_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute("INSERT INTO artists (artist_name) VALUES (%s) RETURNING artist_id;", (artist_name,))
        return cur.fetchone()[0]

def get_or_create_album(cur, album_name, artist_id):
    """Ensure an album exists in the albums table and return its ID."""
    cur.execute("SELECT album_id FROM albums WHERE album_name = %s AND artist_id = %s;", (album_name, artist_id))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute("INSERT INTO albums (album_name, artist_id) VALUES (%s, %s) RETURNING album_id;", (album_name, artist_id))
        return cur.fetchone()[0]

def get_or_create_track(cur, track_name, album_id):
    """Ensure a track exists in the tracks table and return its ID."""
    cur.execute("SELECT track_id FROM tracks WHERE track_name = %s AND album_id = %s;", (track_name, album_id))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute("INSERT INTO tracks (track_name, album_id) VALUES (%s, %s) RETURNING track_id;", (track_name, album_id))
        return cur.fetchone()[0]

def record_exists(cur, played_at, track_id):
    """
    Check if a listening_history record already exists.
    Uniqueness is based on the played_at timestamp and track_id.
    """
    query = """
        SELECT 1 FROM listening_history 
        WHERE timestamp = %s AND track_id = %s
        LIMIT 1;
    """
    cur.execute(query, (played_at, track_id))
    return cur.fetchone() is not None

def scrobble_recent_tracks():
    items = get_recently_played()
    conn = get_db_connection()
    cur = conn.cursor()

    inserted_count = 0
    for item in items:
        played_at_str = item.get("played_at")
        # Parse the played_at timestamp (Spotify returns ISO8601 format)
        try:
            played_at = datetime.strptime(played_at_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            played_at = datetime.strptime(played_at_str, "%Y-%m-%dT%H:%M:%SZ")
        
        track = item.get("track")
        if not track:
            continue

        # Extract track details
        track_name = track.get("name", "Unknown Track")
        album = track.get("album", {})
        album_name = album.get("name", "Unknown Album")
        artists = track.get("artists", [])
        artist_name = ", ".join([artist.get("name", "Unknown Artist") for artist in artists])
        # Use track duration as a proxy for ms_played since recently-played doesn't return actual ms_played
        ms_played = track.get("duration_ms", 0)

        # Default values for other fields
        platform = "Spotify"
        country = None
        reason_start = "scrobble"
        reason_end = "scrobble"
        shuffle = False
        skipped = False
        moods = None

        # Skip if essential info is unknown
        if track_name == "Unknown Track" or album_name == "Unknown Album" or artist_name == "Unknown Artist":
            continue

        # Insert normalized metadata into artists, albums, tracks
        artist_id = get_or_create_artist(cur, artist_name)
        album_id = get_or_create_album(cur, album_name, artist_id)
        track_id = get_or_create_track(cur, track_name, album_id)

        # Skip insertion if record already exists
        if record_exists(cur, played_at, track_id):
            continue

        # Insert into listening_history table using the foreign key (track_id)
        insert_query = """
            INSERT INTO listening_history (
                timestamp, platform, ms_played, country,
                track_id, reason_start, reason_end, shuffle,
                skipped, moods
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(insert_query, (
            played_at, platform, ms_played, country,
            track_id, reason_start, reason_end, shuffle,
            skipped, moods
        ))
        inserted_count += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {inserted_count} new scrobbles.")

if __name__ == "__main__":
    scrobble_recent_tracks()