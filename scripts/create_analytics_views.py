import psycopg2
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db_migration")

# Load environment variables
load_dotenv()

# Database connection parameters
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME", "musicmuse_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432)
}

def create_materialized_views():
    """Create materialized views for frequently accessed analytics."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Define the materialized views
        views = [
            # User listening summary
            (
                "user_listening_summary",
                """
                CREATE MATERIALIZED VIEW user_listening_summary AS
                SELECT 
                    user_id,
                    COUNT(*) as total_streams,
                    COUNT(DISTINCT track_id) as unique_tracks,
                    SUM(ms_played)/3600000.0 as total_hours
                FROM listening_history
                GROUP BY user_id;
                """
            ),
            
            # Top tracks by user
            (
                "user_top_tracks",
                """
                CREATE MATERIALIZED VIEW user_top_tracks AS
                SELECT 
                    lh.user_id,
                    t.track_name,
                    a.artist_name,
                    COUNT(*) as play_count,
                    SUM(lh.ms_played)/60000.0 as total_minutes
                FROM listening_history lh
                JOIN tracks t ON lh.track_id = t.track_id
                JOIN albums al ON t.album_id = al.album_id
                JOIN artists a ON al.artist_id = a.artist_id
                GROUP BY lh.user_id, t.track_name, a.artist_name;
                """
            ),
            
            # Top artists by user
            (
                "user_top_artists",
                """
                CREATE MATERIALIZED VIEW user_top_artists AS
                SELECT 
                    lh.user_id,
                    a.artist_name,
                    COUNT(*) as play_count,
                    SUM(lh.ms_played)/60000.0 as total_minutes
                FROM listening_history lh
                JOIN tracks t ON lh.track_id = t.track_id
                JOIN albums al ON t.album_id = al.album_id
                JOIN artists a ON al.artist_id = a.artist_id
                GROUP BY lh.user_id, a.artist_name;
                """
            ),
            
            # Listening by hour of day
            (
                "user_listening_by_hour",
                """
                CREATE MATERIALIZED VIEW user_listening_by_hour AS
                SELECT 
                    user_id,
                    EXTRACT(HOUR FROM timestamp) as hour,
                    COUNT(*) as play_count
                FROM listening_history
                GROUP BY user_id, hour;
                """
            ),
            
            # Listening by day of week
            (
                "user_listening_by_day",
                """
                CREATE MATERIALIZED VIEW user_listening_by_day AS
                SELECT 
                    user_id,
                    EXTRACT(DOW FROM timestamp) as day,
                    COUNT(*) as play_count
                FROM listening_history
                GROUP BY user_id, day;
                """
            )
        ]
        
        # Create each view
        for view_name, view_definition in views:
            try:
                # Drop view if it exists
                cursor.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name};")
                
                # Create the view
                logger.info(f"Creating materialized view {view_name}...")
                cursor.execute(view_definition)
                
                # Create an index on user_id for the view
                cursor.execute(f"CREATE INDEX idx_{view_name}_user_id ON {view_name}(user_id);")
                
                logger.info(f"Materialized view {view_name} created successfully.")
                
            except Exception as e:
                logger.error(f"Error creating view {view_name}: {str(e)}")
                conn.rollback()
                continue
        
        # Create a function to refresh the views
        refresh_function = """
        CREATE OR REPLACE FUNCTION refresh_analytics_views() RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY user_listening_summary;
            REFRESH MATERIALIZED VIEW CONCURRENTLY user_top_tracks;
            REFRESH MATERIALIZED VIEW CONCURRENTLY user_top_artists;
            REFRESH MATERIALIZED VIEW CONCURRENTLY user_listening_by_hour;
            REFRESH MATERIALIZED VIEW CONCURRENTLY user_listening_by_day;
        END;
        $$ LANGUAGE plpgsql;
        """
        
        try:
            cursor.execute(refresh_function)
            logger.info("Created refresh_analytics_views function.")
        except Exception as e:
            logger.error(f"Error creating refresh function: {str(e)}")
            conn.rollback()
        
        # Commit changes
        conn.commit()
        logger.info("All materialized views created successfully.")
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    create_materialized_views()