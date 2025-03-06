-- db_schema.sql
-- CREATE EXTENSION IF NOT EXISTS citext;

-- Artists table
CREATE TABLE IF NOT EXISTS artists (
    artist_id SERIAL PRIMARY KEY,
    artist_name VARCHAR(255) NOT NULL,
    CONSTRAINT unique_artist_name UNIQUE (artist_name)
);

-- Albums table
CREATE TABLE IF NOT EXISTS albums (
    album_id SERIAL PRIMARY KEY,
    album_name VARCHAR(255) NOT NULL,
    artist_id INT REFERENCES artists (artist_id) ON DELETE CASCADE,
    CONSTRAINT unique_album_artist UNIQUE (album_name, artist_id)
);

-- Tracks table
CREATE TABLE IF NOT EXISTS tracks (
    track_id SERIAL PRIMARY KEY,
    track_name VARCHAR(255) NOT NULL,
    album_id INT REFERENCES albums (album_id) ON DELETE CASCADE,
    CONSTRAINT unique_track_album UNIQUE (track_name, album_id)
);

-- Main listening history table
CREATE TABLE IF NOT EXISTS listening_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    platform VARCHAR(50),
    ms_played INT NOT NULL DEFAULT 0,
    country VARCHAR(5),
    track_id INT REFERENCES tracks (track_id) ON DELETE CASCADE,
    reason_start VARCHAR(50),
    reason_end VARCHAR(50),
    shuffle BOOLEAN DEFAULT FALSE,
    skipped BOOLEAN DEFAULT FALSE,
    moods VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_listening_timestamp ON listening_history (timestamp);
CREATE INDEX IF NOT EXISTS idx_listening_track_id ON listening_history (track_id);
