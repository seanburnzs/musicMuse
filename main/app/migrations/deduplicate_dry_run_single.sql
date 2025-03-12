-- Begin transaction
BEGIN;

-- Combined query to count duplicates for all entity types in a single result set
SELECT 
    'artists' as entity_type,
    COUNT(*) as duplicate_sets,
    SUM(num_duplicates) as total_duplicates
FROM (
    SELECT 
        COUNT(*) - 1 as num_duplicates
    FROM 
        artists
    GROUP BY 
        LOWER(artist_name)
    HAVING 
        COUNT(*) > 1
) as artist_stats

UNION ALL

SELECT 
    'albums' as entity_type,
    COUNT(*) as duplicate_sets,
    SUM(num_duplicates) as total_duplicates
FROM (
    SELECT 
        COUNT(*) - 1 as num_duplicates
    FROM 
        albums
    GROUP BY 
        artist_id, LOWER(album_name)
    HAVING 
        COUNT(*) > 1
) as album_stats

UNION ALL

SELECT 
    'tracks' as entity_type,
    COUNT(*) as duplicate_sets,
    SUM(num_duplicates) as total_duplicates
FROM (
    SELECT 
        COUNT(*) - 1 as num_duplicates
    FROM 
        tracks
    GROUP BY 
        album_id, LOWER(track_name)
    HAVING 
        COUNT(*) > 1
) as track_stats;

-- Artist duplicate details (top 20)
SELECT 
    'ARTIST' as entity_type,
    LOWER(artist_name) as normalized_name,
    string_agg(artist_name, ', ') as duplicate_names,
    COUNT(*) as count
FROM 
    artists
GROUP BY 
    LOWER(artist_name)
HAVING 
    COUNT(*) > 1
ORDER BY count DESC, normalized_name
LIMIT 20;

-- Album duplicate details (top 20)
SELECT 
    'ALBUM' as entity_type,
    LOWER(album_name) as normalized_name,
    string_agg(album_name, ', ') as duplicate_names,
    COUNT(*) as count
FROM 
    albums
GROUP BY 
    artist_id, LOWER(album_name)
HAVING 
    COUNT(*) > 1
ORDER BY count DESC, normalized_name
LIMIT 20;

-- Track duplicate details (top 20)
SELECT 
    'TRACK' as entity_type,
    LOWER(track_name) as normalized_name,
    string_agg(track_name, ', ') as duplicate_names,
    COUNT(*) as count
FROM 
    tracks
GROUP BY 
    album_id, LOWER(track_name)
HAVING 
    COUNT(*) > 1
ORDER BY count DESC, normalized_name
LIMIT 20;

-- Rollback to make no changes
ROLLBACK; 