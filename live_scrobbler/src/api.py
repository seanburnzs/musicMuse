"""
API module for the live scrobbler service.
"""
import logging
import json
from datetime import datetime
from flask import Flask, request, redirect, url_for, jsonify, session
from urllib.parse import urlencode

from config import SECRET_KEY, SPOTIFY_REDIRECT_URI, validate_settings
from .database import get_connection, release_connection, get_active_users, get_user
from .spotify_client import SpotifyClient
from .tasks import process_auth_callback

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = SECRET_KEY

# Validate settings
validate_settings()

@app.before_request
def before_request():
    """Set up logging for each request."""
    logger.info(f"Request: {request.method} {request.path}")

@app.route("/")
def index():
    """Home page."""
    return jsonify({
        "service": "Live Scrobbler",
        "status": "running",
        "version": "1.0.0"
    })

@app.route("/auth/login/<int:user_id>")
def login(user_id):
    """
    Initiate the Spotify OAuth flow for a specific user.
    Redirects the user to the Spotify authorization page.
    
    Args:
        user_id: User ID from your application
    """
    # Store the user_id in the session
    session["user_id"] = user_id
    
    # Check if user exists
    conn = None
    try:
        conn = get_connection()
        user = get_user(conn, user_id)
        if not user:
            return jsonify({"error": f"User {user_id} not found"}), 404
    finally:
        if conn:
            release_connection(conn)
    
    # Initialize Spotify client and get auth URL
    spotify = SpotifyClient()
    auth_url = spotify.get_auth_url()
    
    # Redirect to Spotify authorization page
    return redirect(auth_url)

@app.route("/auth/callback")
def callback():
    """
    Handle the Spotify OAuth callback.
    Exchanges the authorization code for access and refresh tokens.
    """
    code = request.args.get("code")
    if not code:
        error = request.args.get("error", "Unknown error")
        return jsonify({"error": f"Authorization failed: {error}"}), 400
    
    # Get the user_id from the session
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "No user ID found in session"}), 400
    
    # Process the callback asynchronously
    task = process_auth_callback.delay(code, user_id)
    
    # Store the task ID in the session
    session["auth_task_id"] = task.id
    
    # Redirect to the status page
    return redirect(url_for("auth_status"))

@app.route("/auth/status")
def auth_status():
    """
    Check the status of the authentication process.
    """
    task_id = session.get("auth_task_id")
    if not task_id:
        return jsonify({"error": "No authentication in progress"}), 400
    
    # Check the task status
    task = process_auth_callback.AsyncResult(task_id)
    
    if task.state == "PENDING":
        return jsonify({"status": "pending", "message": "Authentication in progress"})
    elif task.state == "SUCCESS":
        result = task.result
        if "error" in result:
            return jsonify({
                "status": "error",
                "message": result["error"]
            }), 400
        
        return jsonify({
            "status": "success",
            "message": "Authentication successful",
            "user_id": result["user_id"],
            "spotify_id": result["spotify_id"]
        })
    elif task.state == "FAILURE":
        return jsonify({
            "status": "error",
            "message": "Authentication failed",
            "error": str(task.result)
        }), 400
    else:
        return jsonify({"status": task.state, "message": "Authentication in progress"})

@app.route("/users/<int:user_id>")
def get_user_info(user_id):
    """
    Get a user's profile.
    
    Args:
        user_id: User ID
    """
    conn = None
    try:
        conn = get_connection()
        user = get_user(conn, user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify(user)
    finally:
        if conn:
            release_connection(conn)

@app.route("/users/<int:user_id>/scrobbles")
def get_user_scrobbles(user_id):
    """
    Get the user's scrobbles.
    
    Args:
        user_id: User ID
    """
    # Parse query parameters
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    
    # Get scrobbles from database
    conn = None
    try:
        conn = get_connection()
        
        # Check if user exists
        user = get_user(conn, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 
                lh.timestamp, 
                t.track_name, 
                a.album_name, 
                ar.artist_name, 
                lh.ms_played,
                t.image_url as track_image_url,
                a.image_url as album_image_url,
                ar.image_url as artist_image_url
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            JOIN artists ar ON a.artist_id = ar.artist_id
            WHERE lh.user_id = %s
            ORDER BY lh.timestamp DESC
            LIMIT %s OFFSET %s;
            """,
            (user_id, limit, offset)
        )
        scrobbles = cur.fetchall()
        
        # Get total count
        cur.execute(
            "SELECT COUNT(*) FROM listening_history WHERE user_id = %s;",
            (user_id,)
        )
        total = cur.fetchone()[0]
        cur.close()
        
        # Format scrobbles
        formatted_scrobbles = []
        for scrobble in scrobbles:
            formatted_scrobbles.append({
                "timestamp": scrobble[0].isoformat(),
                "track_name": scrobble[1],
                "album_name": scrobble[2],
                "artist_name": scrobble[3],
                "ms_played": scrobble[4],
                "track_image_url": scrobble[5],
                "album_image_url": scrobble[6],
                "artist_image_url": scrobble[7]
            })
        
        return jsonify({
            "scrobbles": formatted_scrobbles,
            "total": total,
            "limit": limit,
            "offset": offset
        })
    finally:
        if conn:
            release_connection(conn)

@app.route("/health")
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

@app.route("/metrics")
def metrics():
    """Metrics endpoint."""
    conn = None
    try:
        conn = get_connection()
        
        # Get active users count
        active_users = get_active_users(conn)
        active_users_count = len(active_users)
        
        # Get total scrobbles count
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM listening_history;")
        total_scrobbles = cur.fetchone()[0]
        
        # Get scrobbles in the last 24 hours
        cur.execute(
            """
            SELECT COUNT(*) FROM listening_history
            WHERE timestamp > NOW() - INTERVAL '24 hours';
            """
        )
        recent_scrobbles = cur.fetchone()[0]
        cur.close()
        
        return jsonify({
            "active_users": active_users_count,
            "total_scrobbles": total_scrobbles,
            "recent_scrobbles": recent_scrobbles
        })
    finally:
        if conn:
            release_connection(conn)

if __name__ == "__main__":
    app.run(debug=True) 