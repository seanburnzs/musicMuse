from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, jsonify
import psycopg2
import json
import os
from datetime import datetime, timedelta, date
import random

# Create blueprint
analytics_bp = Blueprint('analytics', __name__)

# Import necessary functions
from ..utils.db import get_db_connection
from ..utils.date_utils import get_date_range
from ..utils.error_handlers import db_error_handler, api_error_handler
from ..musicnlp import process_query

def fetch_top_data(entity, time_range, time_unit, custom_start=None, custom_end=None, limit=20, offset=0):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get current user ID
    user_id = session.get("user_id")
    if not user_id:
        conn.close()
        return []
    
    # Get date range
    date_filter, date_params = get_date_range(time_range, custom_start, custom_end)
    
    # Time unit conversion factor and rounding
    time_divisor = 1000 * 60  # Convert ms to minutes
    decimal_places = 0  # Default for minutes - whole numbers
    
    if time_unit == "hours":
        time_divisor = time_divisor * 60  # Convert minutes to hours
        decimal_places = 0  # For hours - round to nearest tenth
    
    # Build SQL query based on entity type
    if entity == "artists":
        query = """
        SELECT a.artist_id, a.artist_name, COUNT(lh.id) as play_count, 
               ROUND(SUM(lh.ms_played) / %s, %s) as total_time, 
               a.image_url
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s """ + date_filter + """
        GROUP BY a.artist_id, a.artist_name, a.image_url
        ORDER BY play_count DESC
        LIMIT %s OFFSET %s
        """
        params = [time_divisor, decimal_places, user_id] + date_params + [limit, offset]
    elif entity == "albums":
        query = """
        SELECT al.album_id, al.album_name, a.artist_name, COUNT(lh.id) as play_count, 
               ROUND(SUM(lh.ms_played) / %s, %s) as total_time, 
               al.image_url, a.artist_id
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s """ + date_filter + """
        GROUP BY al.album_id, al.album_name, a.artist_name, al.image_url, a.artist_id
        ORDER BY play_count DESC
        LIMIT %s OFFSET %s
        """
        params = [time_divisor, decimal_places, user_id] + date_params + [limit, offset]
    else:  # tracks
        query = """
        SELECT t.track_id, t.track_name, a.artist_name, COUNT(lh.id) as play_count,
               ROUND(SUM(lh.ms_played) / %s, %s) as total_time, 
               t.image_url, al.album_id, a.artist_id
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s """ + date_filter + """
        GROUP BY t.track_id, t.track_name, a.artist_name, t.image_url, al.album_id, a.artist_id
        ORDER BY play_count DESC
        LIMIT %s OFFSET %s
        """
        params = [time_divisor, decimal_places, user_id] + date_params + [limit, offset]
    
    cur.execute(query, params)
    items = cur.fetchall()
    
    # Format the data according to what the templates expect
    formatted_items = []
    for item in items:
        if entity == "artists":
            # artist_name, total_streams, total_time
            formatted_items.append((item[1], item[2], item[3], item[4], item[0]))  # name, streams, time, image_url, id
        elif entity == "albums":
            # album_name, artist_name, total_streams, total_time
            formatted_items.append((item[1], item[2], item[3], item[4], item[5], item[0], item[6]))  # album, artist, streams, time, img, album_id, artist_id
        else:  # tracks
            # track_name, artist_name, total_streams, total_time
            formatted_items.append((item[1], item[2], item[3], item[4], item[5], item[6], item[0], item[7]))  # track, artist, streams, time, img, album_id, track_id, artist_id
    
    conn.close()
    return formatted_items

@analytics_bp.route("/top", methods=["GET"])
def top_items():
    """Redirect to top_items_page with the same query parameters."""
    if "user_id" not in session:
        flash("You must be logged in to view this page.", "error")
        return redirect(url_for("auth.login"))
    
    # Get the request parameters
    entity = request.args.get("entity", "tracks")
    
    # Use the entity to determine the type parameter
    type_param = entity
    
    # Forward all other request parameters
    params = request.args.copy()
    
    # Remove entity parameter if it exists and replace with type
    if "entity" in params:
        del params["entity"]
    
    params["type"] = type_param
    
    # Redirect to top_items_page with all parameters
    return redirect(url_for("analytics.top_items_page", **params))

