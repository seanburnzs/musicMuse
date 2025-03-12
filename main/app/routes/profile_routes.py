from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, current_app, jsonify
import psycopg2
from werkzeug.utils import secure_filename
import os
import requests
from datetime import datetime, timedelta
import time
import logging
from werkzeug.exceptions import RequestEntityTooLarge
import traceback
import sys

# Create blueprint
profile_bp = Blueprint('profile', __name__)

# Set up logger for this module
logger = logging.getLogger('app.profile_routes')

# Import necessary functions
from ..utils.db import get_db_connection
from ..utils.security import csrf_protect
from ..utils.error_handlers import db_error_handler

@profile_bp.route("/profile")
def profile():
    # Redirect to user's profile page
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    return redirect(url_for("profile.user_profile", username=session.get("username")))

@profile_bp.route("/profile/<username>")
def user_profile(username):
    # Display user profile
    if "user_id" not in session:
        flash("You must be logged in to view profiles.", "error")
        return redirect(url_for("auth.login"))
    
    # Implementation for user profile
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get user info
    cur.execute(
        """
        SELECT u.user_id, u.username, u.email, u.profile_picture, u.created_at
        FROM users u
        WHERE u.username = %s
        """,
        (username,)
    )
    user_info = cur.fetchone()
    
    if not user_info:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("main.index"))
    
    user_id = user_info[0]
    
    # Check if this is current user's profile
    is_own_profile = user_id == session.get("user_id")
    
    # Check if the current user follows this user
    is_following = False
    if not is_own_profile:
        cur.execute(
            """
            SELECT 1 FROM user_follows
            WHERE follower_id = %s AND followed_id = %s
            """,
            (session.get("user_id"), user_id)
        )
        is_following = cur.fetchone() is not None
    
    # Get stats
    cur.execute(
        """
        SELECT COUNT(id) as total_streams,
               COUNT(DISTINCT track_id) as unique_tracks,
               SUM(ms_played) / 1000 / 60 / 60 as total_hours
        FROM listening_history
        WHERE user_id = %s
        """,
        (user_id,)
    )
    stats = cur.fetchone()
    
    # Get top items (artists, albums, tracks)
    top_artists = get_top_items(cur, "artist", user_id)
    top_albums = get_top_items(cur, "album", user_id)
    top_tracks = get_top_items(cur, "track", user_id)
    
    # Get recent items (last 30 days)
    recent_artists = get_top_items(cur, "artist", user_id, time_range="30_days")
    recent_albums = get_top_items(cur, "album", user_id, time_range="30_days")
    recent_tracks = get_top_items(cur, "track", user_id, time_range="30_days")
    
    # Get Hall of Fame selections
    # For artists
    cur.execute(
        """
        SELECT a.artist_id, a.artist_name, a.image_url, COUNT(lh.id) as play_count, 
               SUM(lh.ms_played) / 1000 / 60 / 60 as total_hours
        FROM user_hall_of_fame hof
        JOIN artists a ON hof.item_id = a.artist_id
        LEFT JOIN albums al ON al.artist_id = a.artist_id
        LEFT JOIN tracks t ON t.album_id = al.album_id
        LEFT JOIN listening_history lh ON lh.track_id = t.track_id AND lh.user_id = hof.user_id
        WHERE hof.user_id = %s AND hof.item_type = 'artist'
        GROUP BY a.artist_id, a.artist_name, a.image_url, hof.position
        ORDER BY hof.position
        """,
        (user_id,)
    )
    hall_of_fame_artists = cur.fetchall()
    
    # For albums
    cur.execute(
        """
        SELECT al.album_id, al.album_name, a.artist_name, al.image_url, COUNT(lh.id) as play_count, 
               SUM(lh.ms_played) / 1000 / 60 / 60 as total_hours, a.artist_id
        FROM user_hall_of_fame hof
        JOIN albums al ON hof.item_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        LEFT JOIN tracks t ON t.album_id = al.album_id
        LEFT JOIN listening_history lh ON lh.track_id = t.track_id AND lh.user_id = hof.user_id
        WHERE hof.user_id = %s AND hof.item_type = 'album'
        GROUP BY al.album_id, al.album_name, a.artist_name, al.image_url, a.artist_id, hof.position
        ORDER BY hof.position
        """,
        (user_id,)
    )
    hall_of_fame_albums = cur.fetchall()
    
    # For tracks
    cur.execute(
        """
        SELECT t.track_id, t.track_name, a.artist_name, t.image_url, COUNT(lh.id) as play_count, 
               SUM(lh.ms_played) / 1000 / 60 / 60 as total_hours, a.artist_id
        FROM user_hall_of_fame hof
        JOIN tracks t ON hof.item_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        LEFT JOIN listening_history lh ON lh.track_id = t.track_id AND lh.user_id = hof.user_id
        WHERE hof.user_id = %s AND hof.item_type = 'track'
        GROUP BY t.track_id, t.track_name, a.artist_name, t.image_url, a.artist_id, hof.position
        ORDER BY hof.position
        """,
        (user_id,)
    )
    hall_of_fame_tracks = cur.fetchall()
    
    # Construct the hall_of_fame dictionary
    hall_of_fame = {
        "artists": hall_of_fame_artists,
        "albums": hall_of_fame_albums,
        "tracks": hall_of_fame_tracks
    }
    
    # Get user events if allowed
    events = []
    events_visible = False
    
    if is_own_profile:
        events = get_user_events(cur, user_id)
        events_visible = True
    else:
        # Check privacy settings for events
        cur.execute(
            "SELECT events_privacy FROM user_settings WHERE user_id = %s",
            (user_id,)
        )
        settings = cur.fetchone()
        
        if settings:
            events_privacy = settings[0]
            
            if events_privacy == "everyone":
                events = get_user_events(cur, user_id)
                events_visible = True
            elif events_privacy == "friends":
                # Check if current user follows this user
                if is_following:
                    events = get_user_events(cur, user_id)
                    events_visible = True
    
    # Get follower counts
    cur.execute(
        """
        SELECT COUNT(*) FROM user_follows WHERE followed_id = %s
        """,
        (user_id,)
    )
    follower_count = cur.fetchone()[0]
    
    cur.execute(
        """
        SELECT COUNT(*) FROM user_follows WHERE follower_id = %s
        """,
        (user_id,)
    )
    following_count = cur.fetchone()[0]
    
    # Format the data
    formatted_user = {
        "user_id": user_info[0],
        "username": user_info[1],
        "profile_picture": user_info[3],
        "created_at": user_info[4].strftime("%B %Y") if user_info[4] else "Unknown",
        "total_streams": stats[0] if stats else 0,
        "unique_tracks": stats[1] if stats else 0,
        "total_hours": int(stats[2]) if stats and stats[2] else 0,
        "follower_count": follower_count,
        "following_count": following_count
    }
    
    conn.close()
    
    return render_template(
        "user_profile.html",
        username=formatted_user["username"],
        profile_picture=formatted_user["profile_picture"],
        total_streams=formatted_user["total_streams"],
        followers_count=formatted_user["follower_count"],
        following_count=formatted_user["following_count"],
        is_own_profile=is_own_profile,
        is_following=is_following,
        recents={
            "artists": recent_artists,
            "albums": recent_albums,
            "tracks": recent_tracks
        },
        hall_of_fame=hall_of_fame,
        events=events,
        events_visible=events_visible
    )

