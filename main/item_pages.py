from flask import Blueprint, render_template, session, redirect, url_for, abort, g, request
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps

# Import the database connection function
from app.utils.db import get_db_connection

item_pages = Blueprint('item_pages', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@item_pages.route('/artist/<int:artist_id>')
@login_required
def artist_page(artist_id):
    """Display details for a specific artist."""
    user_id = session.get('user_id')
    
    # Connect to database using the imported function
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get artist info
        cur.execute(
            """
            SELECT artist_name 
            FROM artists 
            WHERE artist_id = %s
            """, 
            (artist_id,)
        )
        result = cur.fetchone()
        
        if not result:
            abort(404)
            
        artist_name = result[0]
        
        # Get user stats for this artist
        cur.execute(
            """
            SELECT 
                COUNT(*) as total_streams,
                ROUND(SUM(lh.ms_played) / 3600000.0, 1) as total_hours
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            WHERE lh.user_id = %s AND a.artist_id = %s
            """,
            (user_id, artist_id)
        )
        stats_result = cur.fetchone()
        total_streams = stats_result[0] if stats_result else 0
        
        # Get user's top track for this artist
        cur.execute(
            """
            SELECT 
                t.track_id,
                t.track_name,
                COUNT(*) as stream_count
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            WHERE lh.user_id = %s AND a.artist_id = %s
            GROUP BY t.track_id, t.track_name
            ORDER BY stream_count DESC
            LIMIT 1
            """,
            (user_id, artist_id)
        )
        top_track = cur.fetchone()
        
        # Get user's top album for this artist
        cur.execute(
            """
            SELECT 
                a.album_id,
                a.album_name,
                COUNT(*) as stream_count
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            WHERE lh.user_id = %s AND a.artist_id = %s
            GROUP BY a.album_id, a.album_name
            ORDER BY stream_count DESC
            LIMIT 1
            """,
            (user_id, artist_id)
        )
        top_album = cur.fetchone()
        
        # Get all albums by this artist with user's stats
        cur.execute(
            """
            SELECT 
                a.album_id,
                a.album_name,
                COALESCE(a.image_url, NULL) as image_url,
                COUNT(lh.id) as stream_count
            FROM albums a
            LEFT JOIN tracks t ON t.album_id = a.album_id
            LEFT JOIN listening_history lh ON lh.track_id = t.track_id AND lh.user_id = %s
            WHERE a.artist_id = %s
            GROUP BY a.album_id, a.album_name, a.image_url
            ORDER BY stream_count DESC
            """,
            (user_id, artist_id)
        )
        albums = cur.fetchall()
        
        # Get app-wide stats for this artist
        cur.execute(
            """
            SELECT 
                COUNT(*) as total_streams
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            WHERE a.artist_id = %s
            """,
            (artist_id,)
        )
        app_total_streams = cur.fetchone()[0]
        
        # Get app's top track for this artist
        cur.execute(
            """
            SELECT 
                t.track_name,
                COUNT(*) as stream_count
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            WHERE a.artist_id = %s
            GROUP BY t.track_name
            ORDER BY stream_count DESC
            LIMIT 1
            """,
            (artist_id,)
        )
        app_top_track = cur.fetchone()
        
        # Get app's top album for this artist
        cur.execute(
            """
            SELECT 
                a.album_name,
                COUNT(*) as stream_count
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            JOIN albums a ON t.album_id = a.album_id
            WHERE a.artist_id = %s
            GROUP BY a.album_name
            ORDER BY stream_count DESC
            LIMIT 1
            """,
            (artist_id,)
        )
        app_top_album = cur.fetchone()
        
        # Build user stats dictionary
        user_stats = {
            'total_streams': total_streams,
            'top_track_id': top_track[0] if top_track else None,
            'top_track_name': top_track[1] if top_track else "None",
            'top_album_id': top_album[0] if top_album else None,
            'top_album_name': top_album[1] if top_album else "None"
        }
        
        # Build app stats dictionary
        app_stats = {
            'total_streams': app_total_streams,
            'top_track_name': app_top_track[0] if app_top_track else "None",
            'top_album_name': app_top_album[0] if app_top_album else "None"
        }
        
        return render_template(
            'artist_page.html',
            artist_id=artist_id,
            artist_name=artist_name,
            user_stats=user_stats,
            app_stats=app_stats,
            albums=albums
        )
        
    finally:
        cur.close()
        conn.close()

@item_pages.route('/album/<int:album_id>')
@login_required
def album_page(album_id):
    """Display details for a specific album."""
    user_id = session.get('user_id')
    
    # Connect to database using the imported function
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get album info
        cur.execute(
            """
            SELECT a.album_name, ar.artist_id, ar.artist_name 
            FROM albums a
            JOIN artists ar ON a.artist_id = ar.artist_id
            WHERE a.album_id = %s
            """, 
            (album_id,)
        )
        result = cur.fetchone()
        
        if not result:
            abort(404)
            
        album_name, artist_id, artist_name = result
        
        # Get user stats for this album
        cur.execute(
            """
            SELECT 
                COUNT(*) as total_streams,
                ROUND(SUM(lh.ms_played) / 3600000.0, 1) as total_hours
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            WHERE lh.user_id = %s AND t.album_id = %s
            """,
            (user_id, album_id)
        )
        stats_result = cur.fetchone()
        total_streams = stats_result[0] if stats_result else 0
        hours_listened = stats_result[1] if stats_result else 0
        
        # Get user's top track for this album
        cur.execute(
            """
            SELECT 
                t.track_id,
                t.track_name,
                COUNT(*) as stream_count
            FROM listening_history lh
            JOIN tracks t ON lh.track_id = t.track_id
            WHERE lh.user_id = %s AND t.album_id = %s
            GROUP BY t.track_id, t.track_name
            ORDER BY stream_count DESC
            LIMIT 1
            """,
            (user_id, album_id)
        )
        top_track = cur.fetchone()
        
        # Get all tracks from this album with user's stats
        cur.execute(
            """
            SELECT 
                t.track_id,
                t.track_name,
                COALESCE(t.image_url, al.image_url) as image_url,
                COUNT(lh.id) as stream_count
            FROM tracks t
            LEFT JOIN albums al ON t.album_id = al.album_id
            LEFT JOIN listening_history lh ON lh.track_id = t.track_id AND lh.user_id = %s
            WHERE t.album_id = %s
            GROUP BY t.track_id, t.track_name, t.image_url, al.image_url
            ORDER BY stream_count DESC
            """,
            (user_id, album_id)
        )
        tracks = cur.fetchall()
        
        # Build user stats dictionary
        user_stats = {
            'total_streams': total_streams,
            'hours_listened': hours_listened,
            'top_track_id': top_track[0] if top_track else None,
            'top_track_name': top_track[1] if top_track else "None"
        }
        
        return render_template(
            'album_page.html',
            album_id=album_id,
            album_name=album_name,
            artist_id=artist_id,
            artist_name=artist_name,
            user_stats=user_stats,
            tracks=tracks
        )
        
    finally:
        cur.close()
        conn.close()

@item_pages.route('/track/<int:track_id>')
@login_required
def track_page(track_id):
    """Display details for a specific track."""
    user_id = session.get('user_id')
    
    # Connect to database using the imported function
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get track info
        cur.execute(
            """
            SELECT 
                t.track_name, 
                a.album_id,
                a.album_name, 
                ar.artist_id,
                ar.artist_name,
                a.image_url
            FROM tracks t
            JOIN albums a ON t.album_id = a.album_id
            JOIN artists ar ON a.artist_id = ar.artist_id
            WHERE t.track_id = %s
            """, 
            (track_id,)
        )
        result = cur.fetchone()
        
        if not result:
            abort(404)
            
        track_name, album_id, album_name, artist_id, artist_name, image_url = result
        
        # Get user stats for this track
        cur.execute(
            """
            SELECT 
                COUNT(*) as total_streams,
                ROUND(SUM(ms_played) / 3600000.0, 1) as total_hours
            FROM listening_history
            WHERE user_id = %s AND track_id = %s
            """,
            (user_id, track_id)
        )
        stats_result = cur.fetchone()
        total_streams = stats_result[0] if stats_result else 0
        hours_listened = stats_result[1] if stats_result else 0
        
        return render_template(
            'track_page.html',
            track_id=track_id,
            track_name=track_name,
            album_id=album_id,
            album_name=album_name,
            artist_id=artist_id,
            artist_name=artist_name,
            image_url=image_url,
            total_streams=total_streams,
            hours_listened=hours_listened
        )
        
    finally:
        cur.close()
        conn.close() 