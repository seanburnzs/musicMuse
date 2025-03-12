from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
import psycopg2
from datetime import datetime

# Create blueprint
main_bp = Blueprint('main', __name__)

# Import necessary functions
from ..utils.db import get_db_connection
from ..utils.error_handlers import db_error_handler

@main_bp.route("/")
def index():
    # Always render the index page regardless of login status
    return render_template("index.html")

@main_bp.route("/search_profiles")
def search_profiles():
    query = request.args.get("q", "").strip()
    
    if not query or len(query) < 2:
        return redirect(url_for("main.index"))
    
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
    users = cur.fetchall()
    
    conn.close()
    
    return render_template(
        "search_results.html",
        query=query,
        users=users
    )

# Additional utility functions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS