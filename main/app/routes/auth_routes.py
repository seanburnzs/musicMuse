from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Import necessary functions
from ..utils.db import get_db_connection
from ..utils.security import csrf_protect
from ..utils.error_handlers import db_error_handler

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Validate input
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html")
        
        # Check user credentials
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT user_id, username, password_hash FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        
        conn.close()
        
        if user and check_password_hash(user[2], password):
            # Set session variables
            session["user_id"] = user[0]
            session["username"] = user[1]
            flash("Login successful!", "success")
            return redirect(url_for("profile.profile"))
        else:
            flash("Invalid username or password.", "error")
    
    return render_template("login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        # Validate input
        if not username or not email or not password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("signup.html")
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")
        
        # Check if username exists
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            conn.close()
            flash("Username already exists.", "error")
            return render_template("signup.html")
        
        # Create user
        password_hash = generate_password_hash(password)
        
        try:
            cur.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (%s, %s, %s, %s) RETURNING user_id",
                (username, email, password_hash, datetime.now())
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            
            # Insert default settings
            cur.execute(
                """
                INSERT INTO user_settings 
                (user_id, impersonation_privacy, events_privacy, updated_at) 
                VALUES (%s, 'everyone', 'everyone', %s)
                """,
                (user_id, datetime.now())
            )
            conn.commit()
            
            # Set session variables
            session["user_id"] = user_id
            session["username"] = username
            
            flash("Account created successfully!", "success")
            return redirect(url_for("profile.profile"))
        except Exception as e:
            conn.rollback()
            flash(f"Error creating account: {str(e)}", "error")
        finally:
            conn.close()
    
    return render_template("signup.html")

@auth_bp.route("/logout")
def logout():
    # Clear session
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.index"))

@auth_bp.route("/impersonate", methods=["POST"])
@csrf_protect
def impersonate_user():
    print("==== IMPERSONATION DEBUG START ====")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request form data: {dict(request.form)}")
    print(f"Session data: {dict(session)}")
    
    if "user_id" not in session:
        print("Error: No user_id in session")
        flash("You must be logged in to impersonate users.", "error")
        return redirect(url_for("auth.login"))
    
    username = request.form.get("username")
    redirect_to = request.form.get("redirect_to", "/")
    print(f"Target username: {username}")
    print(f"Redirect to: {redirect_to}")
    
    # If stopping impersonation
    if not username and session.get("impersonating"):
        print("Stopping impersonation")
        # Restore original user
        original_user = session.get("original_user", {})
        session.pop("impersonating", None)
        session.pop("original_user", None)
        
        if original_user:
            session["user_id"] = original_user.get("user_id")
            session["username"] = original_user.get("username")
        
        flash("Stopped impersonation.", "success")
        return redirect(redirect_to)
    
    # Check if user exists
    conn = get_db_connection()
    cur = conn.cursor()
    
    print(f"Checking if user exists: {username}")
    cur.execute("SELECT user_id, username FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    
    if not user:
        print(f"User not found: {username}")
        conn.close()
        flash(f"User {username} not found.", "error")
        return redirect(redirect_to)
    
    print(f"User found: {user}")
    
    # Check impersonation privacy settings
    target_user_id = user[0]
    current_user_id = session.get("original_user", {}).get("user_id") or session.get("user_id")
    print(f"Target user_id: {target_user_id}")
    print(f"Current user_id: {current_user_id}")
    
    # Check if the target user allows impersonation
    print("Checking impersonation privacy settings")
    cur.execute(
        "SELECT impersonation_privacy FROM user_settings WHERE user_id = %s",
        (target_user_id,)
    )
    privacy_setting = cur.fetchone()
    print(f"Privacy setting query result: {privacy_setting}")
    
    if not privacy_setting:
        # Default to 'everyone' if no settings found
        impersonation_privacy = "everyone"
        print("No privacy settings found, defaulting to 'everyone'")
    else:
        impersonation_privacy = privacy_setting[0]
        print(f"Impersonation privacy: {impersonation_privacy}")
    
    is_allowed = False
    
    if impersonation_privacy == "everyone":
        is_allowed = True
        print("Access allowed: Privacy set to 'everyone'")
    elif impersonation_privacy == "friends":
        # Check if current user follows the target user
        print("Checking if current user follows target user")
        cur.execute(
            "SELECT 1 FROM user_follows WHERE follower_id = %s AND followed_id = %s",
            (current_user_id, target_user_id)
        )
        follow_result = cur.fetchone()
        print(f"Follow check result: {follow_result}")
        is_allowed = follow_result is not None
        if is_allowed:
            print("Access allowed: User is a follower")
        else:
            print("Access denied: User is not a follower")
    else:
        # Privacy is "private"
        print("Access denied: Privacy set to 'private'")
    
    conn.close()
    
    if not is_allowed:
        print("Impersonation not allowed, returning 403")
        flash(f"You don't have permission to impersonate {username}.", "error")
        return redirect(redirect_to)
    
    # Store original user if not already impersonating
    if not session.get("impersonating"):
        print("Storing original user in session")
        session["original_user"] = {
            "user_id": session.get("user_id"),
            "username": session.get("username")
        }
    
    # Set impersonation
    print("Setting impersonation session data")
    session["impersonating"] = {
        "user_id": user[0],
        "username": user[1]
    }
    session["user_id"] = user[0]
    session["username"] = user[1]
    
    print("Impersonation successful")
    print("==== IMPERSONATION DEBUG END ====")
    
    flash(f"Now viewing as {username}.", "success")
    return redirect(redirect_to)