def get_top_items(cur, entity_type, user_id, time_range="all_time", limit=3):
    # Get date range
    date_filter, date_params = "", []
    
    # Apply time range filter if needed
    if time_range == "30_days":
        date_filter = "AND lh.timestamp >= NOW() - INTERVAL '30 days' "
    elif time_range == "90_days":
        date_filter = "AND lh.timestamp >= NOW() - INTERVAL '90 days' "
    elif time_range == "6_months":
        date_filter = "AND lh.timestamp >= NOW() - INTERVAL '6 months' "
    elif time_range == "year":
        date_filter = "AND lh.timestamp >= NOW() - INTERVAL '1 year' "
    
    # Build SQL query based on entity type
    if entity_type == "artist":
        query = """
        SELECT a.artist_id, a.artist_name, a.image_url, COUNT(lh.id) as play_count, 
               SUM(lh.ms_played) / 1000 / 60 / 60 as total_hours
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s """ + date_filter + """
        GROUP BY a.artist_id, a.artist_name, a.image_url
        ORDER BY play_count DESC
        LIMIT %s
        """
    elif entity_type == "album":
        query = """
        SELECT al.album_id, al.album_name, a.artist_name, al.image_url, COUNT(lh.id) as play_count, 
               SUM(lh.ms_played) / 1000 / 60 / 60 as total_hours, a.artist_id
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s """ + date_filter + """
        GROUP BY al.album_id, al.album_name, a.artist_name, al.image_url, a.artist_id
        ORDER BY play_count DESC
        LIMIT %s
        """
    else:  # tracks
        query = """
        SELECT t.track_id, t.track_name, a.artist_name, t.image_url, COUNT(lh.id) as play_count,
               SUM(lh.ms_played) / 1000 / 60 / 60 as total_hours, a.artist_id
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s """ + date_filter + """
        GROUP BY t.track_id, t.track_name, a.artist_name, t.image_url, a.artist_id
        ORDER BY play_count DESC
        LIMIT %s
        """
    
    params = [user_id] + date_params + [limit]
    cur.execute(query, params)
    return cur.fetchall()

