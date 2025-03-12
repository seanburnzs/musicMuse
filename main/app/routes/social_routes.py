from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from datetime import datetime

# Create blueprint
social_bp = Blueprint('social', __name__)

# Import necessary functions
from ..utils.db import get_db_connection
from ..utils.security import csrf_protect
from ..utils.error_handlers import db_error_handler
from ..utils.date_utils import get_date_range

@social_bp.route("/follow/<username>", methods=["POST"])
def follow_user(username):
    if "user_id" not in session:
        flash("You must be logged in to follow users.", "error")
        return redirect(url_for("auth.login"))
    
    # Check if the user exists
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    
    if not user:
        conn.close()
        flash(f"User {username} not found.", "error")
        return redirect(url_for("main.index"))
    
    followed_id = user[0]
    follower_id = session.get("user_id")
    
    # Can't follow yourself
    if followed_id == follower_id:
        conn.close()
        flash("You cannot follow yourself.", "error")
        return redirect(url_for("profile.user_profile", username=username))
    
    # Check if already following
    cur.execute(
        "SELECT 1 FROM user_follows WHERE follower_id = %s AND followed_id = %s",
        (follower_id, followed_id)
    )
    
    if cur.fetchone():
        conn.close()
        flash(f"You are already following {username}.", "info")
        return redirect(url_for("profile.user_profile", username=username))
    
    # Create follow relationship
    try:
        cur.execute(
            "INSERT INTO user_follows (follower_id, followed_id, created_at) VALUES (%s, %s, %s)",
            (follower_id, followed_id, datetime.now())
        )
        conn.commit()
        flash(f"You are now following {username}.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error following user: {str(e)}", "error")
    finally:
        conn.close()
    
    return redirect(url_for("profile.user_profile", username=username))

@social_bp.route("/unfollow/<username>", methods=["POST"])
def unfollow_user(username):
    if "user_id" not in session:
        flash("You must be logged in to unfollow users.", "error")
        return redirect(url_for("auth.login"))
    
    # Check if the user exists
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    
    if not user:
        conn.close()
        flash(f"User {username} not found.", "error")
        return redirect(url_for("main.index"))
    
    followed_id = user[0]
    follower_id = session.get("user_id")
    
    # Delete follow relationship
    try:
        cur.execute(
            "DELETE FROM user_follows WHERE follower_id = %s AND followed_id = %s",
            (follower_id, followed_id)
        )
        
        if cur.rowcount == 0:
            flash(f"You are not following {username}.", "info")
        else:
            conn.commit()
            flash(f"You have unfollowed {username}.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error unfollowing user: {str(e)}", "error")
    finally:
        conn.close()
    
    return redirect(url_for("profile.user_profile", username=username))

