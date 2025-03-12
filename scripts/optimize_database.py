import psycopg2
import os
import logging
from dotenv import load_dotenv
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db_optimization.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("db_optimization")

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

def create_additional_indexes():
    """Create additional strategic indexes to improve query performance."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # List of additional indexes to create
        indexes = [
            # More granular indexes for listening_history
            ("idx_listening_history_platform", "listening_history", "platform"),
            ("idx_listening_history_ms_played", "listening_history", "ms_played"),
            ("idx_listening_history_country", "listening_history", "country"),
            
            # Composite indexes for filtering
            ("idx_listening_history_user_platform", "listening_history", "user_id, platform"),
            ("idx_listening_history_timestamp_range", "listening_history", "timestamp DESC"),
            
            # Track/album/artist name indexes
            ("idx_tracks_name", "tracks", "track_name"),
            ("idx_albums_name", "albums", "album_name"),
            ("idx_artists_name", "artists", "artist_name"),
            
            # User events and hall of fame
            ("idx_user_events_category", "user_events", "category"),
            ("idx_user_hall_of_fame_composite", "user_hall_of_fame", "user_id, item_type, position")
        ]
        
        # Create each index
        for index_name, table, columns in indexes:
            try:
                logger.info(f"Creating index {index_name} on {table}({columns})...")
                
                # Check if index already exists
                cursor.execute(f"""
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = '{index_name}'
                """)
                
                if cursor.fetchone():
                    logger.info(f"Index {index_name} already exists. Skipping.")
                    continue
                
                # Create the index
                start_time = time.time()
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({columns});")
                duration = time.time() - start_time
                
                logger.info(f"Index {index_name} created successfully in {duration:.2f} seconds.")
                
            except Exception as e:
                logger.error(f"Error creating index {index_name}: {str(e)}")
                conn.rollback()
                continue
        
        # Create partial indexes with correct syntax
        partial_indexes = [
            ("idx_listening_history_skipped_true", "listening_history", 
             "user_id, timestamp", "skipped = true"),
            ("idx_listening_history_shuffle_true", "listening_history", 
             "user_id, timestamp", "shuffle = true")
        ]
        
        for index_name, table, columns, condition in partial_indexes:
            try:
                logger.info(f"Creating partial index {index_name} on {table}({columns}) WHERE {condition}...")
                
                # Check if index already exists
                cursor.execute(f"""
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = '{index_name}'
                """)
                
                if cursor.fetchone():
                    logger.info(f"Index {index_name} already exists. Skipping.")
                    continue
                
                # Create the partial index with correct syntax
                start_time = time.time()
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({columns}) WHERE {condition};")
                duration = time.time() - start_time
                
                logger.info(f"Partial index {index_name} created successfully in {duration:.2f} seconds.")
                
            except Exception as e:
                logger.error(f"Error creating partial index {index_name}: {str(e)}")
                conn.rollback()
                continue
        
        # Commit changes
        conn.commit()
        logger.info("All additional indexes created successfully.")
        
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

def add_track_metadata_columns():
    """Add additional columns to tracks table for better metadata."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tracks' 
            AND column_name IN ('duration_ms', 'isrc', 'release_date', 'explicit')
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # Add duration_ms column if it doesn't exist
        if 'duration_ms' not in existing_columns:
            logger.info("Adding duration_ms column to tracks table...")
            cursor.execute("ALTER TABLE tracks ADD COLUMN duration_ms INTEGER;")
            logger.info("Column duration_ms added successfully.")
            
        # Add ISRC column if it doesn't exist
        if 'isrc' not in existing_columns:
            logger.info("Adding isrc column to tracks table...")
            cursor.execute("ALTER TABLE tracks ADD COLUMN isrc VARCHAR(20);")
            logger.info("Column isrc added successfully.")
            
        # Add release_date column if it doesn't exist
        if 'release_date' not in existing_columns:
            logger.info("Adding release_date column to tracks table...")
            cursor.execute("ALTER TABLE tracks ADD COLUMN release_date DATE;")
            logger.info("Column release_date added successfully.")
            
        # Add explicit column if it doesn't exist
        if 'explicit' not in existing_columns:
            logger.info("Adding explicit column to tracks table...")
            cursor.execute("ALTER TABLE tracks ADD COLUMN explicit BOOLEAN DEFAULT false;")
            logger.info("Column explicit added successfully.")
            
        # Commit changes
        conn.commit()
        logger.info("All track metadata columns added successfully.")
        
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

