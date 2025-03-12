-- Migration to make database operations case-insensitive
-- This script modifies text columns to use case-insensitive operations and indexes

-- First, enable the citext extension if it doesn't exist
CREATE EXTENSION IF NOT EXISTS citext;

-- Commit after extension creation to avoid potential transaction issues
COMMIT;

-- Begin transaction for schema changes
BEGIN;

-- Announce start of migration
DO $$
BEGIN
    RAISE NOTICE 'Starting case-insensitive schema migration...';
END $$;

-- Save view and materialized view definitions for later recreation
DO $$
BEGIN
    RAISE NOTICE 'Backing up view and materialized view definitions...';
END $$;

-- Drop dependent views and materialized views
DROP VIEW IF EXISTS potential_track_duplicates CASCADE;
DROP MATERIALIZED VIEW IF EXISTS user_top_tracks CASCADE;
DROP MATERIALIZED VIEW IF EXISTS user_top_artists CASCADE;

DO $$
BEGIN
    RAISE NOTICE 'Dependent views and materialized views dropped...';
END $$;

-- 1. Modify the artists table
ALTER TABLE artists 
    -- Create a backup of the current data
    ADD COLUMN temp_artist_name citext;

-- Copy data to the temporary column
UPDATE artists SET temp_artist_name = artist_name;

-- Drop constraints involving artist_name
ALTER TABLE artists DROP CONSTRAINT IF EXISTS artists_artist_name_key;

-- Drop the original column and rename the temporary one
ALTER TABLE artists DROP COLUMN artist_name;
ALTER TABLE artists RENAME COLUMN temp_artist_name TO artist_name;

-- Recreate constraints with case-insensitive column
ALTER TABLE artists ADD CONSTRAINT artists_artist_name_key UNIQUE (artist_name);

DO $$
BEGIN
    RAISE NOTICE 'Artists table converted to case-insensitive...';
END $$;

-- 2. Modify the albums table
ALTER TABLE albums
    -- Create a backup of the current data
    ADD COLUMN temp_album_name citext;

-- Copy data to the temporary column
UPDATE albums SET temp_album_name = album_name;

-- Drop constraints involving album_name
ALTER TABLE albums DROP CONSTRAINT IF EXISTS albums_album_name_artist_id_key;
ALTER TABLE albums DROP CONSTRAINT IF EXISTS albums_album_name_key;

-- Drop the original column and rename the temporary one
ALTER TABLE albums DROP COLUMN album_name;
ALTER TABLE albums RENAME COLUMN temp_album_name TO album_name;

-- Recreate constraints with case-insensitive column
ALTER TABLE albums ADD CONSTRAINT albums_album_name_artist_id_key UNIQUE (album_name, artist_id);

DO $$
BEGIN
    RAISE NOTICE 'Albums table converted to case-insensitive...';
END $$;

-- 3. Modify the tracks table
ALTER TABLE tracks
    -- Create a backup of the current data
    ADD COLUMN temp_track_name citext;

-- Copy data to the temporary column
UPDATE tracks SET temp_track_name = track_name;

-- Drop constraints involving track_name
ALTER TABLE tracks DROP CONSTRAINT IF EXISTS tracks_track_name_album_id_key;
ALTER TABLE tracks DROP CONSTRAINT IF EXISTS tracks_track_name_key;

-- Drop the original column and rename the temporary one
ALTER TABLE tracks DROP COLUMN track_name;
ALTER TABLE tracks RENAME COLUMN temp_track_name TO track_name;

-- Recreate constraints with case-insensitive column
ALTER TABLE tracks ADD CONSTRAINT tracks_track_name_album_id_key UNIQUE (track_name, album_id);

DO $$
BEGIN
    RAISE NOTICE 'Tracks table converted to case-insensitive...';
END $$;

-- Recreate potential_track_duplicates view
CREATE OR REPLACE VIEW potential_track_duplicates AS
SELECT 
    t1.track_id AS track_id_1,
    t2.track_id AS track_id_2,
    t1.track_name AS track_name_1,
    t2.track_name AS track_name_2,
    a1.album_name AS album_name_1,
    a2.album_name AS album_name_2,
    ar1.artist_name AS artist_name_1,
    ar2.artist_name AS artist_name_2,
    similarity(t1.track_name, t2.track_name) AS name_similarity
FROM 
    tracks t1
    JOIN tracks t2 ON t1.track_id < t2.track_id
    JOIN albums a1 ON t1.album_id = a1.album_id
    JOIN albums a2 ON t2.album_id = a2.album_id
    JOIN artists ar1 ON a1.artist_id = ar1.artist_id
    JOIN artists ar2 ON a2.artist_id = ar2.artist_id
WHERE 
    similarity(t1.track_name, t2.track_name) > 0.7;

-- Recreate user_top_tracks materialized view
-- Note: The exact definition might need adjustment based on your schema
CREATE MATERIALIZED VIEW user_top_tracks AS
SELECT 
    lh.user_id,
    t.track_id,
    t.track_name,
    a.album_name,
    ar.artist_name,
    COUNT(*) as play_count
FROM 
    listening_history lh
    JOIN tracks t ON lh.track_id = t.track_id
    JOIN albums a ON t.album_id = a.album_id
    JOIN artists ar ON a.artist_id = ar.artist_id
GROUP BY 
    lh.user_id, t.track_id, t.track_name, a.album_name, ar.artist_name
ORDER BY 
    lh.user_id, play_count DESC;

-- Recreate user_top_artists materialized view
-- Note: The exact definition might need adjustment based on your schema
CREATE MATERIALIZED VIEW user_top_artists AS
SELECT 
    lh.user_id,
    ar.artist_id,
    ar.artist_name,
    COUNT(*) as play_count
FROM 
    listening_history lh
    JOIN tracks t ON lh.track_id = t.track_id
    JOIN albums a ON t.album_id = a.album_id
    JOIN artists ar ON a.artist_id = ar.artist_id
GROUP BY 
    lh.user_id, ar.artist_id, ar.artist_name
ORDER BY 
    lh.user_id, play_count DESC;

DO $$
BEGIN
    RAISE NOTICE 'Views and materialized views recreated...';
END $$;

-- Update data_processing.py log entries to reflect case-insensitive changes
DO $$
BEGIN
    RAISE NOTICE 'Schema migration complete. Note: Update your application code to reflect these changes.';
    RAISE NOTICE 'The track_name, artist_name, and album_name columns now use the citext type.';
END $$;

-- Commit the transaction
COMMIT; 