def get_user_events(cur, user_id):
    cur.execute(
        """
        SELECT event_id, name, start_date, end_date, description, category, color
        FROM user_events
        WHERE user_id = %s
        ORDER BY start_date DESC
        """,
        (user_id,)
    )
    events = cur.fetchall()
    
    formatted_events = []
    for event in events:
        formatted_events.append({
            "event_id": event[0],
            "name": event[1],
            "start_date": event[2].strftime("%Y-%m-%d"),
            "end_date": event[3].strftime("%Y-%m-%d") if event[3] else None,
            "description": event[4],
            "category": event[5],
            "color": event[6] or "#3788d8"
        })
    
    return formatted_events

@profile_bp.route("/settings", methods=["GET", "POST"])
def user_settings():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    user_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        # Determine which form was submitted
        form_type = request.form.get("form_type", "profile")
        
        if form_type == "profile":
            # Update profile information
            email = request.form.get("email", "")
            
            # Handle profile picture upload
            profile_picture = None
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename and allowed_file(file.filename):
                    # Generate a secure filename
                    filename = secure_filename(file.filename)
                    # Add timestamp to ensure uniqueness
                    filename = f"{int(time.time())}_{filename}"
                    # Save the file
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    profile_picture = filename
            
            # Update user information in the database
            try:
                update_query = "UPDATE users SET email = %s"
                params = [email]
                
                if profile_picture:
                    update_query += ", profile_picture = %s"
                    params.append(profile_picture)
                
                update_query += " WHERE user_id = %s"
                params.append(user_id)
                
                cur.execute(update_query, params)
                conn.commit()
                flash("Profile updated successfully.", "success")
            except Exception as e:
                conn.rollback()
                flash(f"Error updating profile: {str(e)}", "error")
        
        elif form_type == "privacy":
            # Update privacy settings
            impersonation_privacy = request.form.get("impersonation_privacy", "everyone")
            events_privacy = request.form.get("events_privacy", "everyone")
            
            # Update settings in the database
            try:
                cur.execute(
                    """
                    INSERT INTO user_settings (user_id, impersonation_privacy, events_privacy, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        impersonation_privacy = EXCLUDED.impersonation_privacy,
                        events_privacy = EXCLUDED.events_privacy,
                        updated_at = NOW()
                    """,
                    (user_id, impersonation_privacy, events_privacy)
                )
                conn.commit()
                flash("Privacy settings updated successfully.", "success")
            except Exception as e:
                conn.rollback()
                flash(f"Error updating privacy settings: {str(e)}", "error")
        
        elif form_type == "spotify":
            # Handle Spotify connection/disconnection
            action = request.form.get("action")
            if action == "disconnect":
                # Remove Spotify connection
                session.pop('spotify_connected', None)
                session.pop('spotify_scrobbling_enabled', None)
                flash("Spotify account disconnected successfully.", "success")
    
    # Get user information
    try:
        cur.execute(
            """
            SELECT username, email, profile_picture 
            FROM users 
            WHERE user_id = %s
            """,
            (user_id,)
        )
        user_info = cur.fetchone()
        
        # Default user info if not found
        if not user_info:
            user_info = ("Unknown", "", None)
    except Exception as e:
        flash(f"Error retrieving user information: {str(e)}", "error")
        user_info = ("Unknown", "", None)
    
    # Get current user settings
    try:
        cur.execute(
            """
            SELECT impersonation_privacy, events_privacy 
            FROM user_settings 
            WHERE user_id = %s
            """,
            (user_id,)
        )
        settings = cur.fetchone()
        
        # Default settings if not found
        if not settings:
            settings = ("everyone", "everyone")
    except Exception as e:
        flash(f"Error retrieving user settings: {str(e)}", "error")
        settings = ("everyone", "everyone")
    
    # Check Spotify connection status
    spotify_connected = session.get('spotify_connected', False)
    spotify_scrobbling_enabled = session.get('spotify_scrobbling_enabled', True)
    
    # Close database connection
    conn.close()
    
    return render_template(
        "settings.html",
        user_info=user_info,
        settings=settings,
        impersonation_privacy=settings[0],
        events_privacy=settings[1],
        spotify_connected=spotify_connected,
        spotify_scrobbling_enabled=spotify_scrobbling_enabled
    )

