import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db():
    """Get a database connection using the same configuration as the main app"""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "musicmuse_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432)
    ) 