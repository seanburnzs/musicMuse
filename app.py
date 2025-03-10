import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from datetime import datetime, timedelta, date
from dotenv import load_dotenv  # DB credentials
from urllib.parse import urlparse
import json
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from music_muse import MusicMuse

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_key_for_testing")  # Set a secret key for sessions

# File upload configuration
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
ALLOWED_EXTENSIONS = {'json', 'jpg', 'jpeg', 'png', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database connection parameters
# Check for DATABASE_URL environment variable (Railway provides this)
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
        "dbname": "musicmuse_db",
        "user": "postgres",  # Update with your local user
        "password": os.getenv("DB_PASS", ""),
        "host": "localhost",
        "port": "5432"
    }

# Utility function to get a DB connection
def get_db_connection():
    return psycopg2.connect(**DB_PARAMS)

# ----- TIME RANGE HELPERS -----
def get_date_range(range_key, custom_start=None, custom_end=None):
    """
    Returns a tuple (sql_where_clause, params_list) for filtering by date range.
    """
    today = date.today()
    
    # Initialize empty params list
    params = []
    
    if range_key == "all_time":
        return ("", params)
    elif range_key == "this_week":
        # Last 7 days
        start = today - timedelta(days=7)
        end = today + timedelta(days=1)  # Include today
        return ("AND lh.timestamp >= %s AND lh.timestamp < %s", [start, end])
    elif range_key == "this_month":
        # Last 30 days
        start = today - timedelta(days=30)
        end = today + timedelta(days=1)  # Include today
        return ("AND lh.timestamp >= %s AND lh.timestamp < %s", [start, end])
    elif range_key == "this_year":
        # From January 1st of current year to today
        start = date(today.year, 1, 1)
        end = today + timedelta(days=1)  # Include today
        return ("AND lh.timestamp >= %s AND lh.timestamp < %s", [start, end])
    elif range_key.startswith("year_"):
        try:
            year_val = int(range_key.replace("year_", ""))
            start = date(year_val, 1, 1)
            end = date(year_val + 1, 1, 1)
            return ("AND lh.timestamp >= %s AND lh.timestamp < %s", [start, end])
        except ValueError:
            return ("", params)
    elif range_key == "custom" and custom_start and custom_end:
        try:
            # Parse the custom date strings to date objects
            start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
            end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
            # Add one day to end_date to include the end date in the range
            end_date = end_date + timedelta(days=1)
            return ("AND lh.timestamp >= %s AND lh.timestamp < %s", [start_date, end_date])
        except ValueError:
            # If there's an error parsing the dates, return empty
            return ("", params)
    elif range_key.startswith("event_"):
        # Handle life event time ranges
        try:
            event_id = int(range_key.replace("event_", ""))
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Get the event dates
            cur.execute("""
                SELECT start_date, end_date
                FROM user_events
                WHERE event_id = %s AND user_id = %s
            """, (event_id, get_current_user_id()))
            
            event = cur.fetchone()
            cur.close()
            conn.close()
            
            if event:
                start_date = event[0]
                # If end_date is None (ongoing event), use today
                end_date = event[1] if event[1] else today + timedelta(days=1)
                return ("AND lh.timestamp >= %s AND lh.timestamp < %s", [start_date, end_date])
        except (ValueError, TypeError):
            pass
        
        return ("", params)
    else:
        return ("", params)

# ----- HOME PAGE -----
@app.route("/")
def index():
    return render_template("index.html")

# ----- COMMON QUERY FUNCTION -----
def fetch_top_data(entity, time_range, time_unit, custom_start=None, custom_end=None, limit=20, offset=0):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get date range
    date_filter, date_params = get_date_range(time_range, custom_start, custom_end)
    
    # Create params list with user_id first
    user_id = get_current_user_id()
    params = [user_id]
    
    # Add date params if they exist
    params.extend(date_params)
    
    # Build query based on entity type
    if entity == "artists":
        query = """
            SELECT a.artist_name as name, COUNT(*) as total_streams, 
                   ROUND(SUM(lh.ms_played) / {divisor}, 2) as total_time
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums al ON t.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            WHERE lh.user_id = %s
            AND a.artist_name NOT LIKE 'Unknown%%'
            AND a.artist_name != ''
            """ + date_filter + """
            GROUP BY a.artist_name
            ORDER BY total_streams DESC
            LIMIT %s OFFSET %s
        """
    elif entity == "albums":
        query = """
            SELECT al.album_name as name, a.artist_name as artist_name, COUNT(*) as total_streams, 
                   ROUND(SUM(lh.ms_played) / {divisor}, 2) as total_time
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums al ON t.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            WHERE lh.user_id = %s
            AND al.album_name NOT LIKE 'Unknown%%'
            AND a.artist_name NOT LIKE 'Unknown%%'
            AND al.album_name != ''
            AND a.artist_name != ''
            """ + date_filter + """
            GROUP BY al.album_name, a.artist_name
            ORDER BY total_streams DESC
            LIMIT %s OFFSET %s
        """
    else:  # tracks
        query = """
            SELECT t.track_name as name, a.artist_name as artist_name, COUNT(*) as total_streams, 
                   ROUND(SUM(lh.ms_played) / {divisor}, 2) as total_time
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums al ON t.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            WHERE lh.user_id = %s
            AND t.track_name NOT LIKE 'Unknown%%'
            AND a.artist_name NOT LIKE 'Unknown%%'
            AND t.track_name != ''
            AND a.artist_name != ''
            """ + date_filter + """
            GROUP BY t.track_name, a.artist_name
            ORDER BY total_streams DESC
            LIMIT %s OFFSET %s
        """
    
    # Set divisor based on time unit
    divisor = "3600000.0" if time_unit == "hours" else "60000.0"
    query = query.format(divisor=divisor)
    
    # Add limit and offset to params
    params.append(limit)
    params.append(offset)
    
    # Execute query
    cur.execute(query, params)
    rows = cur.fetchall()
    
    conn.close()
    return rows

