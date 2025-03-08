import os
from flask import Flask, render_template, request
import psycopg2
from datetime import datetime, timedelta, date
from dotenv import load_dotenv  # DB credentials

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Local DB credentials
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME", "musicmuse_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS"),
    "host": "localhost",
    "port": 5432
}

# Utility function to get a DB connection
def get_db_connection():
    return psycopg2.connect(**DB_PARAMS)

# ----- TIME RANGE HELPERS -----
def get_date_range(range_key, custom_start=None, custom_end=None):
    """
    Returns a (start_date, end_date) tuple based on the chosen range_key.
    Also handles custom date ranges.
    """
    today = date.today()

    if range_key == "all_time":
        return (None, None)
    elif range_key == "this_week":
        # Last 7 days
        start = today - timedelta(days=7)
        end = today + timedelta(days=1)  # Include today
        return (start, end)
    elif range_key == "this_month":
        # Last 30 days
        start = today - timedelta(days=30)
        end = today + timedelta(days=1)  # Include today
        return (start, end)
    elif range_key == "this_year":
        # From January 1st of current year to today
        start = date(today.year, 1, 1)
        end = today + timedelta(days=1)  # Include today
        return (start, end)
    elif range_key.startswith("year_"):
        try:
            year_val = int(range_key.replace("year_", ""))
            start = date(year_val, 1, 1)
            end = date(year_val + 1, 1, 1)
            return (start, end)
        except ValueError:
            return (None, None)
    elif range_key == "custom" and custom_start and custom_end:
        try:
            # Parse the custom date strings to date objects
            start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
            end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
            # Add one day to end_date to include the end date in the range
            end_date = end_date + timedelta(days=1)
            return (start_date, end_date)
        except ValueError:
            # If there's an error parsing the dates, return None
            return (None, None)
    else:
        return (None, None)

# ----- HOME PAGE -----
@app.route("/")
def index():
    return render_template("index.html")

# ----- COMMON QUERY FUNCTION -----
def fetch_top_data(entity, time_range, time_unit, custom_start=None, custom_end=None):
    """
    Fetch top tracks, albums, or artists based on time range and time unit.
    """
    start_date, end_date = get_date_range(time_range, custom_start, custom_end)
    conn = get_db_connection()
    cur = conn.cursor()

    where_conditions = []
    params = []

    # Filtering out "Unknown" entries
    if entity == "tracks":
        where_conditions.append("t.track_name != 'Unknown Track'")
    if entity in ["tracks", "albums"]:
        where_conditions.append("a.album_name != 'Unknown Album'")
    if entity in ["tracks", "albums", "artists"]:
        where_conditions.append("ar.artist_name != 'Unknown Artist'")

    # Time filtering
    if start_date and end_date:
        where_conditions.append("lh.timestamp >= %s AND lh.timestamp < %s")
        params.extend([start_date, end_date])

    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

    # Use ROUND with 1 decimal place for hours
    time_divisor = 60 * 60 * 1000 if time_unit == "hours" else 60 * 1000
    decimal_places = 1 if time_unit == "hours" else 0
    time_label = "total_hours" if time_unit == "hours" else "total_minutes"

    if entity == "tracks":
        query = f"""
            SELECT t.track_name, ar.artist_name, 
                COUNT(*) FILTER (WHERE lh.ms_played >= 30000) AS total_streams, 
                ROUND(SUM(lh.ms_played) / {time_divisor}::numeric, {decimal_places}) AS {time_label}
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            JOIN artists ar ON a.artist_id = ar.artist_id
            {where_clause}
            GROUP BY t.track_name, ar.artist_name
            ORDER BY total_streams DESC
            LIMIT 20;
        """

    elif entity == "albums":
        query = f"""
            SELECT a.album_name, ar.artist_name, 
                   COUNT(*) FILTER (WHERE lh.ms_played >= 30000) AS total_streams, 
                   ROUND(SUM(lh.ms_played) / {time_divisor}::numeric, {decimal_places}) AS {time_label}
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            JOIN artists ar ON a.artist_id = ar.artist_id
            {where_clause}
            GROUP BY a.album_name, ar.artist_name
            ORDER BY total_streams DESC
            LIMIT 20;
        """
    elif entity == "artists":
        query = f"""
            SELECT ar.artist_name, 
                   COUNT(*) FILTER (WHERE lh.ms_played >= 30000) AS total_streams, 
                   ROUND(SUM(lh.ms_played) / {time_divisor}::numeric, {decimal_places}) AS {time_label}
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            JOIN artists ar ON a.artist_id = ar.artist_id
            {where_clause}
            GROUP BY ar.artist_name
            ORDER BY total_streams DESC
            LIMIT 20;
        """
    else:
        return []

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ----- TOP TRACKS -----
@app.route("/top_tracks", methods=["GET", "POST"])
def top_tracks():
    time_range = request.args.get("time_range", "all_time")
    time_unit = request.args.get("time_unit", "hours")
    custom_start = request.args.get("custom_start", None)
    custom_end = request.args.get("custom_end", None)
    
    rows = fetch_top_data("tracks", time_range, time_unit, custom_start, custom_end)
    
    return render_template(
        "top_tracks.html", 
        rows=rows, 
        selected_range=time_range, 
        time_unit=time_unit,
        custom_start=custom_start,
        custom_end=custom_end
    )

