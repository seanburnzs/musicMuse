from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import psycopg2
from datetime import datetime

# Create blueprint
event_bp = Blueprint('event', __name__)

# Import necessary functions
from ..utils.db import get_db_connection
from ..utils.security import csrf_protect
from ..utils.error_handlers import db_error_handler

@event_bp.route("/events", methods=["GET"])
def view_events():
    if "user_id" not in session:
        flash("You must be logged in to view events.", "error")
        return redirect(url_for("auth.login"))
    
    events = get_user_events_for_current_user()
    
    return render_template(
        "events.html",
        events=events
    )

@event_bp.route("/events/new", methods=["GET", "POST"])
def new_event():
    if "user_id" not in session:
        flash("You must be logged in to create events.", "error")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        # Get form data
        name = request.form.get("name")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")
        category = request.form.get("category")
        color = request.form.get("color")
        
        # Validate input
        if not name or not start_date:
            flash("Event name and start date are required.", "error")
            return render_template("event_form.html", editing=False)
        
        # Convert dates
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                if end_date < start_date:
                    flash("End date cannot be before start date.", "error")
                    return render_template("event_form.html", editing=False)
            else:
                end_date = None
        except ValueError:
            flash("Invalid date format.", "error")
            return render_template("event_form.html", editing=False)
        
        # Insert event
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute(
                """
                INSERT INTO user_events 
                (user_id, name, start_date, end_date, description, category, color, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session.get("user_id"),
                    name,
                    start_date,
                    end_date,
                    description,
                    category,
                    color,
                    datetime.now()
                )
            )
            conn.commit()
            flash("Event created successfully!", "success")
            return redirect(url_for("event.view_events"))
        except Exception as e:
            conn.rollback()
            flash(f"Error creating event: {str(e)}", "error")
        finally:
            conn.close()
    
    return render_template("event_form.html", editing=False)

@event_bp.route("/events/edit/<int:event_id>", methods=["GET", "POST"])
def edit_event(event_id):
    if "user_id" not in session:
        flash("You must be logged in to edit events.", "error")
        return redirect(url_for("auth.login"))
    
    # Get the event
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT * FROM user_events WHERE event_id = %s AND user_id = %s",
        (event_id, session.get("user_id"))
    )
    event = cur.fetchone()
    
    if not event:
        conn.close()
        flash("Event not found or you don't have permission to edit it.", "error")
        return redirect(url_for("event.view_events"))
    
    if request.method == "POST":
        # Get form data
        name = request.form.get("name")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        description = request.form.get("description")
        category = request.form.get("category")
        color = request.form.get("color")
        
        # Validate input
        if not name or not start_date:
            flash("Event name and start date are required.", "error")
            return render_template("event_form.html", event=event, editing=True)
        
        # Convert dates
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                if end_date < start_date:
                    flash("End date cannot be before start date.", "error")
                    return render_template("event_form.html", event=event, editing=True)
            else:
                end_date = None
        except ValueError:
            flash("Invalid date format.", "error")
            return render_template("event_form.html", event=event, editing=True)
        
        # Update event
        try:
            cur.execute(
                """
                UPDATE user_events 
                SET name = %s, start_date = %s, end_date = %s, description = %s, category = %s, color = %s
                WHERE event_id = %s AND user_id = %s
                """,
                (
                    name,
                    start_date,
                    end_date,
                    description,
                    category,
                    color,
                    event_id,
                    session.get("user_id")
                )
            )
            conn.commit()
            flash("Event updated successfully!", "success")
            return redirect(url_for("event.view_events"))
        except Exception as e:
            conn.rollback()
            flash(f"Error updating event: {str(e)}", "error")
        finally:
            conn.close()
    
    # Format dates for the form
    event_dict = {
        "event_id": event[0],
        "user_id": event[1],
        "name": event[2],
        "start_date": event[3].strftime("%Y-%m-%d"),
        "end_date": event[4].strftime("%Y-%m-%d") if event[4] else "",
        "description": event[5] or "",
        "category": event[6] or "",
        "color": event[7] or "#3788d8"
    }
    
    conn.close()
    return render_template("event_form.html", event=event_dict, editing=True)

@event_bp.route("/events/delete/<int:event_id>", methods=["POST"])
def delete_event(event_id):
    if "user_id" not in session:
        flash("You must be logged in to delete events.", "error")
        return redirect(url_for("auth.login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "DELETE FROM user_events WHERE event_id = %s AND user_id = %s",
            (event_id, session.get("user_id"))
        )
        
        if cur.rowcount == 0:
            flash("Event not found or you don't have permission to delete it.", "error")
        else:
            conn.commit()
            flash("Event deleted successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting event: {str(e)}", "error")
    finally:
        conn.close()
    
    return redirect(url_for("event.view_events"))

def get_user_events_for_current_user():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        """
        SELECT event_id, name, start_date, end_date, description, category, color
        FROM user_events
        WHERE user_id = %s
        ORDER BY start_date DESC
        """,
        (session.get("user_id"),)
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
    
    conn.close()
    return formatted_events