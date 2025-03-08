# Music Muse

Music Muse is a web application designed to let you explore and analyze your music listening history. Inspired by platforms like StatMuse for sports and stats.fm/Last.fm for music tracking, Music Muse provides detailed insights into your listening habits.

## Features

- **Top Tracks:** View your most played songs with detailed statistics.
- **Top Albums:** Discover which albums you've spent the most time with.
- **Top Artists:** Identify artists that dominate your listening history.
- **Music Muse:** Browse your listening history with custom queries.

### Installation

1. Clone the repository:
```bash
git clone https://github.com/seanburnzs/musicMuse.git
cd musicmuse
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Database Setup

1. Create a PostgreSQL database:
```bash
createdb musicmuse_db
```

2. Initialize the database schema:
```bash
psql -d musicmuse_db -f db_schema.sql
```

3. Create a `.env` file in the root directory with your database credentials:
```env
DB_NAME=musicmuse_db
DB_USER=your_username
DB_PASSWORD=your_password
DB_PASS=
DB_PORT=
SPOTIPY_CLIENT_ID=
SPOTIPY_CLIENT_SECRET=
SPOTIPY_REDIRECT_URI=
```

## Importing Your Data

1. Download your Spotify listening data from your Spotify account (Privacy settings) and place the JSON files in a directory called `streaming_data`.

2. Parse and import the data:
```bash
python parse_spotify_json.py
```

## Running the Application

Start the server:
```bash
python app.py
```

Visit [http://localhost:5000](http://localhost:5000) in your browser to access Music Muse.

## Keeping Data Up to Date
- The scrobbler.py script can be set up to run periodically to keep your listening history up to date with your recent Spotify activity:
```bash
python scrobbler.py
```

- To continuously update your listening data, automate with:
  - **Cron jobs** on Linux/macOS
  - **Task Scheduler** on Windows

## Features & Queries

Music Muse allows you to query insights such as:
- "What artists do I listen to the most?"
- "Which albums do I listen to the most?"
- "What songs do I listen to the most?"
- "Which artists do I listen to the most on Sundays?"
- "What are my top tracks in the Summer?"

# You can also ask more complex queries
- "What were my top tracks on Fridays in the Summer of 2022 after 6PM?"

## Technical Overview

- `db_schema.sql`: Defines tables for artists, albums, tracks, and history.
- `parse_spotify_json.py`: Imports and processes Spotify JSON data.
- `scrobbler.py`: Keeps your listening history automatically updated.
- `app.py`: Runs the Flask web application.

## License

[MIT License](LICENSE)