# ----- TOP ALBUMS -----
@app.route("/top_albums", methods=["GET", "POST"])
def top_albums():
    time_range = request.args.get("time_range", "all_time")
    time_unit = request.args.get("time_unit", "hours")
    custom_start = request.args.get("custom_start", None)
    custom_end = request.args.get("custom_end", None)
    
    rows = fetch_top_data("albums", time_range, time_unit, custom_start, custom_end)
    
    return render_template(
        "top_albums.html", 
        rows=rows, 
        selected_range=time_range, 
        time_unit=time_unit,
        custom_start=custom_start,
        custom_end=custom_end
    )

# ----- TOP ARTISTS -----
@app.route("/top_artists", methods=["GET", "POST"])
def top_artists():
    time_range = request.args.get("time_range", "all_time")
    time_unit = request.args.get("time_unit", "hours")
    custom_start = request.args.get("custom_start", None)
    custom_end = request.args.get("custom_end", None)
    
    rows = fetch_top_data("artists", time_range, time_unit, custom_start, custom_end)
    
    return render_template(
        "top_artists.html", 
        rows=rows, 
        selected_range=time_range, 
        time_unit=time_unit,
        custom_start=custom_start,
        custom_end=custom_end
    )

# ----- MUSIC MUSE -----
@app.route("/music_muse", methods=["GET", "POST"])
def music_muse():
    response = None
    suggestions = get_personalized_suggestions()
    
    if request.method == "POST":
        query_text = request.form.get("query")
        # Import MusicMuse class from music_muse.py
        from music_muse import MusicMuse
        muse = MusicMuse(DB_PARAMS)
        parsed, results = muse.execute_query(query_text)
        response = muse.format_response(parsed, results)
    
    return render_template("music_muse.html", response=response, suggestions=suggestions)

def get_personalized_suggestions():
    """
    Generate personalized query suggestions based on the user's listening history.
    Returns a list of suggestion dictionaries with 'text' and 'query' keys.
    """
    # These are default suggestions that will be shown to all users
    default_suggestions = [
        {
            "text": "What artists do I listen to the most?",
            "query": "What artists do I listen to the most?"
        },
        {
            "text": "Which albums do I listen to the most?",
            "query": "Which albums do I listen to the most?"
        },
        {
            "text": "What songs do I listen to the most?",
            "query": "What songs do I listen to the most?"
        },
        {
            "text": "Which artists do I listen to the most on Sundays?",
            "query": "Which artists do I listen to the most on Sundays?"
        },
        {
            "text": "What are my top tracks in the Summer?",
            "query": "What are my top tracks in the Summer?"
        }
    ]

    return default_suggestions

if __name__ == "__main__":
    app.run(debug=True)