@profile_bp.route("/connect_spotify")
def connect_spotify():
    """Connect user account to Spotify"""
    if "user_id" not in session:
        flash("You must be logged in to connect to Spotify.", "error")
        return redirect(url_for("auth.login"))
    
    # Get client ID and redirect URI from config
    client_id = current_app.config.get('SPOTIFY_CLIENT_ID')
    
    # Use the correct redirect URI format
    redirect_uri = "http://localhost:5000/spotify_callback"
    
    # Define the scopes needed for the application
    scope = "user-read-recently-played user-top-read user-read-currently-playing"
    
    # Properly encode scopes
    encoded_scope = requests.utils.quote(scope)
    
    # Create the authorization URL with proper encoding
    auth_url = f"https://accounts.spotify.com/authorize" \
               f"?client_id={client_id}" \
               f"&response_type=code" \
               f"&redirect_uri={requests.utils.quote(redirect_uri)}" \
               f"&scope={encoded_scope}"
    
    return redirect(auth_url)

@profile_bp.route("/spotify_callback")
def spotify_callback():
    """Callback for Spotify OAuth"""
    if "user_id" not in session:
        flash("You must be logged in to connect to Spotify.", "error")
        return redirect(url_for("auth.login"))
    
    # Get the authorization code from the callback
    error = request.args.get('error')
    code = request.args.get('code')
    
    if error or not code:
        flash("Failed to connect to Spotify. Please try again.", "error")
        return redirect(url_for('profile.user_settings'))
    
    # Exchange the code for an access token
    client_id = current_app.config.get('SPOTIFY_CLIENT_ID')
    client_secret = current_app.config.get('SPOTIFY_CLIENT_SECRET')
    # Use the same redirect URI as in the connect_spotify route
    redirect_uri = "http://localhost:5000/spotify_callback"
    
    try:
        # Make the token exchange request
        token_url = 'https://accounts.spotify.com/api/token'
        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'client_secret': client_secret
        }
        
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        token_info = response.json()
        
        # Store the tokens in the database or session
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if user already has spotify settings
        cur.execute("SELECT user_id FROM user_spotify_settings WHERE user_id = %s", (session['user_id'],))
        existing = cur.fetchone()
        
        if existing:
            # Update existing settings
            cur.execute(
                """
                UPDATE user_spotify_settings 
                SET access_token = %s, refresh_token = %s, token_expiry = %s, enabled = TRUE
                WHERE user_id = %s
                """,
                (
                    token_info['access_token'], 
                    token_info['refresh_token'], 
                    datetime.now().timestamp() + token_info['expires_in'],
                    session['user_id']
                )
            )
        else:
            # Insert new settings
            cur.execute(
                """
                INSERT INTO user_spotify_settings 
                (user_id, access_token, refresh_token, token_expiry, enabled)
                VALUES (%s, %s, %s, %s, TRUE)
                """,
                (
                    session['user_id'], 
                    token_info['access_token'], 
                    token_info['refresh_token'], 
                    datetime.now().timestamp() + token_info['expires_in']
                )
            )
        
        conn.commit()
        conn.close()
        
        # Set the session flag to indicate connected status
        session['spotify_connected'] = True
        session['spotify_scrobbling_enabled'] = True
        
        flash("Successfully connected to Spotify!", "success")
        return redirect(url_for('profile.user_settings') + "#spotify-settings")
        
    except requests.exceptions.RequestException as e:
        flash(f"Error connecting to Spotify: {str(e)}", "error")
        return redirect(url_for('profile.user_settings'))

