from flask import Flask
import os
from dotenv import load_dotenv
import logging
import sys

# Set up logging
def configure_logging():
    """Configure logging for the application"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers to avoid duplicate logs
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    # Create console handler with a detailed formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Suppress some of the more verbose loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    # Create a specific logger for our app
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.DEBUG)
    
    return app_logger

# Create the app logger
app_logger = configure_logging()

# Load environment variables
load_dotenv()

def create_app(test_config=None):
    """Create and configure the Flask application"""
    # Specify the correct static folder location - use absolute path to the static folder
    static_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
    
    app = Flask(__name__, 
                instance_relative_config=True,
                static_folder=static_folder,  # Set the static folder to the correct location
                static_url_path='/static')    # Explicitly set the static URL path
    
    # Configure the app
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key')
    
    # Set the MAX_CONTENT_LENGTH early in the configuration process
    # Ensure this is large enough for streaming data files (30MB)
    MAX_UPLOAD_SIZE = 60 * 1024 * 1024  # 60MB max upload size for safety
    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE
    app_logger.info(f"Setting maximum content length to {MAX_UPLOAD_SIZE/(1024*1024):.1f}MB")
    
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
    app.config['SPOTIFY_CLIENT_ID'] = os.getenv("SPOTIFY_CLIENT_ID")
    app.config['SPOTIFY_CLIENT_SECRET'] = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    # Log app configuration
    app_logger.info(f"App configuration loaded. Max content length: {app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024):.1f}MB")
    app_logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    
    # Ensure the uploads directory exists
    if app.static_folder and not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        app_logger.info(f"Created upload directory: {app.config['UPLOAD_FOLDER']}")
    
    # Override config with test config if provided
    if test_config:
        app.config.update(test_config)
    
    # Register routes and blueprints
    register_blueprints(app)
    
    # Register error handlers
    from .utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_commands(app)
    
    app_logger.info("Flask application initialized successfully")
    return app

def register_blueprints(app):
    """Register all blueprints with the application"""
    # Import blueprints
    from .routes.main_routes import main_bp
    from .routes.auth_routes import auth_bp
    from .routes.profile_routes import profile_bp
    from .routes.social_routes import social_bp
    from .routes.analytics_routes import analytics_bp
    from .routes.event_routes import event_bp
    from .routes.api_routes import api_bp
    
    # Import the item_pages blueprint from the main directory
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from item_pages import item_pages
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(event_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(item_pages)
    
    # Register context processor for CSRF token
    from .utils.security import generate_csrf_token
    @app.context_processor
    def inject_csrf_token():
        return {'csrf_token': generate_csrf_token()}

def register_commands(app):
    """Register CLI commands with the Flask application"""
    from .commands.image_commands import images
    app.cli.add_command(images) 