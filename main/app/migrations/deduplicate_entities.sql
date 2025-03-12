-- SQL script to deduplicate entities in the music database that differ only by case
-- This script should be run BEFORE applying the case-insensitive migration

BEGIN;

-- Create a temporary table to store information about duplicates
CREATE TEMP TABLE entity_deduplication (
    entity_type VARCHAR(50),
    canonical_id INTEGER,
    duplicate_id INTEGER,
    original_name TEXT,
    canonical_name TEXT,
    processed BOOLEAN DEFAULT FALSE
);

-- Log duplicate counts before processing
DO $$
DECLARE
    artist_count INTEGER;
    album_count INTEGER;
    track_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO artist_count FROM artists;
    SELECT COUNT(*) INTO album_count FROM albums;
    SELECT COUNT(*) INTO track_count FROM tracks;
    
    RAISE NOTICE 'Before deduplication: % artists, % albums, % tracks', 
        artist_count, album_count, track_count;
END $$;

----------------------
-- ARTIST DEDUPLICATION
----------------------

-- Find duplicate artists by case-insensitive name
WITH artist_duplicates AS (
    SELECT
        MIN(artist_id) AS canonical_id,
        LOWER(artist_name) AS lower_name,
        array_agg(artist_id) AS duplicate_ids,
        array_agg(artist_name) AS duplicate_names
    FROM
        artists
    GROUP BY
        LOWER(artist_name)
    HAVING
        COUNT(*) > 1
)
INSERT INTO entity_deduplication (entity_type, canonical_id, duplicate_id, canonical_name, original_name)
SELECT
    'artist',
    ad.canonical_id,
    d_id,
    (SELECT artist_name FROM artists WHERE artist_id = ad.canonical_id),
    d_name
FROM
    artist_duplicates ad,
    LATERAL UNNEST(ad.duplicate_ids, ad.duplicate_names) WITH ORDINALITY AS a(d_id, d_name, ord)
WHERE
    d_id <> ad.canonical_id;

-- Log the number of artist duplicates found
DO $$
DECLARE
    duplicate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO duplicate_count FROM entity_deduplication WHERE entity_type = 'artist';
    RAISE NOTICE 'Found % duplicate artists to merge', duplicate_count;
END $$;

-- For each artist duplicate:
-- 1. Update album references to point to the canonical artist
UPDATE albums a
SET artist_id = ed.canonical_id
FROM entity_deduplication ed
WHERE 
    ed.entity_type = 'artist' AND
    a.artist_id = ed.duplicate_id;

-- 2. Mark these artist duplicates as processed
UPDATE entity_deduplication
SET processed = TRUE
WHERE entity_type = 'artist';

-- 3. Delete the duplicate artists (those that have been processed)
DELETE FROM artists a
USING entity_deduplication ed
WHERE 
    ed.entity_type = 'artist' AND
    ed.processed = TRUE AND
    a.artist_id = ed.duplicate_id;

----------------------
-- ALBUM DEDUPLICATION
----------------------

-- Find duplicate albums by case-insensitive name within the same artist
WITH album_duplicates AS (
    SELECT
        MIN(album_id) AS canonical_id,
        artist_id,
        LOWER(album_name) AS lower_name,
        array_agg(album_id) AS duplicate_ids,
        array_agg(album_name) AS duplicate_names
    FROM
        albums
    GROUP BY
        artist_id, LOWER(album_name)
    HAVING
        COUNT(*) > 1
)
INSERT INTO entity_deduplication (entity_type, canonical_id, duplicate_id, canonical_name, original_name)
SELECT
    'album',
    ad.canonical_id,
    d_id,
    (SELECT album_name FROM albums WHERE album_id = ad.canonical_id),
    d_name
FROM
    album_duplicates ad,
    LATERAL UNNEST(ad.duplicate_ids, ad.duplicate_names) WITH ORDINALITY AS a(d_id, d_name, ord)
WHERE
    d_id <> ad.canonical_id;