@profile_bp.route("/upload_streaming_data", methods=["GET", "POST"])
def upload_streaming_data():
    """Handle streaming data upload."""
    logger.info(f"=== UPLOAD PROCESS STARTED ===")
    logger.info(f"Request method: {request.method}")
    
    if "user_id" not in session:
        logger.warning("Upload attempt without user session")
        flash("You must be logged in to upload data.", "error")
        return redirect(url_for("auth.login"))
    
    user_id = session.get("user_id")
    logger.info(f"Upload initiated by user_id: {user_id}")
    
    try:
        if request.method == "POST":
            logger.info("Processing POST request for file upload")
            
            # Debug request content length
            content_length = request.content_length
            logger.info(f"Request content length: {content_length} bytes ({content_length/(1024*1024):.2f}MB)")
            logger.info(f"App MAX_CONTENT_LENGTH: {current_app.config['MAX_CONTENT_LENGTH']} bytes ({current_app.config['MAX_CONTENT_LENGTH']/(1024*1024):.2f}MB)")
            
            # Check if the request content length exceeds our max
            if content_length and content_length > current_app.config['MAX_CONTENT_LENGTH']:
                logger.error(f"Request content length ({content_length/(1024*1024):.2f}MB) exceeds MAX_CONTENT_LENGTH ({current_app.config['MAX_CONTENT_LENGTH']/(1024*1024):.2f}MB)")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        "success": False, 
                        "message": f"The uploaded file is too large. Maximum size is {current_app.config['MAX_CONTENT_LENGTH']/(1024*1024):.0f}MB."
                    }), 413
                flash(f"The uploaded file is too large. Maximum size is {current_app.config['MAX_CONTENT_LENGTH']/(1024*1024):.0f}MB.", "error")
                return redirect(request.url)
            
            # Check if files were uploaded
            if 'streaming_data' not in request.files:
                logger.warning("No 'streaming_data' in request.files")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    logger.info("Returning AJAX response for missing files")
                    return jsonify({"success": False, "message": "No files selected."}), 400
                flash("No files selected.", "error")
                return redirect(request.url)
            
            files = request.files.getlist('streaming_data')
            logger.info(f"Number of files submitted: {len(files)}")
            
            if not files or files[0].filename == '':
                logger.warning("No files selected or first file has empty filename")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"success": False, "message": "No files selected."}), 400
                flash("No files selected.", "error")
                return redirect(request.url)
            
            # Log file sizes
            for idx, file in enumerate(files):
                try:
                    # Attempt to get file size - this might fail with large files
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)  # Reset file pointer to beginning
                    logger.info(f"File {idx+1}: {file.filename}, Size: {file_size} bytes ({file_size/(1024*1024):.2f}MB)")
                except Exception as e:
                    logger.error(f"Error getting file size for {file.filename}: {str(e)}")
            
            # Process the uploaded files
            try:
                # Save files to temporary location
                temp_files = []
                upload_ids = []
                logger.info("Starting to process individual files")
                
                for idx, file in enumerate(files):
                    logger.info(f"Processing file {idx+1}/{len(files)}: {file.filename}")
                    
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        logger.info(f"Secured filename: {filename}")
                        
                        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                        logger.info(f"Target filepath: {filepath}")
                        
                        try:
                            file.save(filepath)
                            logger.info(f"File saved successfully at: {filepath}")
                            
                            # Get file size for logging
                            file_size = os.path.getsize(filepath)
                            logger.info(f"File size: {file_size} bytes ({file_size/(1024*1024):.2f} MB)")
                            
                            temp_files.append(filepath)
                        except Exception as file_save_error:
                            logger.error(f"Error saving file: {str(file_save_error)}")
                            logger.error(traceback.format_exc())
                            continue
                        
                        # Track the upload in the database with initial processing status
                        conn = get_db_connection()
                        cur = conn.cursor()
                        try:
                            logger.info(f"Tracking file in database: {filename}")
                            cur.execute(
                                """
                                INSERT INTO user_uploads (user_id, file_name, file_path, processing, processed)
                                VALUES (%s, %s, %s, %s, %s)
                                RETURNING upload_id
                                """,
                                (session['user_id'], filename, filepath, False, False)
                            )
                            upload_id = cur.fetchone()[0]
                            upload_ids.append(upload_id)
                            logger.info(f"File tracked with upload_id: {upload_id}")
                            conn.commit()
                            logger.info("Database commit successful")
                        except Exception as db_error:
                            logger.error(f"Database error tracking upload: {str(db_error)}")
                            logger.error(traceback.format_exc())
                            conn.rollback()
                            logger.info("Database rollback performed")
                        finally:
                            cur.close()
                            conn.close()
                            logger.info("Database connection closed")
                    else:
                        logger.warning(f"File skipped - invalid file or filename: {file.filename}")
                
                logger.info(f"Total files saved: {len(temp_files)}")
                logger.info(f"Total uploads tracked: {len(upload_ids)}")
                
                # Process the files - try to use Celery, fall back to direct processing
                if temp_files:
                    logger.info("Attempting to process files with Celery")
                    try:
                        # Try to process asynchronously with Celery
                        from ..tasks.data_processing import process_streaming_data
                        task = process_streaming_data.delay(temp_files, session['user_id'])
                        logger.info(f"Celery task dispatched successfully. Task ID: {task.id}")
                        success_message = "Your streaming data is being processed. This may take a few minutes."
                    except Exception as celery_error:
                        logger.error(f"Error using Celery for processing: {str(celery_error)}")
                        logger.error(traceback.format_exc())
                        
                        # Fall back to direct processing if Celery fails
                        logger.info("Falling back to direct processing")
                        try:
                            from ..tasks.data_processing import process_streaming_data as direct_process
                            # Call the function directly instead of as a Celery task
                            logger.info("Starting direct file processing")
                            result = direct_process(temp_files, session['user_id'])
                            logger.info(f"Direct processing complete. Result: {result}")
                            success_message = f"Your streaming data has been processed. {result.get('successful_entries', 0)} entries imported."
                        except Exception as direct_error:
                            logger.error(f"Error in direct processing: {str(direct_error)}")
                            logger.error(traceback.format_exc())
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return jsonify({"success": False, "message": f"Error processing data: {str(direct_error)}"}), 500
                            flash(f"Error processing data: {str(direct_error)}", "error")
                            return redirect(request.url)
                    
                    logger.info(f"Processing initiated successfully: {success_message}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        logger.info("Returning successful AJAX response")
                        return jsonify({
                            "success": True, 
                            "message": success_message,
                            "upload_ids": upload_ids
                        })
                    flash(success_message, "success")
                else:
                    logger.warning("No valid files to process")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({"success": False, "message": "No valid files were uploaded."}), 400
                    flash("No valid files were uploaded.", "error")
                    
            except Exception as processing_error:
                logger.error(f"Unexpected error during file processing: {str(processing_error)}")
                logger.error(traceback.format_exc())
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"success": False, "message": f"Error processing files: {str(processing_error)}"}), 500
                flash(f"Error processing files: {str(processing_error)}", "error")
            
            logger.info("Upload process complete, redirecting user")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": True, "redirect": url_for("profile.user_settings")})
            return redirect(url_for("profile.user_settings"))
    
    except RequestEntityTooLarge:
        logger.error("RequestEntityTooLarge exception caught - file too large")
        logger.error(f"Request content length exceeds Flask's MAX_CONTENT_LENGTH: {current_app.config['MAX_CONTENT_LENGTH']/(1024*1024):.2f}MB")
        max_size_mb = current_app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
        error_message = f"The uploaded file is too large. Maximum size is {max_size_mb:.0f}MB."
        logger.error(error_message)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                "success": False, 
                "message": error_message
            }), 413
        flash(error_message, "error")
        return redirect(request.url)
    except Exception as e:
        logger.error(f"Unexpected critical error in upload process: {str(e)}")
        logger.error(traceback.format_exc())
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
        flash(f"An unexpected error occurred: {str(e)}", "error")
        return redirect(request.url)
    
    logger.info("Rendering upload_data.html template for GET request")
    return render_template("upload_data.html")

