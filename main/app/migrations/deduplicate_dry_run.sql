-- Begin transaction
BEGIN;

-- Identify and count duplicate artists
WITH artist_duplicates AS (
    SELECT 
        LOWER(artist_name) as lower_name,
        string_agg(artist_name, ', ') as duplicate_names,
        array_agg(artist_id) as duplicate_ids,
        COUNT(*) as count
    FROM 
        artists
    GROUP BY 
        LOWER(artist_name)
    HAVING 
        COUNT(*) > 1
)
SELECT lower_name as normalized_name, duplicate_names, count
FROM artist_duplicates
ORDER BY count DESC;

-- Identify and count duplicate albums
WITH album_duplicates AS (
    SELECT 
        LOWER(album_name) as lower_name,
        string_agg(album_name, ', ') as duplicate_names,
        array_agg(album_id) as duplicate_ids,
        COUNT(*) as count
    FROM 
        albums
    GROUP BY 
        LOWER(album_name), artist_id
    HAVING 
        COUNT(*) > 1
)
SELECT lower_name as normalized_name, duplicate_names, count
FROM album_duplicates
ORDER BY count DESC;

-- Identify and count duplicate tracks
WITH track_duplicates AS (
    SELECT 
        LOWER(track_name) as lower_name,
        string_agg(track_name, ', ') as duplicate_names,
        array_agg(track_id) as duplicate_ids,
        COUNT(*) as count
    FROM 
        tracks
    GROUP BY 
        LOWER(track_name), album_id
    HAVING 
        COUNT(*) > 1
)
SELECT lower_name as normalized_name, duplicate_names, count
FROM track_duplicates
ORDER BY count DESC;

-- Rollback to make no changes
ROLLBACK; 