# ----- TOP ITEMS -----
@app.route("/top", methods=["GET"])
def top_items():
    """Combined view for top tracks, albums, and artists"""
    item_type = request.args.get("type", "tracks")
    time_range = request.args.get("time_range", "all_time")
    time_unit = request.args.get("time_unit", "hours")
    custom_start = request.args.get("custom_start", None)
    custom_end = request.args.get("custom_end", None)
    
    # Validate item_type
    if item_type not in ["tracks", "albums", "artists"]:
        item_type = "tracks"
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    # Modify the fetch_top_data function to include pagination
    rows = fetch_top_data(
        item_type, 
        time_range, 
        time_unit, 
        custom_start, 
        custom_end,
        limit=per_page,
        offset=offset
    )
    
    # Return JSON if requested (for infinite scrolling)
    if request.args.get('format') == 'json':
        return jsonify({
            'items': rows,
            'type': item_type,
            'page': page
        })
    
    # Get user events for the filter dropdown
    user_events = get_user_events_for_current_user()
    
    return render_template(
        "top_items.html", 
        rows=rows, 
        selected_type=item_type,
        selected_range=time_range, 
        time_unit=time_unit,
        custom_start=custom_start,
        custom_end=custom_end,
        user_events=user_events
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
        
        # Get the current user ID
        user_id = get_current_user_id()
        
        # Add debug logging
        logging.info(f"Creating MusicMuse with user_id: {user_id}")
        
        # Create MusicMuse instance with user_id
        muse = MusicMuse(DB_PARAMS, user_id)
        
        # Execute the query
        parsed, results = muse.execute_query(query_text)
        
        # Format the response
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

# ----- USER PROFILE -----
@app.route("/profile/<username>")
def user_profile(username):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get user data from database
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    
    if not user:
        conn.close()
        flash("User not found")
        return redirect(url_for("index"))
    
    user_id = user[0]
    current_user_id = get_current_user_id()
    
    # Check if current user is following this user
    is_following = False
    if current_user_id:
        cur.execute(
            "SELECT 1 FROM user_follows WHERE follower_id = %s AND followed_id = %s",
            (current_user_id, user_id)
        )
        is_following = cur.fetchone() is not None
    
    # Get follower and following counts
    cur.execute("SELECT COUNT(*) FROM user_follows WHERE followed_id = %s", (user_id,))
    followers_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM user_follows WHERE follower_id = %s", (user_id,))
    following_count = cur.fetchone()[0]
    
    # Get total streams and hours
    cur.execute(
        """
        SELECT COUNT(*), ROUND(SUM(ms_played) / 3600000.0, 2)
        FROM listening_history
        WHERE user_id = %s
        """,
        (user_id,)
    )
    total_stats = cur.fetchone()
    total_streams = total_stats[0] if total_stats[0] else 0
    total_hours = total_stats[1] if total_stats[1] else 0
    
    # Check if user has customized their Hall of Fame
    cur.execute(
        "SELECT COUNT(*) FROM user_hall_of_fame WHERE user_id = %s",
        (user_id,)
    )
    has_custom_hof = cur.fetchone()[0] > 0
    
    # Get Hall of Fame items
    hall_of_fame = {
        'artists': [],
        'albums': [],
        'tracks': []
    }
    
    if has_custom_hof:
        # Get custom Hall of Fame items
        for item_type in ['artist', 'album', 'track']:
            cur.execute(
                """
                SELECT uhf.item_id, position FROM user_hall_of_fame uhf
                WHERE uhf.user_id = %s AND uhf.item_type = %s
                ORDER BY position
                """,
                (user_id, item_type)
            )
            custom_items = cur.fetchall()
            
            for item_id, position in custom_items:
                if item_type == 'artist':
                    cur.execute(
                        """
                        SELECT a.artist_id, a.artist_name, a.image_url, 
                               COUNT(*) as total_streams, 
                               ROUND(SUM(lh.ms_played) / 3600000.0, 2) as total_hours
                        FROM artists a
                        JOIN albums al ON a.artist_id = al.artist_id
                        JOIN tracks t ON al.album_id = t.album_id
                        JOIN listening_history lh ON t.track_id = lh.track_id
                        WHERE a.artist_id = %s AND lh.user_id = %s
                        AND a.artist_name NOT LIKE 'Unknown%%'
                        AND a.artist_name != ''
                        GROUP BY a.artist_id, a.artist_name, a.image_url
                        """,
                        (item_id, user_id)
                    )
                    artist = cur.fetchone()
                    if artist:
                        hall_of_fame['artists'].append(artist)
                
                elif item_type == 'album':
                    cur.execute(
                        """
                        SELECT al.album_id, al.album_name, a.artist_name, al.image_url, 
                               COUNT(*) as total_streams, 
                               ROUND(SUM(lh.ms_played) / 3600000.0, 2) as total_hours
                        FROM albums al
                        JOIN artists a ON al.artist_id = a.artist_id
                        JOIN tracks t ON al.album_id = t.album_id
                        JOIN listening_history lh ON t.track_id = lh.track_id
                        WHERE al.album_id = %s AND lh.user_id = %s
                        AND al.album_name NOT LIKE 'Unknown%%'
                        AND a.artist_name NOT LIKE 'Unknown%%'
                        AND al.album_name != ''
                        AND a.artist_name != ''
                        GROUP BY al.album_id, al.album_name, a.artist_name, al.image_url
                        """,
                        (item_id, user_id)
                    )
                    album = cur.fetchone()
                    if album:
                        hall_of_fame['albums'].append(album)
                
                else:  # track
                    cur.execute(
                        """
                        SELECT t.track_id, t.track_name, a.artist_name, al.image_url, 
                               COUNT(*) as total_streams, 
                               ROUND(SUM(lh.ms_played) / 3600000.0, 2) as total_hours
                        FROM tracks t
                        JOIN albums al ON t.album_id = al.album_id
                        JOIN artists a ON al.artist_id = a.artist_id
                        JOIN listening_history lh ON t.track_id = lh.track_id
                        WHERE t.track_id = %s AND lh.user_id = %s
                        AND t.track_name NOT LIKE 'Unknown%%'
                        AND a.artist_name NOT LIKE 'Unknown%%'
                        AND t.track_name != ''
                        AND a.artist_name != ''
                        GROUP BY t.track_id, t.track_name, a.artist_name, al.image_url
                        """,
                        (item_id, user_id)
                    )
                    track = cur.fetchone()
                    if track:
                        hall_of_fame['tracks'].append(track)
    else:
        # Get default top items for Hall of Fame
        hall_of_fame['artists'] = get_top_items(cur, "artists", user_id, limit=3)
        hall_of_fame['albums'] = get_top_items(cur, "albums", user_id, limit=3)
        hall_of_fame['tracks'] = get_top_items(cur, "tracks", user_id, limit=3)
    
    # Get recent items (last 30 days)
    recents = {
        'artists': get_top_items(cur, "artists", user_id, time_range="this_month", limit=3),
        'albums': get_top_items(cur, "albums", user_id, time_range="this_month", limit=3),
        'tracks': get_top_items(cur, "tracks", user_id, time_range="this_month", limit=3)
    }
    
    # Check if events are visible to current user
    events_visible = True
    cur.execute(
        "SELECT events_privacy FROM user_settings WHERE user_id = %s",
        (user_id,)
    )
    privacy_setting = cur.fetchone()
    
    if privacy_setting:
        events_privacy = privacy_setting[0]
        
        if events_privacy == 'private':
            events_visible = (current_user_id == user_id)
        elif events_privacy == 'friends':
            if current_user_id != user_id:
                cur.execute(
                    """
                    SELECT 1 FROM user_follows 
                    WHERE follower_id = %s AND followed_id = %s
                    """,
                    (user_id, current_user_id)
                )
                events_visible = cur.fetchone() is not None
    
    # Get user events if visible
    events = []
    if events_visible:
        events = get_user_events(cur, user_id)
    
    conn.close()
    
    return render_template(
        "user_profile.html",
        username=username,
        hall_of_fame=hall_of_fame,
        recents=recents,
        events=events,
        events_visible=events_visible,
        is_following=is_following,
        followers_count=followers_count,
        following_count=following_count,
        total_streams=total_streams,
        total_hours=total_hours
    )

def get_top_items(cur, entity_type, user_id, time_range="all_time", limit=3):
    # Get date range
    date_filter, date_params = get_date_range(time_range)
    
    # Create params list with user_id first
    params = [user_id]
    
    # Add date params if they exist
    params.extend(date_params)
    
    if entity_type == "artists":
        query = """
            SELECT a.artist_id, a.artist_name as name, a.image_url, COUNT(*) as total_streams, 
                   ROUND(SUM(lh.ms_played) / 3600000.0, 2) as total_hours
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums al ON t.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            WHERE lh.user_id = %s
            AND a.artist_name NOT LIKE 'Unknown%%'
            AND a.artist_name != ''
            """ + date_filter + """
            GROUP BY a.artist_id, a.artist_name, a.image_url
            ORDER BY total_streams DESC
            LIMIT %s
        """
    elif entity_type == "albums":
        query = """
            SELECT al.album_id, al.album_name as name, a.artist_name as artist_name, al.image_url, 
                   COUNT(*) as total_streams, 
                   ROUND(SUM(lh.ms_played) / 3600000.0, 2) as total_hours
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums al ON t.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            WHERE lh.user_id = %s
            AND al.album_name NOT LIKE 'Unknown%%'
            AND a.artist_name NOT LIKE 'Unknown%%'
            AND al.album_name != ''
            AND a.artist_name != ''
            """ + date_filter + """
            GROUP BY al.album_id, al.album_name, a.artist_name, al.image_url
            ORDER BY total_streams DESC
            LIMIT %s
        """
    else:  # tracks
        query = """
            SELECT t.track_id, t.track_name as name, a.artist_name as artist_name, al.image_url, 
                   COUNT(*) as total_streams, 
                   ROUND(SUM(lh.ms_played) / 3600000.0, 2) as total_hours
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums al ON t.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            WHERE lh.user_id = %s
            AND t.track_name NOT LIKE 'Unknown%%'
            AND a.artist_name NOT LIKE 'Unknown%%'
            AND t.track_name != ''
            AND a.artist_name != ''
            """ + date_filter + """
            GROUP BY t.track_id, t.track_name, a.artist_name, al.image_url
            ORDER BY total_streams DESC
            LIMIT %s
        """
    
    params.append(limit)
    cur.execute(query, params)
    return cur.fetchall()

def get_user_events(cur, user_id):
    """Get all events for a user"""
    query = """
        SELECT event_id, name, start_date, end_date, description, category, color
        FROM user_events
        WHERE user_id = %s
        ORDER BY start_date DESC;
    """
    cur.execute(query, (user_id,))
    return cur.fetchall()

# ----- PROFILE COMPARISON -----
@app.route("/compare", methods=["GET", "POST"])
def compare_profiles():
    user1 = request.args.get("user1")
    user2 = request.args.get("user2")
    time_range = request.args.get("time_range", "all_time")
    custom_start = request.args.get("custom_start")
    custom_end = request.args.get("custom_end")
    
    # If no users specified, show selection form
    if not user1 or not user2:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users ORDER BY username")
        users = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return render_template("compare_select.html", users=users)
    
    # Get comparison data
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if users exist
    cur.execute("SELECT user_id FROM users WHERE username = %s", (user1,))
    user1_id = cur.fetchone()
    cur.execute("SELECT user_id FROM users WHERE username = %s", (user2,))
    user2_id = cur.fetchone()
    
    if not user1_id or not user2_id:
        cur.close()
        conn.close()
        return render_template("error.html", message="One or both users not found")
    
    user1_id = user1_id[0]
    user2_id = user2_id[0]
    
    # Get date range for the selected time range
    date_filter, date_params = get_date_range(time_range, custom_start, custom_end)
    start_date = date_params[0] if date_params else None
    end_date = date_params[1] if len(date_params) > 1 else None
    
    # Get comparison metrics
    metrics = get_comparison_metrics(cur, user1_id, user2_id, start_date, end_date)
    
    # Get top genres
    user1_genres = get_top_genres(cur, user1_id, start_date, end_date, limit=5)
    user2_genres = get_top_genres(cur, user2_id, start_date, end_date, limit=5)
    
    cur.close()
    conn.close()
    
    return render_template(
        "compare_profiles.html",
        user1=user1,
        user2=user2,
        metrics=metrics,
        user1_genres=user1_genres,
        user2_genres=user2_genres,
        selected_range=time_range,
        custom_start=custom_start,
        custom_end=custom_end
    )

def get_comparison_metrics(cur, user1_id, user2_id, start_date=None, end_date=None):
    """Get comparison metrics for two users"""
    metrics = {}
    
    # Build WHERE clause for time filtering
    where_time = ""
    params_time = []
    if start_date and end_date:
        where_time = "AND lh.timestamp >= %s AND lh.timestamp < %s"
        params_time = [start_date, end_date]
    
    # Total streams
    query = f"""
        SELECT COUNT(*) FILTER (WHERE ms_played >= 30000)
        FROM listening_history lh
        WHERE lh.user_id = %s {where_time};
    """
    
    cur.execute(query, [user1_id] + params_time)
    metrics["total_streams_1"] = cur.fetchone()[0]
    
    cur.execute(query, [user2_id] + params_time)
    metrics["total_streams_2"] = cur.fetchone()[0]
    
    # Total listening time (hours)
    query = f"""
        SELECT ROUND(SUM(ms_played) / (60 * 60 * 1000)::numeric, 1)
        FROM listening_history lh
        WHERE lh.user_id = %s {where_time};
    """
    
    cur.execute(query, [user1_id] + params_time)
    metrics["total_hours_1"] = cur.fetchone()[0] or 0
    
    cur.execute(query, [user2_id] + params_time)
    metrics["total_hours_2"] = cur.fetchone()[0] or 0
    
    # Unique tracks count
    query = f"""
        SELECT COUNT(DISTINCT lh.track_id)
        FROM listening_history lh
        WHERE lh.user_id = %s {where_time};
    """
    
    cur.execute(query, [user1_id] + params_time)
    metrics["unique_tracks_1"] = cur.fetchone()[0]
    
    cur.execute(query, [user2_id] + params_time)
    metrics["unique_tracks_2"] = cur.fetchone()[0]
    
    # Unique albums count
    query = f"""
        SELECT COUNT(DISTINCT al.album_id)
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        WHERE lh.user_id = %s {where_time};
    """
    
    cur.execute(query, [user1_id] + params_time)
    metrics["unique_albums_1"] = cur.fetchone()[0]
    
    cur.execute(query, [user2_id] + params_time)
    metrics["unique_albums_2"] = cur.fetchone()[0]
    
    # Unique artists count
    query = f"""
        SELECT COUNT(DISTINCT ar.artist_id)
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists ar ON al.artist_id = ar.artist_id
        WHERE lh.user_id = %s {where_time};
    """
    
    cur.execute(query, [user1_id] + params_time)
    metrics["unique_artists_1"] = cur.fetchone()[0]
    
    cur.execute(query, [user2_id] + params_time)
    metrics["unique_artists_2"] = cur.fetchone()[0]
    
    # Obscurity score (based on average track popularity)
    query = f"""
        SELECT 100 - AVG(t.popularity)
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        WHERE lh.user_id = %s {where_time};
    """
    
    cur.execute(query, [user1_id] + params_time)
    result = cur.fetchone()[0]
    metrics["obscurity_score_1"] = round(result, 1) if result is not None else 0
    
    cur.execute(query, [user2_id] + params_time)
    result = cur.fetchone()[0]
    metrics["obscurity_score_2"] = round(result, 1) if result is not None else 0
    
    return metrics

def get_top_genres(cur, user_id, start_date=None, end_date=None, limit=5):
    """Get top genres for a user"""
    where_time = ""
    params = [user_id]
    
    if start_date and end_date:
        where_time = "AND lh.timestamp >= %s AND lh.timestamp < %s"
        params.extend([start_date, end_date])
    
    query = f"""
        SELECT g.genre_name, COUNT(*) as count
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN track_genres tg ON t.track_id = tg.track_id
        JOIN genres g ON tg.genre_id = g.genre_id
        WHERE lh.user_id = %s {where_time}
        GROUP BY g.genre_name
        ORDER BY count DESC
        LIMIT %s;
    """
    
    params.append(limit)
    cur.execute(query, params)
    return cur.fetchall()

# ----- USER IMPERSONATION -----
@app.route("/impersonate", methods=["POST"])
def impersonate_user():
    """Set the impersonated user in the session"""
    username = request.form.get("username")
    redirect_to = request.form.get("redirect_to", "/")
    
    if username:
        # Check if user exists
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            # Store impersonation in session
            session["impersonating"] = {
                "username": username,
                "user_id": user[0]
            }
            # Force a refresh by redirecting to the current page
            return redirect(redirect_to)
        else:
            flash(f"User '{username}' not found", "error")
            return redirect(redirect_to)
    else:
        # Clear impersonation
        if "impersonating" in session:
            del session["impersonating"]
        
        # Force a refresh by redirecting to the current page
        return redirect(redirect_to)

# Modify existing routes to support impersonation
def get_current_user_id():
    """Get the current user ID (real or impersonated)"""
    if "impersonating" in session:
        return session["impersonating"]["user_id"]
    # Check if user is logged in
    if "user_id" in session:
        return session["user_id"]
    # Return a default user ID if not logged in
    return 1  # Default user ID

# Helper function to get all usernames for the impersonation dropdown
def get_all_usernames():
    """Get all usernames for the impersonation dropdown"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM users ORDER BY username")
    usernames = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return usernames

# Make the function available to templates
app.jinja_env.globals.update(get_all_usernames=get_all_usernames)

# ----- LIFE EVENTS -----
@app.route("/events", methods=["GET"])
def view_events():
    """View all life events for the current user"""
    user_id = get_current_user_id()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all events for the user
    cur.execute("""
        SELECT event_id, name, start_date, end_date, description, category, color
        FROM user_events
        WHERE user_id = %s
        ORDER BY start_date DESC
    """, (user_id,))
    
    events = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template("events.html", events=events)

@app.route("/events/new", methods=["GET", "POST"])
def new_event():
    """Create a new life event"""
    if request.method == "POST":
        user_id = get_current_user_id()
        name = request.form.get("name")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date") or None
        description = request.form.get("description")
        category = request.form.get("category")
        color = request.form.get("color", "#5c6bc0")
        
        if not name or not start_date:
            flash("Name and start date are required", "error")
            return redirect(url_for("new_event"))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO user_events (user_id, name, start_date, end_date, description, category, color)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, name, start_date, end_date, description, category, color))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return redirect(url_for("view_events"))
    
    # GET request - show the form
    return render_template("event_form.html", event=None)

@app.route("/events/edit/<int:event_id>", methods=["GET", "POST"])
def edit_event(event_id):
    """Edit an existing life event"""
    user_id = get_current_user_id()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if event exists and belongs to the user
    cur.execute("""
        SELECT event_id, name, start_date, end_date, description, category, color
        FROM user_events
        WHERE event_id = %s AND user_id = %s
    """, (event_id, user_id))
    
    event = cur.fetchone()
    
    if not event:
        cur.close()
        conn.close()
        flash("Event not found", "error")
        return redirect(url_for("view_events"))
    
    if request.method == "POST":
        name = request.form.get("name")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date") or None
        description = request.form.get("description")
        category = request.form.get("category")
        color = request.form.get("color", "#5c6bc0")
        
        if not name or not start_date:
            flash("Name and start date are required", "error")
            return redirect(url_for("edit_event", event_id=event_id))
        
        cur.execute("""
            UPDATE user_events
            SET name = %s, start_date = %s, end_date = %s, description = %s, category = %s, color = %s
            WHERE event_id = %s AND user_id = %s
        """, (name, start_date, end_date, description, category, color, event_id, user_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return redirect(url_for("view_events"))
    
    # GET request - show the form with event data
    cur.close()
    conn.close()
    
    return render_template("event_form.html", event=event)

@app.route("/events/delete/<int:event_id>", methods=["POST"])
def delete_event(event_id):
    """Delete a life event"""
    user_id = get_current_user_id()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if event exists and belongs to the user
    cur.execute("""
        SELECT 1 FROM user_events
        WHERE event_id = %s AND user_id = %s
    """, (event_id, user_id))
    
    if not cur.fetchone():
        cur.close()
        conn.close()
        flash("Event not found", "error")
        return redirect(url_for("view_events"))
    
    # Delete the event
    cur.execute("DELETE FROM user_events WHERE event_id = %s", (event_id,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    
    # Get the username for the redirect
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
    username = cur.fetchone()[0]
    cur.close()
    conn.close()
    
    # Redirect to the user's profile
    return redirect(url_for("user_profile", username=username))

def get_user_events_for_current_user():
    """Get all events for the current user"""
    user_id = get_current_user_id()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT event_id, name, start_date, end_date, description, category, color
        FROM user_events
        WHERE user_id = %s
        ORDER BY start_date DESC
    """, (user_id,))
    
    events = cur.fetchall()
    cur.close()
    conn.close()
    
    return events