@social_bp.route("/compare", methods=["GET", "POST"])
def compare_profiles():
    if "user_id" not in session:
        flash("You must be logged in to compare profiles.", "error")
        return redirect(url_for("auth.login"))
    
    user_id = session.get("user_id")
    
    if request.method == "POST":
        username1 = request.form.get("username1")
        username2 = request.form.get("username2")
        
        if not username1 or not username2:
            flash("Please select two users to compare.", "error")
            return redirect(url_for("social.compare_profiles"))
        
        # Check if usernames are the same
        if username1 == username2:
            flash("Please select two different users to compare.", "error")
            return redirect(url_for("social.compare_profiles"))
        
        # Get time range
        time_range = request.form.get("time_range", "all_time")
        custom_start = request.form.get("custom_start")
        custom_end = request.form.get("custom_end")
        
        # Get user IDs
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get user1 ID
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username1,))
        user1 = cur.fetchone()
        if not user1:
            conn.close()
            flash(f"User {username1} not found.", "error")
            return redirect(url_for("social.compare_profiles"))
        
        user1_id = user1[0]
        
        # Get user2 ID
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username2,))
        user2 = cur.fetchone()
        if not user2:
            conn.close()
            flash(f"User {username2} not found.", "error")
            return redirect(url_for("social.compare_profiles"))
        
        user2_id = user2[0]
        
        # Get date range
        date_filter, date_params = get_date_range(time_range, custom_start, custom_end)
        start_date = date_params[0] if date_params else None
        end_date = date_params[1] if len(date_params) > 1 else None
        
        # Get comparison metrics
        metrics = get_comparison_metrics(cur, user1_id, user2_id, start_date, end_date)
        
        # Get top genres
        user1_genres = get_top_genres(cur, user1_id, start_date, end_date)
        user2_genres = get_top_genres(cur, user2_id, start_date, end_date)
        
        # Get usernames
        cur.execute("SELECT username FROM users WHERE user_id = %s", (user1_id,))
        user1_name = cur.fetchone()[0]
        
        cur.execute("SELECT username FROM users WHERE user_id = %s", (user2_id,))
        user2_name = cur.fetchone()[0]
        
        conn.close()
        
        return render_template(
            "compare_profiles.html",
            comparing=True,
            metrics=metrics,
            user1_name=user1_name,
            user2_name=user2_name,
            user1_genres=user1_genres,
            user2_genres=user2_genres,
            time_range=time_range,
            custom_start=custom_start,
            custom_end=custom_end
        )
    
    # Check for username parameters in the URL for direct comparison
    username1 = request.args.get("username1")
    username2 = request.args.get("username2")
    time_range = request.args.get("time_range", "all_time")
    custom_start = request.args.get("custom_start")
    custom_end = request.args.get("custom_end")
    
    # If both usernames are provided in the URL, process comparison directly
    if username1 and username2:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get user1 ID
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username1,))
        user1 = cur.fetchone()
        if not user1:
            conn.close()
            flash(f"User {username1} not found.", "error")
            return redirect(url_for("social.compare_profiles"))
        
        user1_id = user1[0]
        
        # Get user2 ID
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username2,))
        user2 = cur.fetchone()
        if not user2:
            conn.close()
            flash(f"User {username2} not found.", "error")
            return redirect(url_for("social.compare_profiles"))
        
        user2_id = user2[0]
        
        # Get date range
        date_filter, date_params = get_date_range(time_range, custom_start, custom_end)
        start_date = date_params[0] if date_params else None
        end_date = date_params[1] if len(date_params) > 1 else None
        
        # Get comparison metrics
        metrics = get_comparison_metrics(cur, user1_id, user2_id, start_date, end_date)
        
        # Get top genres
        user1_genres = get_top_genres(cur, user1_id, start_date, end_date)
        user2_genres = get_top_genres(cur, user2_id, start_date, end_date)
        
        conn.close()
        
        return render_template(
            "compare_profiles.html",
            comparing=True,
            metrics=metrics,
            user1_name=username1,
            user2_name=username2,
            user1_genres=user1_genres,
            user2_genres=user2_genres,
            time_range=time_range,
            custom_start=custom_start,
            custom_end=custom_end
        )
    
    # Get user's friends
    friends = get_user_friends()
    
    # Get all users for comparison dropdown
    all_users = get_all_users()
    
    return render_template(
        "compare_profiles.html",
        comparing=False,
        friends=friends,
        all_users=all_users
    )

