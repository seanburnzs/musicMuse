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
    
    # Add image_search_attempted column to artists table
    cur.execute("""
        ALTER TABLE artists 
        ADD COLUMN IF NOT EXISTS image_search_attempted BOOLEAN DEFAULT FALSE
    """)
    
    # Add image_search_attempted column to albums table
    cur.execute("""
        ALTER TABLE albums 
        ADD COLUMN IF NOT EXISTS image_search_attempted BOOLEAN DEFAULT FALSE
    """)
    
    # Add image_search_attempted column to tracks table
    cur.execute("""
        ALTER TABLE tracks 
        ADD COLUMN IF NOT EXISTS image_search_attempted BOOLEAN DEFAULT FALSE
    """)
    
    # Update existing records with images to mark them as attempted
    cur.execute("""
        UPDATE artists 
        SET image_search_attempted = TRUE 
        WHERE image_url IS NOT NULL AND image_url != ''
    """)
    
    cur.execute("""
        UPDATE albums 
        SET image_search_attempted = TRUE 
        WHERE image_url IS NOT NULL AND image_url != ''
    """)
    
    cur.execute("""
        UPDATE tracks 
        SET image_search_attempted = TRUE 
        WHERE image_url IS NOT NULL AND image_url != ''
    """)
    
    # Commit the transaction
    conn.commit()
    
    print("Added image_search_attempted columns and updated existing records successfully.")
except Exception as e:
    conn.rollback()
    print(f"Error: {str(e)}")
finally:
    # Close the connection
    if conn:
        conn.close() 