@analytics_bp.route("/top_items", methods=["GET"])
def top_items_page():
    if "user_id" not in session:
        flash("You must be logged in to view this page.", "error")
        return redirect(url_for("auth.login"))
    
    # Get parameters from request
    selected_type = request.args.get("type", "tracks")
    selected_range = request.args.get("time_range", "all_time")
    custom_start = request.args.get("custom_start")
    custom_end = request.args.get("custom_end")
    time_unit = request.args.get("time_unit", "hours")
    
    # Get format parameter for AJAX requests
    format_param = request.args.get("format")
    page = int(request.args.get("page", 1))
    offset = (page - 1) * 20
    
    # Convert time range values to match date_utils function
    # Handle this_week, this_month, etc.
    time_range_map = {
        "this_week": "last_week",
        "this_month": "last_month",
        "this_year": "this_year",
        "year_2024": "year_2024",
        "year_2023": "year_2023",
        "custom": "custom",
        "all_time": "all_time"
    }
    
    db_time_range = time_range_map.get(selected_range, "all_time")
    
    # Fetch data
    items = fetch_top_data(selected_type, db_time_range, time_unit, custom_start, custom_end, limit=20, offset=offset)
    
    # If requesting JSON format (AJAX), return JSON response
    if format_param == "json":
        return jsonify({
            "items": items,
            "type": selected_type
        })
    
    # For HTML response, render the top_items template
    return render_template(
        "top_items.html",
        rows=items,
        selected_type=selected_type,
        selected_range=selected_range,
        time_unit=time_unit,
        custom_start=custom_start,
        custom_end=custom_end
    )

@analytics_bp.route("/music_muse", methods=["GET", "POST"])
@db_error_handler
def music_muse():
    if "user_id" not in session:
        flash("You must be logged in to use Music Muse.", "error")
        return redirect(url_for("auth.login"))
    
    response = None
    query = ""
    
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        
        if query:
            try:
                # Import the MusicMuse class from app.musicnlp.music_muse
                from ..musicnlp.music_muse import MusicMuse
                
                # Create database parameters
                db_params = {
                    "dbname": os.getenv("DB_NAME", "musicmuse_db"),
                    "user": os.getenv("DB_USER", "postgres"),
                    "password": os.getenv("DB_PASSWORD", ""),
                    "host": os.getenv("DB_HOST", "localhost"),
                    "port": int(os.getenv("DB_PORT", "5432"))
                }
                
                # Create MusicMuse instance
                music_muse_instance = MusicMuse(db_params, user_id=session.get("user_id"))
                
                # Execute the query and get the response
                parsed, results = music_muse_instance.execute_query(query)
                response = music_muse_instance.format_response(parsed, results)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                response = f"An error occurred while processing your query: {str(e)}"
    
    # Get personalized suggestions
    suggestions = get_personalized_suggestions()
    
    return render_template(
        "music_muse.html",
        response=response,
        query=query,
        suggestions=suggestions
    )