-- Log the number of album duplicates found
DO $$
DECLARE
    duplicate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO duplicate_count FROM entity_deduplication WHERE entity_type = 'album' AND processed = FALSE;
    RAISE NOTICE 'Found % duplicate albums to merge', duplicate_count;
END $$;

-- For each album duplicate:
-- 1. Update track references to point to the canonical album
UPDATE tracks t
SET album_id = ed.canonical_id
FROM entity_deduplication ed
WHERE 
    ed.entity_type = 'album' AND
    t.album_id = ed.duplicate_id;

-- 2. Mark these album duplicates as processed
UPDATE entity_deduplication
SET processed = TRUE
WHERE entity_type = 'album';

-- 3. Delete the duplicate albums (those that have been processed)
DELETE FROM albums a
USING entity_deduplication ed
WHERE 
    ed.entity_type = 'album' AND
    ed.processed = TRUE AND
    a.album_id = ed.duplicate_id;

----------------------
-- TRACK DEDUPLICATION
----------------------

-- Find duplicate tracks by case-insensitive name within the same album
WITH track_duplicates AS (
    SELECT
        MIN(track_id) AS canonical_id,
        album_id,
        LOWER(track_name) AS lower_name,
        array_agg(track_id) AS duplicate_ids,
        array_agg(track_name) AS duplicate_names
    FROM
        tracks
    GROUP BY
        album_id, LOWER(track_name)
    HAVING
        COUNT(*) > 1
)
INSERT INTO entity_deduplication (entity_type, canonical_id, duplicate_id, canonical_name, original_name)
SELECT
    'track',
    td.canonical_id,
    d_id,
    (SELECT track_name FROM tracks WHERE track_id = td.canonical_id),
    d_name
FROM
    track_duplicates td,
    LATERAL UNNEST(td.duplicate_ids, td.duplicate_names) WITH ORDINALITY AS t(d_id, d_name, ord)
WHERE
    d_id <> td.canonical_id;

-- Log the number of track duplicates found
DO $$
DECLARE
    duplicate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO duplicate_count FROM entity_deduplication WHERE entity_type = 'track' AND processed = FALSE;
    RAISE NOTICE 'Found % duplicate tracks to merge', duplicate_count;
END $$;

-- For each track duplicate:
-- 1. Update listening_history references to point to the canonical track
UPDATE listening_history lh
SET track_id = ed.canonical_id
FROM entity_deduplication ed
WHERE 
    ed.entity_type = 'track' AND
    lh.track_id = ed.duplicate_id;

-- 2. Mark these track duplicates as processed
UPDATE entity_deduplication
SET processed = TRUE
WHERE entity_type = 'track';

-- 3. Delete the duplicate tracks (those that have been processed)
DELETE FROM tracks t
USING entity_deduplication ed
WHERE 
    ed.entity_type = 'track' AND
    ed.processed = TRUE AND
    t.track_id = ed.duplicate_id;

-- Log entity counts after deduplication
DO $$
DECLARE
    artist_count INTEGER;
    album_count INTEGER;
    track_count INTEGER;
    artist_dups INTEGER;
    album_dups INTEGER;
    track_dups INTEGER;
BEGIN
    SELECT COUNT(*) INTO artist_count FROM artists;
    SELECT COUNT(*) INTO album_count FROM albums;
    SELECT COUNT(*) INTO track_count FROM tracks;
    
    SELECT COUNT(*) INTO artist_dups FROM entity_deduplication WHERE entity_type = 'artist';
    SELECT COUNT(*) INTO album_dups FROM entity_deduplication WHERE entity_type = 'album';
    SELECT COUNT(*) INTO track_dups FROM entity_deduplication WHERE entity_type = 'track';
    
    RAISE NOTICE 'After deduplication: % artists (% duplicates merged), % albums (% duplicates merged), % tracks (% duplicates merged)', 
        artist_count, artist_dups, album_count, album_dups, track_count, track_dups;
END $$;

-- Clean up
DROP TABLE entity_deduplication;

COMMIT; 