def deduplicate_track_data():
    """Create an infrastructure for track deduplication."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Check if the track_aliases table exists
        cursor.execute("""
            SELECT EXISTS (
               SELECT FROM information_schema.tables 
               WHERE table_name = 'track_aliases'
            );
        """)
        
        if not cursor.fetchone()[0]:
            # Create track_aliases table
            logger.info("Creating track_aliases table...")
            cursor.execute("""
                CREATE TABLE track_aliases (
                    alias_id SERIAL PRIMARY KEY,
                    canonical_track_id INTEGER NOT NULL REFERENCES tracks(track_id),
                    alternate_track_id INTEGER NOT NULL REFERENCES tracks(track_id),
                    similarity_score FLOAT DEFAULT 1.0,
                    manually_verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_alias UNIQUE(canonical_track_id, alternate_track_id)
                );
            """)
            
            # Create indexes for track_aliases
            cursor.execute("CREATE INDEX idx_track_aliases_canonical ON track_aliases(canonical_track_id);")
            cursor.execute("CREATE INDEX idx_track_aliases_alternate ON track_aliases(alternate_track_id);")
            
            logger.info("Track aliases table and indexes created successfully.")
        
        # Check if potential_duplicates view exists
        cursor.execute("""
            SELECT EXISTS (
               SELECT FROM information_schema.views 
               WHERE table_name = 'potential_track_duplicates'
            );
        """)
        
        if not cursor.fetchone()[0]:
            # Create view for potential duplicates
            logger.info("Creating potential_track_duplicates view...")
            cursor.execute("""
                CREATE OR REPLACE VIEW potential_track_duplicates AS
                SELECT 
                    t1.track_id as track_id_1,
                    t2.track_id as track_id_2,
                    t1.track_name as track_name_1,
                    t2.track_name as track_name_2,
                    a1.album_name as album_name_1,
                    a2.album_name as album_name_2,
                    ar1.artist_name as artist_name_1,
                    ar2.artist_name as artist_name_2,
                    SIMILARITY(t1.track_name, t2.track_name) as name_similarity
                FROM 
                    tracks t1
                JOIN 
                    tracks t2 ON t1.track_id < t2.track_id
                JOIN 
                    albums a1 ON t1.album_id = a1.album_id
                JOIN 
                    albums a2 ON t2.album_id = a2.album_id
                JOIN 
                    artists ar1 ON a1.artist_id = ar1.artist_id
                JOIN 
                    artists ar2 ON a2.artist_id = ar2.artist_id
                WHERE 
                    SIMILARITY(t1.track_name, t2.track_name) > 0.8
                    AND ar1.artist_id = ar2.artist_id
                    AND t1.track_id NOT IN (SELECT alternate_track_id FROM track_aliases)
                    AND t2.track_id NOT IN (SELECT alternate_track_id FROM track_aliases);
            """)
            
            logger.info("Potential track duplicates view created successfully.")
        
        # Create function to merge tracks
        logger.info("Creating function to merge duplicate tracks...")
        cursor.execute("""
            CREATE OR REPLACE FUNCTION merge_tracks(canonical_id INTEGER, duplicate_id INTEGER)
            RETURNS BOOLEAN AS $$
            DECLARE
                success BOOLEAN := TRUE;
            BEGIN
                -- Insert into track_aliases
                INSERT INTO track_aliases (canonical_track_id, alternate_track_id, manually_verified)
                VALUES (canonical_id, duplicate_id, TRUE)
                ON CONFLICT (canonical_track_id, alternate_track_id) DO 
                    UPDATE SET manually_verified = TRUE;
                
                -- Update listening_history to point to canonical track
                UPDATE listening_history
                SET track_id = canonical_id
                WHERE track_id = duplicate_id;
                
                -- Update user_hall_of_fame to point to canonical track
                UPDATE user_hall_of_fame
                SET item_id = canonical_id
                WHERE item_type = 'track' AND item_id = duplicate_id;
                
                RETURN success;
            EXCEPTION
                WHEN OTHERS THEN
                    RETURN FALSE;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        # Commit changes
        conn.commit()
        logger.info("Track deduplication infrastructure created successfully.")
        
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

