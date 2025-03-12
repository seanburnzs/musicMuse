# Music Muse Main Application

Music Muse is a web application designed to let you explore and analyze your music listening history. Inspired by platforms like StatMuse for sports and stats.fm/Last.fm for music tracking, Music Muse provides detailed insights into your listening habits.

## Features

- **Top Tracks:** View your most played songs with detailed statistics.
- **Top Albums:** Discover which albums you've spent the most time with.
- **Top Artists:** Identify artists that dominate your listening history.
- **Music Muse:** Browse your listening history with custom queries.
- **Media Artwork:** Images for artists, albums, and tracks fetched from Spotify API.
- **Live Scrobbling:** Connect to Spotify for real-time tracking of your listening history.
- **Life Events Timeline:** Correlate your music habits with significant personal events.
- **Profile Comparison:** Compare your music taste with friends.
- **Hall of Fame:** Customize your profile to showcase your favorite music.

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the root directory with your database credentials:
```env
DB_NAME=musicmuse_db
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:5000/spotify_callback
LIVE_SCROBBLER_URL=http://localhost:5001
```

3. Initialize the database:
```bash
psql -d musicmuse_db -f schema.sql
```

4. Run the application:
```bash
python app.py
```

## Running in Production

For production deployment, use gunicorn:
```bash
gunicorn wsgi:app -w 4 -b 0.0.0.0:5000
```

## License

MIT