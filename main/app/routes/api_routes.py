from flask import Blueprint, jsonify, request, session
import psycopg2
from datetime import datetime

# Create blueprint
api_bp = Blueprint('api', __name__)

# Import necessary functions
from ..utils.db import get_db_connection
from ..utils.security import csrf_protect
from ..utils.cache import redis_cache
from ..utils.error_handlers import api_error_handler
from ..services.spotify_service import SpotifyService

@api_bp.route("/api/top_items", methods=["GET"])
@api_error_handler
def api_top_items():
    # Implementation for top items API
    # ... (implementation details)
    return jsonify({})

@api_bp.route("/api/user_profile", methods=["GET"])
@api_error_handler
@redis_cache("user_profile", expire=3600)
def api_user_profile():
    # Implementation for user profile API
    # ... (implementation details)
    return jsonify({})

@api_bp.route("/api/search_users")
@api_error_handler
def search_users():
    query = request.args.get("q", "").strip()
    
    if not query or len(query) < 2:
        return jsonify({"users": []})
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Search for users
    cur.execute(
        """
        SELECT user_id, username, profile_picture 
        FROM users 
        WHERE username ILIKE %s 
        ORDER BY username
        LIMIT 20
        """,
        (f"%{query}%",)
    )
    users_data = cur.fetchall()
    conn.close()
    
    # Format users as dictionaries
    users = []
    for user in users_data:
        users.append({
            "user_id": user[0],
            "username": user[1],
            "profile_picture": user[2]
        })
    
    return jsonify({"users": users})