def format_music_nlp_response(results):
    """Format the NLP response for display as a string"""
    if not results or "error" in results:
        return f"Sorry, I couldn't process that query: {results.get('error', 'Unknown error')}"
    
    # Get the query interpretation if available
    interpretation = results.get("intent", "")
    
    # Get the results data
    data = results.get("results", [])
    entity_type = results.get("metadata", {}).get("entity_type", "track")
    
    if not data:
        return "No results found for your query."
    
    # Format the response based on entity type
    response_lines = []
    
    # Add interpretation if available
    if interpretation:
        response_lines.append(f"I understood your query as: {interpretation}")
        response_lines.append("")  # Empty line for spacing
    
    # Format the header based on entity type
    if entity_type == "track":
        response_lines.append("Here are the tracks you requested:")
    elif entity_type == "album":
        response_lines.append("Here are the albums you requested:")
    elif entity_type == "artist":
        response_lines.append("Here are the artists you requested:")
    else:
        response_lines.append("Here are the results for your query:")
    
    response_lines.append("")  # Empty line for spacing
    
    # Format each result item
    for i, item in enumerate(data, 1):
        if entity_type == "track":
            track_name = item.get("track_name", item.get("name", "Unknown Track"))
            artist_name = item.get("artist_name", item.get("artist", "Unknown Artist"))
            play_count = item.get("play_count", 0)
            response_lines.append(f"{i}. \"{track_name}\" by {artist_name} (Played {play_count} times)")
        
        elif entity_type == "album":
            album_name = item.get("album_name", item.get("name", "Unknown Album"))
            artist_name = item.get("artist_name", item.get("artist", "Unknown Artist"))
            play_count = item.get("play_count", 0)
            response_lines.append(f"{i}. \"{album_name}\" by {artist_name} (Played {play_count} times)")
        
        elif entity_type == "artist":
            artist_name = item.get("artist_name", item.get("name", "Unknown Artist"))
            play_count = item.get("play_count", 0)
            response_lines.append(f"{i}. {artist_name} (Played {play_count} times)")
        
        else:
            # Generic format for other types
            response_lines.append(f"{i}. {item}")
    
    # Join all lines with newlines and return
    return "\n".join(response_lines)

def get_personalized_suggestions():
    # Get personalized query suggestions based on user history
    conn = get_db_connection()
    cur = conn.cursor()
    
    user_id = session.get("user_id")
    suggestions = []
    
    # Get top artist
    cur.execute("""
        SELECT a.artist_name
        FROM listening_history lh
        JOIN tracks t ON lh.track_id = t.track_id
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        WHERE lh.user_id = %s
        GROUP BY a.artist_name
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """, (user_id,))
    
    top_artist = cur.fetchone()
    if top_artist:
        query = f"What are my top {top_artist[0]} songs?"
        suggestions.append({"query": query, "text": query})
    
    # Add generic suggestions
    generic_suggestions = [
        "What are my top albums after 8PM?",
        "What are my top artists on Fridays?"
    ]
    
    for query in generic_suggestions:
        suggestions.append({"query": query, "text": query})
    
    conn.close()
    return suggestions

@analytics_bp.route("/charts")
def charts():
    if "user_id" not in session:
        flash("You must be logged in to view charts.", "error")
        return redirect(url_for("auth.login"))
    
    return render_template("charts.html")

@analytics_bp.route("/api/search_items")
@api_error_handler
def search_items():
    """API endpoint to search for artists, albums, or tracks"""
    item_type = request.args.get("type", "artists")
    query = request.args.get("q", "").strip()
    
    if not query or len(query) < 2:
        return jsonify({"items": []})
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get current user ID
    user_id = session.get("user_id")
    if not user_id:
        conn.close()
        return jsonify({"error": "User not logged in"}), 401
    
    # Build SQL query based on item type
    if item_type == "artists":
        sql = """
        SELECT DISTINCT a.artist_id, a.artist_name, a.image_url
        FROM artists a
        JOIN albums al ON a.artist_id = al.artist_id
        JOIN tracks t ON al.album_id = t.album_id
        JOIN listening_history lh ON t.track_id = lh.track_id
        WHERE lh.user_id = %s AND a.artist_name ILIKE %s
        ORDER BY a.artist_name
        LIMIT 10
        """
        params = (user_id, f"%{query}%")
    elif item_type == "albums":
        sql = """
        SELECT DISTINCT al.album_id, al.album_name, a.artist_name, al.image_url
        FROM albums al
        JOIN artists a ON al.artist_id = a.artist_id
        JOIN tracks t ON al.album_id = t.album_id
        JOIN listening_history lh ON t.track_id = lh.track_id
        WHERE lh.user_id = %s AND (al.album_name ILIKE %s OR a.artist_name ILIKE %s)
        ORDER BY al.album_name
        LIMIT 10
        """
        params = (user_id, f"%{query}%", f"%{query}%")
    else:  # tracks
        sql = """
        SELECT DISTINCT t.track_id, t.track_name, a.artist_name, t.image_url
        FROM tracks t
        JOIN albums al ON t.album_id = al.album_id
        JOIN artists a ON al.artist_id = a.artist_id
        JOIN listening_history lh ON t.track_id = lh.track_id
        WHERE lh.user_id = %s AND (t.track_name ILIKE %s OR a.artist_name ILIKE %s)
        ORDER BY t.track_name
        LIMIT 10
        """
        params = (user_id, f"%{query}%", f"%{query}%")
    
    cur.execute(sql, params)
    results = cur.fetchall()
    
    # Format results based on item type
    items = []
    for result in results:
        if item_type == "artists":
            items.append({
                "id": result[0],
                "name": result[1],
                "image_url": result[2]
            })
        elif item_type == "albums":
            items.append({
                "id": result[0],
                "name": result[1],
                "artist_name": result[2],
                "image_url": result[3]
            })
        else:  # tracks
            items.append({
                "id": result[0],
                "name": result[1],
                "artist_name": result[2],
                "image_url": result[3]
            })
    
    conn.close()
    return jsonify({"items": items})