# Add a profile route
@app.route("/profile")
def profile():
    """Redirect to the current user's profile"""
    # Get the current username
    conn = get_db_connection()
    cur = conn.cursor()
    user_id = get_current_user_id()
    cur.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        return redirect(url_for('user_profile', username=user[0]))
    else:
        # Fallback to a default user if needed
        return redirect(url_for('user_profile', username="default_user"))

# Add a compare route shortcut
@app.route("/compare_shortcut")
def compare_shortcut():
    """Shortcut to the compare profiles page"""
    return redirect(url_for('compare_profiles'))

# User authentication routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if user exists and password is correct
        cur.execute("SELECT user_id, password_hash FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        
        if user and check_password_hash(user[1], password):
            # Set session variables
            session["user_id"] = user[0]
            session["username"] = username
            
            # Clear any impersonation
            if "impersonating" in session:
                del session["impersonating"]
            
            conn.close()
            return redirect(url_for("index"))
        else:
            conn.close()
            flash("Invalid username or password")
            return render_template("login.html")
    
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if username or email already exists
        cur.execute("SELECT user_id FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cur.fetchone()
        
        if existing_user:
            conn.close()
            flash("Username or email already exists")
            return render_template("signup.html")
        
        # Create new user
        password_hash = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (%s, %s, %s, NOW()) RETURNING user_id",
            (username, email, password_hash)
        )
        user_id = cur.fetchone()[0]
        
        # Create default privacy settings
        cur.execute(
            "INSERT INTO user_settings (user_id, impersonation_privacy, events_privacy) VALUES (%s, 'everyone', 'everyone')",
            (user_id,)
        )
        
        conn.commit()
        conn.close()
        
        # Log user in
        session["user_id"] = user_id
        session["username"] = username
        
        return redirect(url_for("index"))
    
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# Following system
@app.route("/follow/<username>", methods=["POST"])
def follow_user(username):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    follower_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get user_id of the user to follow
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    
    if not user:
        conn.close()
        flash("User not found")
        return redirect(url_for("index"))
    
    followed_id = user[0]
    
    # Check if already following
    cur.execute(
        "SELECT 1 FROM user_follows WHERE follower_id = %s AND followed_id = %s",
        (follower_id, followed_id)
    )
    already_following = cur.fetchone()
    
    if not already_following:
        # Create follow relationship
        cur.execute(
            "INSERT INTO user_follows (follower_id, followed_id, created_at) VALUES (%s, %s, NOW())",
            (follower_id, followed_id)
        )
        conn.commit()
    
    conn.close()
    return redirect(url_for("user_profile", username=username))

@app.route("/unfollow/<username>", methods=["POST"])
def unfollow_user(username):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    follower_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get user_id of the user to unfollow
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    
    if not user:
        conn.close()
        flash("User not found")
        return redirect(url_for("index"))
    
    followed_id = user[0]
    
    # Remove follow relationship
    cur.execute(
        "DELETE FROM user_follows WHERE follower_id = %s AND followed_id = %s",
        (follower_id, followed_id)
    )
    conn.commit()
    conn.close()
    
    return redirect(url_for("user_profile", username=username))

@app.route("/settings", methods=["GET", "POST"])
def user_settings():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        # Update privacy settings
        impersonation_privacy = request.form.get("impersonation_privacy")
        events_privacy = request.form.get("events_privacy")
        
        cur.execute(
            """
            UPDATE user_settings 
            SET impersonation_privacy = %s, events_privacy = %s
            WHERE user_id = %s
            """,
            (impersonation_privacy, events_privacy, user_id)
        )
        
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename:
                # Save file to uploads directory
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                # Update user profile picture in database
                cur.execute(
                    "UPDATE users SET profile_picture = %s WHERE user_id = %s",
                    (filename, user_id)
                )
        
        conn.commit()
    
    # Get current settings
    cur.execute(
        "SELECT impersonation_privacy, events_privacy FROM user_settings WHERE user_id = %s",
        (user_id,)
    )
    settings = cur.fetchone()
    
    # Get user info
    cur.execute(
        "SELECT username, email, profile_picture FROM users WHERE user_id = %s",
        (user_id,)
    )
    user_info = cur.fetchone()
    
    conn.close()
    
    return render_template(
        "settings.html",
        settings=settings,
        user_info=user_info
    )

@app.route("/settings/upload_data", methods=["GET", "POST"])
def upload_streaming_data():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        if 'streaming_data' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['streaming_data']
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Process the streaming data file
            try:
                process_streaming_data(file_path, session["user_id"])
                flash('Streaming data uploaded and processed successfully')
            except Exception as e:
                flash(f'Error processing streaming data: {str(e)}')
            
            return redirect(url_for('user_settings'))
    
    return render_template("upload_data.html")

@app.route("/profile/customize_hof", methods=["GET", "POST"])
def customize_hall_of_fame():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        # Clear existing HOF entries
        cur.execute("DELETE FROM user_hall_of_fame WHERE user_id = %s", (user_id,))
        
        # Process artists
        for i in range(1, 4):  # Up to 3 artists
            artist_id = request.form.get(f"artist_{i}")
            if artist_id:
                cur.execute(
                    "INSERT INTO user_hall_of_fame (user_id, item_type, item_id, position) VALUES (%s, 'artist', %s, %s)",
                    (user_id, artist_id, i)
                )
        
        # Process albums
        for i in range(1, 4):  # Up to 3 albums
            album_id = request.form.get(f"album_{i}")
            if album_id:
                cur.execute(
                    "INSERT INTO user_hall_of_fame (user_id, item_type, item_id, position) VALUES (%s, 'album', %s, %s)",
                    (user_id, album_id, i)
                )
        
        # Process tracks
        for i in range(1, 4):  # Up to 3 tracks
            track_id = request.form.get(f"track_{i}")
            if track_id:
                cur.execute(
                    "INSERT INTO user_hall_of_fame (user_id, item_type, item_id, position) VALUES (%s, 'track', %s, %s)",
                    (user_id, track_id, i)
                )
        
        conn.commit()
        return redirect(url_for("profile"))
    
    # Get current HOF selections
    cur.execute(
        """
        SELECT item_type, item_id, position FROM user_hall_of_fame 
        WHERE user_id = %s
        ORDER BY item_type, position
        """,
        (user_id,)
    )
    current_hof = cur.fetchall()
    
    # Organize by type and position
    hof_selections = {
        'artists': {},
        'albums': {},
        'tracks': {}
    }
    
    for item_type, item_id, position in current_hof:
        hof_selections[item_type + 's'][position] = item_id
    
    # Get top items for selection
    top_artists = get_top_items(cur, "artists", user_id, limit=20)
    top_albums = get_top_items(cur, "albums", user_id, limit=20)
    top_tracks = get_top_items(cur, "tracks", user_id, limit=20)
    
    conn.close()
    
    return render_template(
        "customize_hof.html",
        hof_selections=hof_selections,
        top_artists=top_artists,
        top_albums=top_albums,
        top_tracks=top_tracks
    )

def process_streaming_data(file_path, user_id):
    """Process a streaming history JSON file and insert data into the database"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        for item in data:
            # Extract data from JSON
            timestamp = item.get('ts', '')
            ms_played = item.get('ms_played', 0)
            master_metadata_track_name = item.get('master_metadata_track_name', '')
            master_metadata_album_artist_name = item.get('master_metadata_album_artist_name', '')
            master_metadata_album_album_name = item.get('master_metadata_album_album_name', '')
            platform = item.get('platform', '')
            country = item.get('country', '')
            reason_start = item.get('reason_start', '')
            reason_end = item.get('reason_end', '')
            shuffle = item.get('shuffle', False)
            skipped = item.get('skipped', False)
            
            if not master_metadata_track_name or not master_metadata_album_artist_name:
                continue  # Skip entries without track or artist info
            
            # Check if artist exists, if not create it
            cur.execute(
                "SELECT artist_id FROM artists WHERE artist_name = %s",
                (master_metadata_album_artist_name,)
            )
            artist = cur.fetchone()
            
            if not artist:
                cur.execute(
                    "INSERT INTO artists (artist_name) VALUES (%s) RETURNING artist_id",
                    (master_metadata_album_artist_name,)
                )
                artist_id = cur.fetchone()[0]
            else:
                artist_id = artist[0]
            
            # Check if album exists, if not create it
            if master_metadata_album_album_name:
                cur.execute(
                    "SELECT album_id FROM albums WHERE album_name = %s AND artist_id = %s",
                    (master_metadata_album_album_name, artist_id)
                )
                album = cur.fetchone()
                
                if not album:
                    cur.execute(
                        "INSERT INTO albums (album_name, artist_id) VALUES (%s, %s) RETURNING album_id",
                        (master_metadata_album_album_name, artist_id)
                    )
                    album_id = cur.fetchone()[0]
                else:
                    album_id = album[0]
            else:
                album_id = None
            
            # Check if track exists, if not create it
            cur.execute(
                "SELECT track_id FROM tracks WHERE track_name = %s AND album_id = %s",
                (master_metadata_track_name, album_id)
            )
            track = cur.fetchone()
            
            if not track:
                cur.execute(
                    "INSERT INTO tracks (track_name, album_id) VALUES (%s, %s) RETURNING track_id",
                    (master_metadata_track_name, album_id)
                )
                track_id = cur.fetchone()[0]
            else:
                track_id = track[0]
            
            # Insert listening history entry
            cur.execute(
                """
                INSERT INTO listening_history (
                    user_id, timestamp, ms_played, track_id,
                    platform, country, reason_start, reason_end,
                    shuffle, skipped, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    user_id, timestamp, ms_played, track_id,
                    platform, country, reason_start, reason_end,
                    shuffle, skipped
                )
            )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Add this function to get the current user's friends
def get_user_friends():
    """Get friends of the current user"""
    if "user_id" not in session:
        return []
    
    user_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get users that the current user follows
    cur.execute("""
        SELECT u.user_id, u.username, u.profile_picture
        FROM users u
        JOIN user_follows f ON u.user_id = f.followed_id
        WHERE f.follower_id = %s
        ORDER BY u.username
    """, (user_id,))
    
    friends = [{"user_id": row[0], "username": row[1], "profile_picture": row[2]} for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return friends

# Make the function available to templates
app.jinja_env.globals.update(get_user_friends=get_user_friends)

# Add an API endpoint for searching users
@app.route("/api/search_users")
def search_users():
    """Search for users by username"""
    query = request.args.get("q", "").strip()
    
    if len(query) < 2:
        return jsonify({"users": []})
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Search for users with usernames containing the query
    cur.execute("""
        SELECT user_id, username, profile_picture
        FROM users
        WHERE username ILIKE %s
        ORDER BY username
        LIMIT 10
    """, (f"%{query}%",))
    
    users = [{"user_id": row[0], "username": row[1], "profile_picture": row[2]} for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return jsonify({"users": users})

if __name__ == "__main__":
    app.run(debug=True)