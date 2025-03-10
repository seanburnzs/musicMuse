import os
import json
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import dotenv

def load_spotify_data(json_file_path, db_conn_params, cur, user_id):
    """
    Reads a single Spotify JSON file (json_file_path) and upserts it into
    the database using cursor (cur). This function does not commit—commit once
    at the end of main loop for efficiency.
    
    Now includes user_id parameter to associate data with a specific user.
    """

    # Read JSON data
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Temporary in-memory lists
    artist_batch = []
    album_batch = []
    track_batch = []
    listening_batch = []

    for entry in data:
        ts_str = entry.get("ts", None)
        if not ts_str:
            continue
        dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")

        platform = entry.get("platform", "")[:50]
        ms_played = entry.get("ms_played", 0)
        country = entry.get("conn_country", "")
        track_name = entry.get("master_metadata_track_name", "Unknown Track")
        track_name = track_name if track_name else "Unknown Track"
        album_name = entry.get("master_metadata_album_album_name", "Unknown Album")
        album_name = album_name if album_name else "Unknown Album"
        artist_name = entry.get("master_metadata_album_artist_name", "Unknown Artist")
        artist_name = artist_name if artist_name else "Unknown Artist"
        reason_start = entry.get("reason_start", "")[:50]
        reason_end = entry.get("reason_end", "")
        reason_end = reason_end[:50] if reason_end else ""
        shuffle = entry.get("shuffle", False)
        skipped = entry.get("skipped", False)
        moods = ""  # assign or parse

        # Collect batches
        artist_batch.append((artist_name,))
        album_batch.append((album_name, artist_name))
        track_batch.append((track_name, album_name, artist_name))
        listening_batch.append({
            "timestamp": dt,
            "platform": platform,
            "ms_played": ms_played,
            "country": country,
            "artist_name": artist_name,
            "album_name": album_name,
            "track_name": track_name,
            "reason_start": reason_start,
            "reason_end": reason_end,
            "shuffle": shuffle,
            "skipped": skipped,
            "moods": moods,
            "user_id": user_id  # Add user_id to each record
        })

    # 1) Insert or ignore duplicate artists
    artist_insert_sql = """
        INSERT INTO artists (artist_name)
        VALUES %s
        ON CONFLICT (artist_name) DO NOTHING
    """
    unique_artists = list(set(artist_batch))
    execute_values(cur, artist_insert_sql, unique_artists)

    # Build artist map
    cur.execute("SELECT artist_id, artist_name FROM artists;")
    artist_rows = cur.fetchall()
    artist_map = {row[1]: row[0] for row in artist_rows}

    # 2) Insert or ignore duplicate albums
    album_insert_sql = """
        INSERT INTO albums (album_name, artist_id)
        VALUES %s
        ON CONFLICT (album_name, artist_id) DO NOTHING
    """
    album_temp = set()
    for (alb_name, art_name) in album_batch:
        a_id = artist_map.get(art_name, None)
        if a_id:
            album_temp.add((alb_name, a_id))
    album_temp_list = list(album_temp)
    execute_values(cur, album_insert_sql, album_temp_list)

    # Build album map
    cur.execute("SELECT album_id, album_name, artist_id FROM albums;")
    album_rows = cur.fetchall()
    album_map = {(row[1], row[2]): row[0] for row in album_rows}

    # 3) Insert or ignore duplicate tracks
    track_insert_sql = """
        INSERT INTO tracks (track_name, album_id)
        VALUES %s
        ON CONFLICT (track_name, album_id) DO NOTHING
    """
    track_temp = set()
    for (trk_name, alb_name, art_name) in track_batch:
        a_id = artist_map.get(art_name, None)
        alb_id = album_map.get((alb_name, a_id), None)
        if alb_id:
            track_temp.add((trk_name, alb_id))
    track_temp_list = list(track_temp)
    execute_values(cur, track_insert_sql, track_temp_list)

    # Build track map
    cur.execute("SELECT track_id, track_name, album_id FROM tracks;")
    track_rows = cur.fetchall()
    track_map = {(row[1], row[2]): row[0] for row in track_rows}

    # 4) Insert listening records
    history_insert_sql = """
        INSERT INTO listening_history (
            timestamp, platform, ms_played, country,
            track_id, reason_start, reason_end, shuffle,
            skipped, moods, user_id
        )
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    final_listening_records = []
    for row in listening_batch:
        a_id = artist_map.get(row["artist_name"], None)
        alb_id = album_map.get((row["album_name"], a_id), None)
        if not alb_id:
            continue
        t_id = track_map.get((row["track_name"], alb_id), None)
        if not t_id:
            continue

        final_listening_records.append((
            row["timestamp"],
            row["platform"],
            row["ms_played"],
            row["country"],
            t_id,
            row["reason_start"],
            row["reason_end"],
            row["shuffle"],
            row["skipped"],
            row["moods"],
            row["user_id"]  # Include user_id in the insert
        ))

    execute_values(cur, history_insert_sql, final_listening_records)


if __name__ == "__main__":
    # Load environment variables
    dotenv.load_dotenv()
    
    # Database parameters for local DB
    db_params = {
        "dbname": os.getenv("DB_NAME", "musicmuse_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASS"),
        "host": "localhost",
        "port": 5432
    }

    # Connect to PostgreSQL once
    conn = psycopg2.connect(**db_params)
    conn.autocommit = False
    cur = conn.cursor()
    
    # Get the user ID for the new user
    user_id = int(input("Enter the user ID for this data: "))

    # Directory containing all the JSON files
    folder_path = input("Enter the path to the directory containing JSON files (e.g., streaming_data_new): ")

    # Loop over each file in that directory
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            full_path = os.path.join(folder_path, filename)
            print(f"Processing file: {full_path}")
            load_spotify_data(full_path, db_params, cur, user_id)

    # Commit once at the end for efficiency
    conn.commit()
    cur.close()
    conn.close()
    print("All files processed successfully.")