@profile_bp.route("/customize_hall_of_fame", methods=["GET", "POST"])
def customize_hall_of_fame():
    """Customize user's hall of fame."""
    if "user_id" not in session:
        flash("You must be logged in to customize your hall of fame.", "error")
        return redirect(url_for("auth.login"))
    
    user_id = session["user_id"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        try:
            # Clear existing hall of fame entries
            cur.execute("DELETE FROM user_hall_of_fame WHERE user_id = %s", (user_id,))
            
            # Process artist selections
            for position in range(1, 4):
                artist_id = request.form.get(f"artist_{position}")
                if artist_id:
                    cur.execute(
                        """
                        INSERT INTO user_hall_of_fame (user_id, item_type, item_id, position)
                        VALUES (%s, 'artist', %s, %s)
                        """,
                        (user_id, artist_id, position)
                    )
            
            # Process album selections
            for position in range(1, 4):
                album_id = request.form.get(f"album_{position}")
                if album_id:
                    cur.execute(
                        """
                        INSERT INTO user_hall_of_fame (user_id, item_type, item_id, position)
                        VALUES (%s, 'album', %s, %s)
                        """,
                        (user_id, album_id, position)
                    )
            
            # Process track selections
            for position in range(1, 4):
                track_id = request.form.get(f"track_{position}")
                if track_id:
                    cur.execute(
                        """
                        INSERT INTO user_hall_of_fame (user_id, item_type, item_id, position)
                        VALUES (%s, 'track', %s, %s)
                        """,
                        (user_id, track_id, position)
                    )
            
            conn.commit()
            flash("Your Hall of Fame has been updated.", "success")
            return redirect(url_for("profile.profile"))
            
        except Exception as e:
            conn.rollback()
            flash(f"Error updating Hall of Fame: {str(e)}", "error")
        finally:
            conn.close()
    
    # Get current hall of fame selections
    try:
        cur.execute(
            """
            SELECT item_type, item_id, position
            FROM user_hall_of_fame
            WHERE user_id = %s
            """,
            (user_id,)
        )
        
        hof_selections = {
            "artists": {},
            "albums": {},
            "tracks": {}
        }
        
        for item_type, item_id, position in cur.fetchall():
            if item_type == "artist":
                hof_selections["artists"][position] = item_id
            elif item_type == "album":
                hof_selections["albums"][position] = item_id
            elif item_type == "track":
                hof_selections["tracks"][position] = item_id
        
        # Get top artists, albums, and tracks for selection
        top_artists = get_top_items(cur, "artist", user_id, limit=20)
        top_albums = get_top_items(cur, "album", user_id, limit=20)
        top_tracks = get_top_items(cur, "track", user_id, limit=20)
        
    except Exception as e:
        flash(f"Error retrieving data: {str(e)}", "error")
        hof_selections = {"artists": {}, "albums": {}, "tracks": {}}
        top_artists = []
        top_albums = []
        top_tracks = []
    finally:
        conn.close()
    
    return render_template(
        "customize_hof.html",
        hof_selections=hof_selections,
        top_artists=top_artists,
        top_albums=top_albums,
        top_tracks=top_tracks
    )

@profile_bp.route("/previous_uploads", methods=["GET"])
def previous_uploads():
    """Display previous uploads for the user."""
    logger.info("=== PREVIOUS UPLOADS PAGE REQUESTED ===")
    
    if "user_id" not in session:
        logger.warning("Previous uploads page requested without user session")
        flash("You must be logged in to view previous uploads.", "error")
        return redirect(url_for("auth.login"))
    
    user_id = session["user_id"]
    logger.info(f"Previous uploads requested for user_id: {user_id}")
    
    # Connect to the database
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        logger.info("Querying database for user uploads")
        # Query for previous uploads - removed DISTINCT to show all uploads
        cur.execute(
            """
            SELECT upload_id, file_name, file_path, created_at, 
                   CASE WHEN processed = TRUE THEN 'Processed' 
                        WHEN processing = TRUE THEN 'Processing'
                        ELSE 'Pending' END as status
            FROM user_uploads
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        uploads = cur.fetchall()
        logger.info(f"Found {len(uploads)} upload records for user")
        
        # Format the results
        formatted_uploads = []
        for upload in uploads:
            logger.info(f"Processing upload record: ID={upload[0]}, Filename={upload[1]}")
            # Get file size if file exists
            file_size = "Unknown"
            if os.path.exists(upload[2]):
                file_size = os.path.getsize(upload[2])
                logger.info(f"File exists at {upload[2]}, size: {file_size} bytes")
                # Convert to readable format
                if file_size < 1024:
                    file_size = f"{file_size} bytes"
                elif file_size < 1024 * 1024:
                    file_size = f"{file_size / 1024:.1f} KB"
                else:
                    file_size = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                logger.warning(f"File does not exist at path: {upload[2]}")
            
            formatted_uploads.append({
                "upload_id": upload[0],
                "file_name": upload[1],
                "file_path": upload[2],
                "created_at": upload[3].strftime("%Y-%m-%d %H:%M:%S") if upload[3] else "Unknown",
                "status": upload[4],
                "file_size": file_size
            })
        
    except Exception as e:
        logger.error(f"Error fetching previous uploads: {str(e)}")
        logger.error(traceback.format_exc())
        uploads = []
        formatted_uploads = []
    finally:
        cur.close()
        conn.close()
        logger.info("Database connection closed")
    
    logger.info(f"Rendering previous_uploads.html with {len(formatted_uploads)} uploads")
    return render_template("previous_uploads.html", uploads=formatted_uploads)

@profile_bp.route("/check_upload_status", methods=["GET"])
def check_upload_status():
    """Check the status of user uploads and return as JSON."""
    logger.info("=== CHECKING UPLOAD STATUS ===")
    
    if "user_id" not in session:
        logger.warning("Upload status check requested without user session")
        return jsonify({"success": False, "message": "You must be logged in to check upload status."}), 401
    
    user_id = session["user_id"]
    logger.info(f"Upload status check for user_id: {user_id}")
    
    # Connect to the database
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        logger.info("Querying database for upload status")
        # Query for uploads with status
        cur.execute(
            """
            SELECT upload_id, file_name, file_path, created_at, 
                   CASE WHEN processed = TRUE THEN 'Processed' 
                        WHEN processing = TRUE THEN 'Processing'
                        ELSE 'Pending' END as status
            FROM user_uploads
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        uploads = cur.fetchall()
        logger.info(f"Found {len(uploads)} upload records")
        
        # Format the results
        formatted_uploads = []
        for upload in uploads:
            logger.info(f"Processing upload status: ID={upload[0]}, Filename={upload[1]}, Status={upload[4]}")
            # Get file size if file exists
            file_size = "Unknown"
            if os.path.exists(upload[2]):
                file_size = os.path.getsize(upload[2])
                # Convert to readable format
                if file_size < 1024:
                    file_size = f"{file_size} bytes"
                elif file_size < 1024 * 1024:
                    file_size = f"{file_size / 1024:.1f} KB"
                else:
                    file_size = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                logger.warning(f"File not found at path: {upload[2]}")
            
            formatted_uploads.append({
                "upload_id": upload[0],
                "file_name": upload[1],
                "file_path": upload[2],
                "created_at": upload[3].strftime("%Y-%m-%d %H:%M:%S") if upload[3] else "Unknown",
                "status": upload[4],
                "file_size": file_size
            })
        
        logger.info(f"Returning JSON response with {len(formatted_uploads)} upload statuses")
        return jsonify({"success": True, "uploads": formatted_uploads})
        
    except Exception as e:
        logger.error(f"Error fetching upload status: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"Error checking upload status: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()
        logger.info("Database connection closed")

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    ALLOWED_EXTENSIONS = {'json', 'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS