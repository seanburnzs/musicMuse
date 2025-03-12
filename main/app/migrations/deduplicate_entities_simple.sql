-- SQL script to deduplicate entities in the music database that differ only by case
-- This script should be run BEFORE applying the case-insensitive migration
-- Simplified version without RAISE NOTICE statements

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

-- Get counts before processing
SELECT 'Before deduplication: ' || 
       (SELECT COUNT(*) FROM artists) || ' artists, ' || 
       (SELECT COUNT(*) FROM albums) || ' albums, ' || 
       (SELECT COUNT(*) FROM tracks) || ' tracks' AS info;

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
SELECT 'Found ' || COUNT(*) || ' duplicate artists to merge' AS info
FROM entity_deduplication 
WHERE entity_type = 'artist';

-- SPECIAL CASE: First identify and handle albums that would cause conflicts after artist merging
-- Create a table to track album conflicts
CREATE TEMP TABLE album_conflicts (
    canonical_artist_id INTEGER,
    duplicate_artist_id INTEGER,
    canonical_album_id INTEGER,
    duplicate_album_id INTEGER,
    album_name TEXT,
    resolved BOOLEAN DEFAULT FALSE
);

-- Find albums that would conflict when artists are merged
INSERT INTO album_conflicts (canonical_artist_id, duplicate_artist_id, canonical_album_id, duplicate_album_id, album_name)
SELECT 
    ed.canonical_id AS canonical_artist_id,
    ed.duplicate_id AS duplicate_artist_id,
    a1.album_id AS canonical_album_id,
    a2.album_id AS duplicate_album_id,
    LOWER(a1.album_name) AS album_name
FROM 
    entity_deduplication ed
JOIN 
    albums a1 ON a1.artist_id = ed.canonical_id
JOIN 
    albums a2 ON a2.artist_id = ed.duplicate_id AND LOWER(a2.album_name) = LOWER(a1.album_name)
WHERE 
    ed.entity_type = 'artist';

-- Log conflicts found
SELECT 'Found ' || COUNT(*) || ' album name conflicts to resolve before artist merging' AS info
FROM album_conflicts;

-- For each album conflict, merge tracks from the duplicate album to the canonical album
-- First, identify tracks that would conflict when albums are merged
CREATE TEMP TABLE track_conflicts (
    canonical_album_id INTEGER,
    duplicate_album_id INTEGER,
    canonical_track_id INTEGER,
    duplicate_track_id INTEGER,
    track_name TEXT,
    resolved BOOLEAN DEFAULT FALSE
);

-- Find tracks that would conflict when conflicting albums are merged
INSERT INTO track_conflicts (canonical_album_id, duplicate_album_id, canonical_track_id, duplicate_track_id, track_name)
SELECT 
    ac.canonical_album_id,
    ac.duplicate_album_id,
    t1.track_id AS canonical_track_id,
    t2.track_id AS duplicate_track_id,
    LOWER(t1.track_name) AS track_name
FROM 
    album_conflicts ac
JOIN 
    tracks t1 ON t1.album_id = ac.canonical_album_id
JOIN 
    tracks t2 ON t2.album_id = ac.duplicate_album_id AND LOWER(t2.track_name) = LOWER(t1.track_name);

-- Log track conflicts found
SELECT 'Found ' || COUNT(*) || ' track conflicts from album conflicts' AS info
FROM track_conflicts;

-- Update listening_history references for conflicting tracks
UPDATE listening_history lh
SET track_id = tc.canonical_track_id
FROM track_conflicts tc
WHERE lh.track_id = tc.duplicate_track_id;

-- Mark track conflicts as resolved
UPDATE track_conflicts SET resolved = TRUE;

-- Delete the duplicate tracks from conflicting albums
DELETE FROM tracks t
USING track_conflicts tc
WHERE t.track_id = tc.duplicate_track_id AND tc.resolved = TRUE;

-- Now move remaining tracks from duplicate albums to canonical albums
UPDATE tracks t
SET album_id = ac.canonical_album_id
FROM album_conflicts ac
WHERE t.album_id = ac.duplicate_album_id;

-- Mark album conflicts as resolved
UPDATE album_conflicts SET resolved = TRUE;

-- Delete the duplicate albums that were in conflict
DELETE FROM albums a
USING album_conflicts ac
WHERE a.album_id = ac.duplicate_album_id AND ac.resolved = TRUE;

-- Now it's safe to update album references for the artists
UPDATE albums a
SET artist_id = ed.canonical_id
FROM entity_deduplication ed
WHERE 
    ed.entity_type = 'artist' AND
    a.artist_id = ed.duplicate_id;

-- Mark these artist duplicates as processed
UPDATE entity_deduplication
SET processed = TRUE
WHERE entity_type = 'artist';

-- Delete the duplicate artists (those that have been processed)
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
SELECT 'Found ' || COUNT(*) || ' duplicate albums to merge' AS info
FROM entity_deduplication 
WHERE entity_type = 'album' AND processed = FALSE;

-- SPECIAL CASE: Handle tracks that would cause conflicts when albums are merged
-- Clear the previous track conflicts table for reuse
TRUNCATE TABLE track_conflicts;

-- Find tracks that would conflict when albums are merged during album deduplication
INSERT INTO track_conflicts (canonical_album_id, duplicate_album_id, canonical_track_id, duplicate_track_id, track_name)
SELECT 
    ed.canonical_id AS canonical_album_id,
    ed.duplicate_id AS duplicate_album_id,
    t1.track_id AS canonical_track_id,
    t2.track_id AS duplicate_track_id,
    LOWER(t1.track_name) AS track_name
FROM 
    entity_deduplication ed
JOIN 
    tracks t1 ON t1.album_id = ed.canonical_id
JOIN 
    tracks t2 ON t2.album_id = ed.duplicate_id AND LOWER(t2.track_name) = LOWER(t1.track_name)
WHERE 
    ed.entity_type = 'album' AND
    ed.processed = FALSE;

-- Log track conflicts found
SELECT 'Found ' || COUNT(*) || ' track conflicts from album deduplication' AS info
FROM track_conflicts
WHERE resolved = FALSE;

-- Update listening_history references for conflicting tracks
UPDATE listening_history lh
SET track_id = tc.canonical_track_id
FROM track_conflicts tc
WHERE 
    lh.track_id = tc.duplicate_track_id AND
    tc.resolved = FALSE;

-- Delete the duplicate tracks that would conflict
DELETE FROM tracks t
USING track_conflicts tc
WHERE 
    t.track_id = tc.duplicate_track_id AND
    tc.resolved = FALSE;

-- Mark these conflicts as resolved
UPDATE track_conflicts SET resolved = TRUE
WHERE resolved = FALSE;

-- Now it's safe to update the remaining tracks to point to the canonical album
UPDATE tracks t
SET album_id = ed.canonical_id
FROM entity_deduplication ed
WHERE 
    ed.entity_type = 'album' AND
    ed.processed = FALSE AND
    t.album_id = ed.duplicate_id;

-- Mark these album duplicates as processed
UPDATE entity_deduplication
SET processed = TRUE
WHERE entity_type = 'album' AND processed = FALSE;

-- Delete the duplicate albums (those that have been processed)
DELETE FROM albums a
USING entity_deduplication ed
WHERE 
    ed.entity_type = 'album' AND
    ed.processed = TRUE AND
    a.artist_id = (SELECT artist_id FROM albums WHERE album_id = ed.canonical_id) AND
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
SELECT 'Found ' || COUNT(*) || ' duplicate tracks to merge' AS info
FROM entity_deduplication 
WHERE entity_type = 'track' AND processed = FALSE;

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
SELECT 
    'After deduplication: ' || 
    (SELECT COUNT(*) FROM artists) || ' artists (' || 
    (SELECT COUNT(*) FROM entity_deduplication WHERE entity_type = 'artist') || ' duplicates merged), ' ||
    (SELECT COUNT(*) FROM albums) || ' albums (' || 
    (SELECT COUNT(*) FROM entity_deduplication WHERE entity_type = 'album') || ' duplicates merged + ' ||
    (SELECT COUNT(*) FROM album_conflicts) || ' conflict merges), ' ||
    (SELECT COUNT(*) FROM tracks) || ' tracks (' || 
    (SELECT COUNT(*) FROM entity_deduplication WHERE entity_type = 'track') || ' duplicates merged + ' ||
    (SELECT COUNT(*) FROM track_conflicts) || ' conflict merges)' AS info;

-- Clean up
DROP TABLE entity_deduplication;
DROP TABLE album_conflicts;
DROP TABLE track_conflicts;

COMMIT; 