def get_comparison_metrics(cur, user1_id, user2_id, start_date=None, end_date=None):
    # Helper function to build the date filter for SQL queries
    def build_date_filter():
        if start_date and end_date:
            return "AND lh.timestamp BETWEEN %s AND %s"
        elif start_date:
            return "AND lh.timestamp >= %s"
        elif end_date:
            return "AND lh.timestamp <= %s"
        return ""
    
    # Helper function to get date parameters
    def get_date_params():
        if start_date and end_date:
            return [start_date, end_date]
        elif start_date:
            return [start_date]
        elif end_date:
            return [end_date]
        return []
    
    date_filter = build_date_filter()
    date_params = get_date_params()
    
    metrics = {}
    
    # Common artists
    query = f"""
    WITH user1_artists AS (
        SELECT a.artist_id, a.artist_name, COUNT(lh.id) as play_count
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
        GROUP BY a.artist_id, a.artist_name
    ),
    user2_artists AS (
        SELECT a.artist_id, a.artist_name, COUNT(lh.id) as play_count
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
        GROUP BY a.artist_id, a.artist_name
    )
    SELECT u1.artist_id, u1.artist_name, u1.play_count as user1_plays, u2.play_count as user2_plays
    FROM user1_artists u1
    JOIN user2_artists u2 ON u1.artist_id = u2.artist_id
    ORDER BY u1.play_count + u2.play_count DESC
    LIMIT 10
    """
    
    params = [user1_id] + date_params + [user2_id] + date_params
    cur.execute(query, params)
    common_artists = cur.fetchall()
    
    # Common tracks
    query = f"""
    WITH user1_tracks AS (
        SELECT t.track_id, t.track_name, a.artist_name, COUNT(lh.id) as play_count
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
        GROUP BY t.track_id, t.track_name, a.artist_name
    ),
    user2_tracks AS (
        SELECT t.track_id, t.track_name, a.artist_name, COUNT(lh.id) as play_count
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
        GROUP BY t.track_id, t.track_name, a.artist_name
    )
    SELECT u1.track_id, u1.track_name, u1.artist_name, u1.play_count as user1_plays, u2.play_count as user2_plays
    FROM user1_tracks u1
    JOIN user2_tracks u2 ON u1.track_id = u2.track_id
    ORDER BY u1.play_count + u2.play_count DESC
    LIMIT 10
    """
    
    params = [user1_id] + date_params + [user2_id] + date_params
    cur.execute(query, params)
    common_tracks = cur.fetchall()
    
    # Unique artists for user1
    query = f"""
    WITH user1_artists AS (
        SELECT a.artist_id, a.artist_name, COUNT(lh.id) as play_count
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
        GROUP BY a.artist_id, a.artist_name
    ),
    user2_artists AS (
        SELECT a.artist_id
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
        GROUP BY a.artist_id
    )
    SELECT u1.artist_id, u1.artist_name, u1.play_count
    FROM user1_artists u1
    LEFT JOIN user2_artists u2 ON u1.artist_id = u2.artist_id
    WHERE u2.artist_id IS NULL
    ORDER BY u1.play_count DESC
    LIMIT 5
    """
    
    params = [user1_id] + date_params + [user2_id] + date_params
    cur.execute(query, params)
    unique_artists_user1 = cur.fetchall()
    
    # Unique artists for user2
    query = f"""
    WITH user2_artists AS (
        SELECT a.artist_id, a.artist_name, COUNT(lh.id) as play_count
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
        GROUP BY a.artist_id, a.artist_name
    ),
    user1_artists AS (
        SELECT a.artist_id
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
        GROUP BY a.artist_id
    )
    SELECT u2.artist_id, u2.artist_name, u2.play_count
    FROM user2_artists u2
    LEFT JOIN user1_artists u1 ON u2.artist_id = u1.artist_id
    WHERE u1.artist_id IS NULL
    ORDER BY u2.play_count DESC
    LIMIT 5
    """
    
    params = [user2_id] + date_params + [user1_id] + date_params
    cur.execute(query, params)
    unique_artists_user2 = cur.fetchall()
    
    # Get total stats including listening_time, unique_albums, and unique_artists
    query = f"""
    WITH user1_stats AS (
        SELECT 
            COUNT(lh.id) as stream_count, 
            COUNT(DISTINCT lh.track_id) as unique_tracks,
            SUM(lh.ms_played) as listening_time_ms,
            COUNT(DISTINCT al.album_id) as unique_albums,
            COUNT(DISTINCT a.artist_id) as unique_artists
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
    ),
    user2_stats AS (
        SELECT 
            COUNT(lh.id) as stream_count, 
            COUNT(DISTINCT lh.track_id) as unique_tracks,
            SUM(lh.ms_played) as listening_time_ms,
            COUNT(DISTINCT al.album_id) as unique_albums,
            COUNT(DISTINCT a.artist_id) as unique_artists
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s {date_filter}
    )
    SELECT 
        u1.stream_count as user1_streams, 
        u1.unique_tracks as user1_unique_tracks, 
        u1.listening_time_ms as user1_listening_time,
        u1.unique_albums as user1_unique_albums,
        u1.unique_artists as user1_unique_artists,
        u2.stream_count as user2_streams, 
        u2.unique_tracks as user2_unique_tracks,
        u2.listening_time_ms as user2_listening_time,
        u2.unique_albums as user2_unique_albums,
        u2.unique_artists as user2_unique_artists
    FROM user1_stats u1, user2_stats u2
    """
    
    params = [user1_id] + date_params + [user2_id] + date_params
    cur.execute(query, params)
    stats = cur.fetchone()
    
    metrics["common_artists"] = common_artists
    metrics["common_tracks"] = common_tracks
    metrics["unique_artists_user1"] = unique_artists_user1
    metrics["unique_artists_user2"] = unique_artists_user2
    metrics["stats"] = stats
    
    return metrics

