import secrets
import hashlib
from flask import session, request, abort
from functools import wraps

def generate_csrf_token():
    """Generate a new CSRF token and store it in the session."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

def validate_csrf_token(token):
    """Validate the provided CSRF token against the one stored in the session."""
    if 'csrf_token' not in session:
        return False
    
    return secrets.compare_digest(session['csrf_token'], token)

def csrf_protect(func):
    """Decorator to protect routes from CSRF attacks."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            print("==== CSRF DEBUG START ====")
            print(f"CSRF checking route: {request.path}")
            print(f"Request method: {request.method}")
            print(f"CSRF token in session: {'csrf_token' in session}")
            if 'csrf_token' in session:
                print(f"Session CSRF token: {session['csrf_token']}")
            
            # Check for token in form data
            token = request.form.get('csrf_token')
            print(f"CSRF token in form: {token}")
            
            # If not in form data, check headers for JSON requests
            if not token and request.headers.get('Content-Type') == 'application/json':
                token = request.headers.get('X-CSRFToken')
                print(f"CSRF token in header: {token}")
            
            if not token:
                print("CSRF ERROR: No token found in request")
                print(f"Request URL: {request.url}")
                print(f"Method: {request.method}")
                print(f"Form data: {request.form}")
                print(f"Request headers: {request.headers}")
                abort(403, "CSRF token validation failed")
            elif not validate_csrf_token(token):
                print(f"CSRF ERROR: Token validation failed")
                print(f"Request token: {token}")
                print(f"Session token: {session.get('csrf_token', 'None')}")
                print(f"Request URL: {request.url}")
                print(f"Method: {request.method}")
                print(f"Form data: {request.form}")
                print(f"Request headers: {request.headers}")
                abort(403, "CSRF token validation failed")
            else:
                print("CSRF validation successful")
            
            print("==== CSRF DEBUG END ====")
            
        return func(*args, **kwargs)
    return wrapper

def hash_password(password):
    """Hash a password using a more secure method."""
    # Generate a random salt
    salt = secrets.token_hex(16)
    
    # Hash the password with the salt
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # Number of iterations
    ).hex()
    
    # Return the salt and hash together
    return f"{salt}${password_hash}"

def verify_password(stored_password, provided_password):
    """Verify a password against a stored hash."""
    # Split the stored password into salt and hash
    salt, stored_hash = stored_password.split('$')
    
    # Hash the provided password with the same salt
    computed_hash = hashlib.pbkdf2_hmac(
        'sha256',
        provided_password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # Same number of iterations as when creating the hash
    ).hex()
    
    # Compare the computed hash with the stored hash
    return secrets.compare_digest(stored_hash, computed_hash)