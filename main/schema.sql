-- Create the user_spotify_settings table
CREATE TABLE IF NOT EXISTS user_spotify_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    access_token TEXT,
    refresh_token TEXT,
    token_expiry BIGINT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
); 