def get_top_genres(cur, user_id, start_date=None, end_date=None, limit=5):
    # Helper function to build the date filter for SQL queries
    def build_date_filter():
        if start_date and end_date:
            return "AND lh.timestamp BETWEEN %s AND %s"
        elif start_date:
            return "AND lh.timestamp >= %s"
        elif end_date:
            return "AND lh.timestamp <= %s"
        return ""
    
    # Helper function to get date parameters
    def get_date_params():
        if start_date and end_date:
            return [start_date, end_date]
        elif start_date:
            return [start_date]
        elif end_date:
            return [end_date]
        return []
    
    date_filter = build_date_filter()
    date_params = get_date_params()
    
    query = f"""
    SELECT g.genre_name, COUNT(lh.id) as play_count
    FROM listening_history lh
    JOIN tracks t ON lh.track_id = t.track_id
    JOIN track_genres tg ON t.track_id = tg.track_id
    JOIN genres g ON tg.genre_id = g.genre_id
    WHERE lh.user_id = %s {date_filter}
    GROUP BY g.genre_name
    ORDER BY play_count DESC
    LIMIT %s
    """
    
    params = [user_id] + date_params + [limit]
    cur.execute(query, params)
    
    return cur.fetchall()

@social_bp.route("/compare_shortcut")
def compare_shortcut():
    if "user_id" not in session:
        flash("You must be logged in to compare profiles.", "error")
        return redirect(url_for("auth.login"))
    
    username = request.args.get("username")
    if not username:
        return redirect(url_for("social.compare_profiles"))
    
    # Use the current user as the first user and the selected user as the second
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE user_id = %s", (session.get("user_id"),))
    current_username = cur.fetchone()[0]
    conn.close()
    
    # Redirect to the form submission route with both usernames
    return redirect(url_for("social.compare_profiles") + f"?username1={current_username}&username2={username}")

def get_user_friends():
    if "user_id" not in session:
        return []
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        """
        SELECT u.user_id, u.username, u.profile_picture
        FROM user_follows f
        JOIN users u ON f.followed_id = u.user_id
        WHERE f.follower_id = %s
        ORDER BY u.username
        """,
        (session.get("user_id"),)
    )
    
    friends_data = cur.fetchall()
    conn.close()
    
    # Convert tuples to dictionaries
    friends = []
    for friend in friends_data:
        friends.append({
            "user_id": friend[0],
            "username": friend[1],
            "profile_picture": friend[2]
        })
    
    return friends

def get_all_users():
    """Get all users from the database for comparison search."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        """
        SELECT user_id, username, profile_picture
        FROM users
        ORDER BY username
        """
    )
    
    users_data = cur.fetchall()
    conn.close()
    
    # Convert tuples to dictionaries
    users = []
    for user in users_data:
        users.append({
            "user_id": user[0],
            "username": user[1],
            "profile_picture": user[2]
        })
    
    return users