from flask import render_template, jsonify
from functools import wraps
import psycopg2
import logging

logger = logging.getLogger(__name__)

def db_error_handler(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except psycopg2.Error as e:
            logger.error(f"Database error in {f.__name__}: {str(e)}")
            return render_template("error.html", error=f"Database error: {str(e)}"), 500
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return render_template("error.html", error=f"An error occurred: {str(e)}"), 500
    return decorated_function

def api_error_handler(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except psycopg2.Error as e:
            logger.error(f"Database error in {f.__name__}: {str(e)}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    return decorated_function

def register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("error.html", error="Page not found"), 404
        
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("error.html", error="Internal server error"), 500
        
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", error="Forbidden"), 403
        
    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", error="Bad request"), 400 