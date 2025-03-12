"""
Development script to run the live scrobbler service locally.
"""
import os
import sys
import subprocess
import time
import signal
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define processes
processes = []

def signal_handler(sig, frame):
    """Handle termination signals."""
    logger.info("Shutting down...")
    for process in processes:
        if process.poll() is None:  # If process is still running
            process.terminate()
    sys.exit(0)

def run_api():
    """Run the API server."""
    logger.info("Starting API server...")
    api_process = subprocess.Popen(
        ["python", "-m", "flask", "--app", "src.api", "run", "--debug"],
        env=os.environ.copy()
    )
    processes.append(api_process)
    return api_process

def run_celery_worker():
    """Run the Celery worker."""
    logger.info("Starting Celery worker...")
    worker_process = subprocess.Popen(
        ["celery", "-A", "src.tasks", "worker", "--loglevel=info"],
        env=os.environ.copy()
    )
    processes.append(worker_process)
    return worker_process

def run_celery_beat():
    """Run the Celery beat scheduler."""
    logger.info("Starting Celery beat scheduler...")
    beat_process = subprocess.Popen(
        ["celery", "-A", "src.tasks", "beat", "--loglevel=info"],
        env=os.environ.copy()
    )
    processes.append(beat_process)
    return beat_process

def main():
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize database if needed
    try:
        from src.db_init import main as init_db
        init_db()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return
    
    # Start processes
    api_process = run_api()
    worker_process = run_celery_worker()
    beat_process = run_celery_beat()
    
    # Monitor processes
    try:
        while True:
            if api_process.poll() is not None:
                logger.error("API server crashed. Restarting...")
                api_process = run_api()
            
            if worker_process.poll() is not None:
                logger.error("Celery worker crashed. Restarting...")
                worker_process = run_celery_worker()
            
            if beat_process.poll() is not None:
                logger.error("Celery beat scheduler crashed. Restarting...")
                beat_process = run_celery_beat()
            
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main() 