def create_streaming_data_partitions():
    """Create partitions for the listening_history table based on timestamp."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Check if listening_history is already partitioned
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM pg_inherits
                WHERE inhparent = 'listening_history'::regclass
            );
        """)
        
        if cursor.fetchone()[0]:
            logger.info("Listening history table is already partitioned. Skipping partition creation.")
            return
        
        # Create temporary table with the same structure
        logger.info("Creating temporary table for partitioning...")
        cursor.execute("""
            CREATE TABLE listening_history_new (
                id SERIAL,
                timestamp TIMESTAMP NOT NULL,
                platform VARCHAR(50),
                ms_played INTEGER NOT NULL,
                country VARCHAR(5),
                track_id INTEGER REFERENCES tracks(track_id),
                reason_start VARCHAR(50),
                reason_end VARCHAR(50),
                shuffle BOOLEAN,
                skipped BOOLEAN,
                moods VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER REFERENCES users(user_id)
            ) PARTITION BY RANGE (timestamp);
        """)
        
        # Create partitions by year
        years = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
        for i, year in enumerate(years):
            if i < len(years) - 1:
                next_year = years[i+1]
                logger.info(f"Creating partition for year {year}...")
                cursor.execute(f"""
                    CREATE TABLE listening_history_y{year} PARTITION OF listening_history_new
                    FOR VALUES FROM ('{year}-01-01') TO ('{next_year}-01-01');
                """)
            else:
                # Last year, create partition for current year and future
                logger.info(f"Creating partition for year {year} and beyond...")
                cursor.execute(f"""
                    CREATE TABLE listening_history_y{year}_plus PARTITION OF listening_history_new
                    FOR VALUES FROM ('{year}-01-01') TO (MAXVALUE);
                """)
        
        # Copy data from old table to new partitioned table
        logger.info("Copying data to partitioned table (this may take a while)...")
        cursor.execute("""
            INSERT INTO listening_history_new (
                id, timestamp, platform, ms_played, country, 
                track_id, reason_start, reason_end, shuffle, 
                skipped, moods, created_at, user_id
            )
            SELECT 
                id, timestamp, platform, ms_played, country, 
                track_id, reason_start, reason_end, shuffle, 
                skipped, moods, created_at, user_id
            FROM listening_history;
        """)
        
        # Rename tables
        logger.info("Renaming tables...")
        cursor.execute("ALTER TABLE listening_history RENAME TO listening_history_old;")
        cursor.execute("ALTER TABLE listening_history_new RENAME TO listening_history;")
        
        # Create new indexes on partitioned table
        logger.info("Creating indexes on partitioned table...")
        cursor.execute("CREATE INDEX idx_listening_history_user_id ON listening_history(user_id);")
        cursor.execute("CREATE INDEX idx_listening_history_timestamp ON listening_history(timestamp);")
        cursor.execute("CREATE INDEX idx_listening_history_track_id ON listening_history(track_id);")
        cursor.execute("CREATE INDEX idx_listening_history_user_track ON listening_history(user_id, track_id);")
        cursor.execute("CREATE INDEX idx_listening_history_user_timestamp ON listening_history(user_id, timestamp);")
        
        # Commit changes
        conn.commit()
        logger.info("Listening history partitioning completed successfully.")
        
        # Note: Keep the old table for safety - can be dropped later after verification
        logger.info("Old table has been preserved as listening_history_old.")
        
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

def optimize_database():
    """Run all optimization functions."""
    logger.info("Starting database optimization...")
    
    # Step 1: Add additional indexes
    create_additional_indexes()
    
    # Step 2: Add metadata columns to tracks table
    add_track_metadata_columns()
    
    # Step 3: Create deduplication infrastructure
    deduplicate_track_data()
    
    # Step 4: Partition the listening_history table
    # Note: This is commented out because it's a more invasive change
    # and should be run separately after thorough testing
    # create_streaming_data_partitions()
    
    logger.info("Database optimization completed successfully.")

if __name__ == "__main__":
    optimize_database() 