@api_bp.route("/api/user_connections/<connection_type>/<username>")
@api_error_handler
def user_connections(connection_type, username):
    if connection_type not in ["followers", "following"]:
        return jsonify({"error": "Invalid connection type"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get user ID from username
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    
    user_id = user[0]
    
    # Get connections based on type
    if connection_type == "followers":
        # Get users who follow this user
        cur.execute(
            """
            SELECT u.user_id, u.username, u.profile_picture
            FROM user_follows f
            JOIN users u ON f.follower_id = u.user_id
            WHERE f.followed_id = %s
            ORDER BY u.username
            """,
            (user_id,)
        )
    else:  # following
        # Get users this user follows
        cur.execute(
            """
            SELECT u.user_id, u.username, u.profile_picture
            FROM user_follows f
            JOIN users u ON f.followed_id = u.user_id
            WHERE f.follower_id = %s
            ORDER BY u.username
            """,
            (user_id,)
        )
    
    connections_data = cur.fetchall()
    conn.close()
    
    # Format connections as dictionaries
    connections = []
    for connection in connections_data:
        connections.append({
            "user_id": connection[0],
            "username": connection[1],
            "profile_picture": connection[2]
        })
    
    return jsonify({"connections": connections})

@api_bp.route("/api/user_analytics", methods=["GET"])
@api_error_handler
def api_user_analytics():
    try:
        # Get user ID from session
        user_id = session.get('user_id')
        print(f"DEBUG: User ID from session: {user_id}")
        
        if not user_id:
            print("DEBUG: No user ID in session")
            return jsonify({'error': 'Not logged in'}), 401
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if user has any listening data
        check_query = "SELECT COUNT(*) FROM listening_history WHERE user_id = %s"
        cur.execute(check_query, (user_id,))
        count = cur.fetchone()[0]
        print(f"DEBUG: User {user_id} has {count} listening history records")
        
        if count == 0:
            print(f"DEBUG: No listening data for user {user_id}")
            return jsonify({
                'no_listening_data': True,
                'listening_streak': 0,
                'most_active_day': 'N/A',
                'most_active_time': 'N/A'
            })
        
        # Get listening streak
        streak_query = """
            WITH daily_listens AS (
                SELECT DISTINCT DATE(lh.timestamp) as listen_date
                FROM listening_history lh
                WHERE lh.user_id = %s
                ORDER BY listen_date
            ),
            date_diffs AS (
                SELECT 
                    listen_date,
                    listen_date - LAG(listen_date, 1) OVER (ORDER BY listen_date) AS diff
                FROM daily_listens
            ),
            streaks AS (
                SELECT
                    listen_date,
                    SUM(CASE WHEN diff = 1 THEN 0 ELSE 1 END) OVER (ORDER BY listen_date) AS streak_group
                FROM date_diffs
            ),
            streak_lengths AS (
                SELECT
                    streak_group,
                    COUNT(*) AS streak_length
                FROM streaks
                GROUP BY streak_group
            )
            SELECT COALESCE(MAX(streak_length), 0) AS max_streak
            FROM streak_lengths
        """
        print(f"DEBUG: Executing streak query for user {user_id}")
        cur.execute(streak_query, (user_id,))
        
        streak_result = cur.fetchone()
        print(f"DEBUG: Streak result: {streak_result}")
        listening_streak = streak_result[0] if streak_result else 0
        
        # Get most active day
        day_query = """
            SELECT 
                CASE 
                    WHEN EXTRACT(DOW FROM lh.timestamp) = 0 THEN 'Sunday'
                    WHEN EXTRACT(DOW FROM lh.timestamp) = 1 THEN 'Monday'
                    WHEN EXTRACT(DOW FROM lh.timestamp) = 2 THEN 'Tuesday'
                    WHEN EXTRACT(DOW FROM lh.timestamp) = 3 THEN 'Wednesday'
                    WHEN EXTRACT(DOW FROM lh.timestamp) = 4 THEN 'Thursday'
                    WHEN EXTRACT(DOW FROM lh.timestamp) = 5 THEN 'Friday'
                    WHEN EXTRACT(DOW FROM lh.timestamp) = 6 THEN 'Saturday'
                END as day_name,
                COUNT(*) as listen_count
            FROM listening_history lh
            WHERE lh.user_id = %s
            GROUP BY EXTRACT(DOW FROM lh.timestamp)
            ORDER BY listen_count DESC
            LIMIT 1
        """
        print(f"DEBUG: Executing day query for user {user_id}")
        cur.execute(day_query, (user_id,))
        
        day_result = cur.fetchone()
        print(f"DEBUG: Day result: {day_result}")
        most_active_day = day_result[0] if day_result else 'N/A'
        
        # Get most active time
        time_query = """
            SELECT 
                EXTRACT(HOUR FROM lh.timestamp) as hour,
                COUNT(*) as listen_count
            FROM listening_history lh
            WHERE lh.user_id = %s
            GROUP BY hour
            ORDER BY listen_count DESC
            LIMIT 1
        """
        print(f"DEBUG: Executing time query for user {user_id}")
        cur.execute(time_query, (user_id,))
        
        time_result = cur.fetchone()
        print(f"DEBUG: Time result: {time_result}")
        
        # Convert hour to 12-hour format with AM/PM
        if time_result:
            hour = int(time_result[0])
            if hour == 0:
                most_active_time = "12 AM"
            elif hour < 12:
                most_active_time = f"{hour} AM"
            elif hour == 12:
                most_active_time = "12 PM"
            else:
                most_active_time = f"{hour - 12} PM"
        else:
            most_active_time = 'N/A'
        
        # Get most popular artist
        artist_query = """
            SELECT a.artist_name, COUNT(*) as play_count
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums al ON t.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            WHERE lh.user_id = %s
            GROUP BY a.artist_name
            ORDER BY play_count DESC
            LIMIT 1
        """
        print(f"DEBUG: Executing artist query for user {user_id}")
        cur.execute(artist_query, (user_id,))
        
        artist_result = cur.fetchone()
        print(f"DEBUG: Artist result: {artist_result}")
        most_popular_artist = artist_result[0] if artist_result else 'N/A'
        
        response_data = {
            'no_listening_data': False,
            'listening_streak': listening_streak,
            'most_active_day': most_active_day,
            'most_active_time': most_active_time,
            'most_popular_artist': most_popular_artist
        }
        
        print(f"DEBUG: Final response data: {response_data}")
        return jsonify(response_data)
    
    except Exception as e:
        print(f"DEBUG: Error in user_analytics: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()

@api_bp.route("/api/app_analytics")
@api_error_handler
def api_app_analytics():
    """Get global app analytics data"""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get total users
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        # Get total streams
        cur.execute("SELECT COUNT(*) FROM listening_history")
        total_streams = cur.fetchone()[0]
        
        # Get unique tracks
        cur.execute("SELECT COUNT(*) FROM tracks")
        unique_tracks = cur.fetchone()[0]
        
        # Get unique albums
        cur.execute("SELECT COUNT(*) FROM albums")
        unique_albums = cur.fetchone()[0]
        
        # Get unique artists
        cur.execute("SELECT COUNT(*) FROM artists")
        unique_artists = cur.fetchone()[0]
        
        # Get most popular artist
        cur.execute("""
            SELECT a.artist_name
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums al ON t.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            GROUP BY a.artist_name
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """)
        
        popular_artist_result = cur.fetchone()
        popular_artist = popular_artist_result[0] if popular_artist_result else "Unknown"
        
        return jsonify({
            "total_users": total_users,
            "total_streams": total_streams,
            "unique_tracks": unique_tracks,
            "unique_albums": unique_albums,
            "unique_artists": unique_artists,
            "popular_artist": popular_artist
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    finally:
        conn.close()

@api_bp.route("/api/music_muse", methods=["POST"])
@api_error_handler
def api_music_muse():
    # Implementation for Music Muse API
    # ... (implementation details)
    return jsonify({})

@api_bp.route("/api/update_spotify_settings", methods=["POST"])
@api_error_handler
@csrf_protect
def api_update_spotify_settings():
    """Update user's Spotify integration settings"""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = session["user_id"]
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Extract settings from request
    enabled = data.get("enabled")
    sync_frequency = data.get("sync_frequency")
    share_listening = data.get("share_listening")
    
    # Validate settings
    if enabled is None:
        return jsonify({"error": "Missing required field: enabled"}), 400
    
    if sync_frequency and sync_frequency not in ["realtime", "hourly", "daily", "never"]:
        return jsonify({"error": "Invalid sync_frequency value"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if user has Spotify settings
        cur.execute("SELECT user_id FROM user_spotify_settings WHERE user_id = %s", (user_id,))
        existing = cur.fetchone()
        
        if existing:
            # Update existing settings
            update_fields = []
            params = []
            
            if enabled is not None:
                update_fields.append("enabled = %s")
                params.append(enabled)
            
            if sync_frequency:
                update_fields.append("sync_frequency = %s")
                params.append(sync_frequency)
            
            if share_listening is not None:
                update_fields.append("share_listening = %s")
                params.append(share_listening)
            
            # Add user_id to params
            params.append(user_id)
            
            # Execute update query
            cur.execute(
                f"""
                UPDATE user_spotify_settings 
                SET {", ".join(update_fields)}, updated_at = %s
                WHERE user_id = %s
                """,
                (*params, datetime.now(), user_id)
            )
        else:
            # User doesn't have Spotify connected
            if enabled:
                return jsonify({
                    "error": "Cannot enable Spotify integration without connecting to Spotify first",
                    "redirect": "/connect_spotify"
                }), 400
        
        conn.commit()
        return jsonify({"success": True, "message": "Spotify settings updated successfully"})
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    
    finally:
        conn.close()

@api_bp.route("/api/spotify_status")
@api_error_handler
def api_spotify_status():
    """Get the current status of user's Spotify integration"""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get user's Spotify settings
        cur.execute(
            """
            SELECT enabled, sync_frequency, share_listening, token_expiry
            FROM user_spotify_settings
            WHERE user_id = %s
            """,
            (user_id,)
        )
        
        settings = cur.fetchone()
        
        if not settings:
            return jsonify({
                "connected": False,
                "enabled": False,
                "message": "Spotify not connected"
            })
        
        enabled, sync_frequency, share_listening, token_expiry = settings
        
        # Check if token is expired
        token_valid = token_expiry > datetime.now().timestamp() if token_expiry else False
        
        return jsonify({
            "connected": True,
            "enabled": enabled,
            "sync_frequency": sync_frequency,
            "share_listening": share_listening,
            "token_valid": token_valid
        })
    
    finally:
        conn.close()

@api_bp.route("/api/spotify_currently_playing")
@api_error_handler
@redis_cache("currently_playing", expire=60)  # Cache for 60 seconds
def api_spotify_currently_playing():
    """Get user's currently playing track from Spotify"""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if user has Spotify enabled
        cur.execute(
            """
            SELECT access_token, refresh_token, token_expiry, enabled
            FROM user_spotify_settings
            WHERE user_id = %s
            """,
            (user_id,)
        )
        
        spotify_settings = cur.fetchone()
        
        if not spotify_settings or not spotify_settings[3]:  # not enabled
            return jsonify({"error": "Spotify integration not enabled"}), 400
        
        access_token, refresh_token, token_expiry, _ = spotify_settings
        
        # Check if token is expired and needs refresh
        if token_expiry < datetime.now().timestamp():
            # Token is expired, would need to refresh
            # This would be implemented in a real application
            return jsonify({"error": "Spotify token expired, please reconnect"}), 401
        
        # In a real implementation, we would call Spotify API here
        # For now, return a placeholder
        return jsonify({
            "is_playing": True,
            "track": {
                "name": "Example Track",
                "artist": "Example Artist",
                "album": "Example Album",
                "album_art": "https://example.com/album_art.jpg",
                "duration_ms": 180000,
                "progress_ms": 45000
            }
        })
    
    finally:
        conn.close()

@api_bp.route("/api/spotify_recent_tracks")
@api_error_handler
def api_spotify_recent_tracks():
    """Get user's recently played tracks from Spotify"""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = session["user_id"]
    limit = request.args.get("limit", 10, type=int)
    
    # Validate limit
    if limit < 1 or limit > 50:
        return jsonify({"error": "Invalid limit parameter (must be between 1 and 50)"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if user has Spotify enabled
        cur.execute(
            """
            SELECT access_token, refresh_token, token_expiry, enabled
            FROM user_spotify_settings
            WHERE user_id = %s
            """,
            (user_id,)
        )
        
        spotify_settings = cur.fetchone()
        
        if not spotify_settings or not spotify_settings[3]:  # not enabled
            return jsonify({"error": "Spotify integration not enabled"}), 400
        
        # In a real implementation, we would call Spotify API here
        # For now, return placeholder data
        tracks = []
        for i in range(limit):
            tracks.append({
                "track": {
                    "id": f"track_{i}",
                    "name": f"Example Track {i}",
                    "artist": f"Example Artist {i % 3}",
                    "album": f"Example Album {i % 5}",
                    "album_art": f"https://example.com/album_art_{i}.jpg",
                },
                "played_at": (datetime.now().isoformat())
            })
        
        return jsonify({"items": tracks})
    
    finally:
        conn.close()

@api_bp.route("/api/spotify_top_items/<item_type>")
@api_error_handler
@redis_cache("spotify_top", expire=86400)  # Cache for 24 hours
def api_spotify_top_items(item_type):
    """Get user's top artists or tracks from Spotify"""
    if item_type not in ["artists", "tracks"]:
        return jsonify({"error": "Invalid item type. Must be 'artists' or 'tracks'"}), 400
    
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = session["user_id"]
    time_range = request.args.get("time_range", "medium_term")
    limit = request.args.get("limit", 10, type=int)
    
    # Validate parameters
    if time_range not in ["short_term", "medium_term", "long_term"]:
        return jsonify({"error": "Invalid time_range parameter"}), 400
    
    if limit < 1 or limit > 50:
        return jsonify({"error": "Invalid limit parameter (must be between 1 and 50)"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if user has Spotify enabled
        cur.execute(
            """
            SELECT access_token, refresh_token, token_expiry, enabled
            FROM user_spotify_settings
            WHERE user_id = %s
            """,
            (user_id,)
        )
        
        spotify_settings = cur.fetchone()
        
        if not spotify_settings or not spotify_settings[3]:  # not enabled
            return jsonify({"error": "Spotify integration not enabled"}), 400
        
        # In a real implementation, we would call Spotify API here
        # For now, return placeholder data
        items = []
        for i in range(limit):
            if item_type == "artists":
                items.append({
                    "id": f"artist_{i}",
                    "name": f"Example Artist {i}",
                    "popularity": 100 - (i * 2),
                    "genres": [f"genre_{i % 5}", f"genre_{(i + 1) % 5}"],
                    "image": f"https://example.com/artist_{i}.jpg"
                })
            else:  # tracks
                items.append({
                    "id": f"track_{i}",
                    "name": f"Example Track {i}",
                    "artist": f"Example Artist {i % 5}",
                    "album": f"Example Album {i % 3}",
                    "popularity": 100 - (i * 2),
                    "image": f"https://example.com/track_{i}.jpg"
                })
        
        return jsonify({
            "items": items,
            "time_range": time_range
        })
    
    finally:
        conn.close()