import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect to the database
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME", "musicmuse_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASS"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", 5432)
)

try:
    # Create a cursor
    cur = conn.cursor()
    
    # Add image_url column to tracks table if it doesn't exist
    cur.execute("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS image_url VARCHAR(255)")
    
    # Commit the transaction
    conn.commit()
    
    print("Image URL column added to tracks table successfully.")
except Exception as e:
    conn.rollback()
    print(f"Error: {str(e)}")
finally:
    # Close the connection
    if conn:
        conn.close() 