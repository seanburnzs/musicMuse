-- db_schema.sql
-- CREATE EXTENSION IF NOT EXISTS citext;

-- Artists table
CREATE TABLE IF NOT EXISTS artists (
    artist_id SERIAL PRIMARY KEY,
    artist_name VARCHAR(255) NOT NULL,
    CONSTRAINT unique_artist_name UNIQUE (artist_name),
    image_url VARCHAR(255)
);

-- Albums table
CREATE TABLE IF NOT EXISTS albums (
    album_id SERIAL PRIMARY KEY,
    album_name VARCHAR(255) NOT NULL,
    artist_id INT REFERENCES artists (artist_id) ON DELETE CASCADE,
    CONSTRAINT unique_album_artist UNIQUE (album_name, artist_id),
    image_url VARCHAR(255)
);

-- Tracks table
CREATE TABLE IF NOT EXISTS tracks (
    track_id SERIAL PRIMARY KEY,
    track_name VARCHAR(255) NOT NULL,
    album_id INT REFERENCES albums (album_id) ON DELETE CASCADE,
    CONSTRAINT unique_track_album UNIQUE (track_name, album_id),
    popularity INTEGER DEFAULT 50
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(user_id)
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_listening_timestamp ON listening_history (timestamp);
CREATE INDEX IF NOT EXISTS idx_listening_track_id ON listening_history (track_id);
CREATE INDEX IF NOT EXISTS idx_listening_history_user_id ON listening_history(user_id);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    profile_image_url VARCHAR(255)
);

-- Add popularity column to tracks for obscurity calculation
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS popularity INTEGER DEFAULT 50;

-- Add image_url columns to artists and albums
ALTER TABLE artists ADD COLUMN IF NOT EXISTS image_url VARCHAR(255);
ALTER TABLE albums ADD COLUMN IF NOT EXISTS image_url VARCHAR(255);

-- Life events table
CREATE TABLE IF NOT EXISTS user_events (
    event_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) NOT NULL,
    name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    description TEXT,
    category VARCHAR(50),
    color VARCHAR(20) DEFAULT '#5c6bc0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on user_id in events
CREATE INDEX IF NOT EXISTS idx_user_events_user_id ON user_events(user_id);

-- Genres table
CREATE TABLE IF NOT EXISTS genres (
    genre_id SERIAL PRIMARY KEY,
    genre_name VARCHAR(100) UNIQUE NOT NULL
);

-- Track genres mapping table
CREATE TABLE IF NOT EXISTS track_genres (
    track_id INTEGER REFERENCES tracks(track_id) NOT NULL,
    genre_id INTEGER REFERENCES genres(genre_id) NOT NULL,
    PRIMARY KEY (track_id, genre_id)
);

-- Add similarity extension for fuzzy matching event names
CREATE EXTENSION IF NOT EXISTS pg_trgm;