@analytics_bp.route("/api/generate_chart", methods=["POST"])
@api_error_handler
def generate_chart():
    """API endpoint to generate chart data for selected items"""
    # Get current user ID
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401
    
    # Get request data
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    chart_type = data.get("chart_type", "total")
    time_group = data.get("time_group", "month")
    time_range = data.get("time_range", "all_time")
    custom_start = data.get("custom_start")
    custom_end = data.get("custom_end")
    items = data.get("items", [])
    
    if not items:
        return jsonify({"error": "No items selected"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get date range
    date_filter, date_params = get_date_range(time_range, custom_start, custom_end)
    
    # Generate chart data
    labels = []
    datasets = []
    
    # Generate time labels based on time_group
    if time_group == "month":
        # Generate month labels
        sql_labels = """
        SELECT DISTINCT TO_CHAR(lh.timestamp, 'YYYY-MM') as month_year,
                        TO_CHAR(lh.timestamp, 'Month YYYY') as month_year_label
        FROM listening_history lh
        WHERE lh.user_id = %s """ + date_filter + """
        ORDER BY month_year
        """
        cur.execute(sql_labels, [user_id] + date_params)
        label_results = cur.fetchall()
        
        # Extract month-year values and labels
        month_years = [row[0] for row in label_results]
        labels = [row[1] for row in label_results]
    else:  # year
        # Generate year labels
        sql_labels = """
        SELECT DISTINCT TO_CHAR(lh.timestamp, 'YYYY') as year
        FROM listening_history lh
        WHERE lh.user_id = %s """ + date_filter + """
        ORDER BY year
        """
        cur.execute(sql_labels, [user_id] + date_params)
        label_results = cur.fetchall()
        
        # Extract year values
        labels = [row[0] for row in label_results]
        month_years = labels  # For year grouping, use the same values
    
    # Generate vibrant colors for datasets
    vibrant_colors = [
        '#4361ee', '#3a0ca3', '#7209b7', '#f72585', '#4cc9f0',
        '#ff9e00', '#38b000', '#ff006e', '#2b9348', '#f15bb5',
        '#0077b6', '#9d4edd', '#ef476f', '#fb8500', '#06d6a0',
        '#118ab2', '#073b4c', '#e76f51', '#d62828', '#5390d9'
    ]
    
    # Process each selected item
    for i, item in enumerate(items):
        item_id = item.get("id")
        item_type = item.get("type")
        item_name = item.get("name")
        
        # Skip if missing required data
        if not all([item_id, item_type, item_name]):
            continue
        
        # Assign a color from the vibrant colors list
        color_index = i % len(vibrant_colors)
        color = vibrant_colors[color_index]
        
        # Build SQL query based on item type and time grouping
        if item_type == "artists":
            if time_group == "month":
                sql = """
                SELECT TO_CHAR(lh.timestamp, 'YYYY-MM') as month_year, COUNT(lh.id) as play_count
                FROM listening_history lh
                JOIN tracks t ON lh.track_id = t.track_id
                JOIN albums al ON t.album_id = al.album_id
                JOIN artists a ON al.artist_id = a.artist_id
                WHERE lh.user_id = %s AND a.artist_id = %s """ + date_filter + """
                GROUP BY month_year
                ORDER BY month_year
                """
                params = [user_id, item_id] + date_params
            else:  # year
                sql = """
                SELECT TO_CHAR(lh.timestamp, 'YYYY') as year, COUNT(lh.id) as play_count
                FROM listening_history lh
                JOIN tracks t ON lh.track_id = t.track_id
                JOIN albums al ON t.album_id = al.album_id
                JOIN artists a ON al.artist_id = a.artist_id
                WHERE lh.user_id = %s AND a.artist_id = %s """ + date_filter + """
                GROUP BY year
                ORDER BY year
                """
                params = [user_id, item_id] + date_params
        elif item_type == "albums":
            if time_group == "month":
                sql = """
                SELECT TO_CHAR(lh.timestamp, 'YYYY-MM') as month_year, COUNT(lh.id) as play_count
                FROM listening_history lh
                JOIN tracks t ON lh.track_id = t.track_id
                JOIN albums al ON t.album_id = al.album_id
                WHERE lh.user_id = %s AND al.album_id = %s """ + date_filter + """
                GROUP BY month_year
                ORDER BY month_year
                """
                params = [user_id, item_id] + date_params
            else:  # year
                sql = """
                SELECT TO_CHAR(lh.timestamp, 'YYYY') as year, COUNT(lh.id) as play_count
                FROM listening_history lh
                JOIN tracks t ON lh.track_id = t.track_id
                JOIN albums al ON t.album_id = al.album_id
                WHERE lh.user_id = %s AND al.album_id = %s """ + date_filter + """
                GROUP BY year
                ORDER BY year
                """
                params = [user_id, item_id] + date_params
        else:  # tracks
            if time_group == "month":
                sql = """
                SELECT TO_CHAR(lh.timestamp, 'YYYY-MM') as month_year, COUNT(lh.id) as play_count
                FROM listening_history lh
                WHERE lh.user_id = %s AND lh.track_id = %s """ + date_filter + """
                GROUP BY month_year
                ORDER BY month_year
                """
                params = [user_id, item_id] + date_params
            else:  # year
                sql = """
                SELECT TO_CHAR(lh.timestamp, 'YYYY') as year, COUNT(lh.id) as play_count
                FROM listening_history lh
                WHERE lh.user_id = %s AND lh.track_id = %s """ + date_filter + """
                GROUP BY year
                ORDER BY year
                """
                params = [user_id, item_id] + date_params
        
        cur.execute(sql, params)
        results = cur.fetchall()
        
        # Create a dictionary to map time periods to play counts
        play_counts = {row[0]: row[1] for row in results}
        
        # Create dataset with data for each time period
        dataset_data = []
        for period in month_years:
            dataset_data.append(play_counts.get(period, 0))
        
        # Create dataset object
        dataset = {
            "label": item_name,
            "data": dataset_data
        }
        
        # Set chart-specific styling
        if chart_type == "total":  # Bar chart
            dataset["backgroundColor"] = color
            dataset["borderColor"] = color
            dataset["borderWidth"] = 1
        else:  # Line chart
            dataset["borderColor"] = color
            dataset["backgroundColor"] = color + "33"  # Add transparency
            dataset["fill"] = True
            dataset["tension"] = 0.2
            dataset["pointBackgroundColor"] = color
        
        datasets.append(dataset)
    
    conn.close()
    
    return jsonify({
        "labels": labels,
        "datasets": datasets
    })

def format_time(ms):
    # Format milliseconds into a human-readable time format
    seconds = ms // 1000
    minutes = seconds // 60
    hours = minutes // 60
    
    if hours > 0:
        return f"{hours}h {minutes % 60}m"
    elif minutes > 0:
        return f"{minutes}m {seconds % 60}s"
    else:
        return f"{seconds}s"