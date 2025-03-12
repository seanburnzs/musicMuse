"""Constants used throughout the application."""

# Database tables
TABLE_USERS = "users"
TABLE_LISTENING_HISTORY = "listening_history"
TABLE_TRACKS = "tracks"
TABLE_ALBUMS = "albums"
TABLE_ARTISTS = "artists"
TABLE_USER_EVENTS = "user_events"
TABLE_USER_FOLLOWS = "user_follows"
TABLE_USER_HALL_OF_FAME = "user_hall_of_fame"
TABLE_USER_SETTINGS = "user_settings"

# Time ranges
TIME_RANGE_ALL_TIME = "all_time"
TIME_RANGE_THIS_WEEK = "this_week"
TIME_RANGE_THIS_MONTH = "this_month"
TIME_RANGE_THIS_YEAR = "this_year"
TIME_RANGE_YEAR_2024 = "year_2024"
TIME_RANGE_YEAR_2023 = "year_2023"
TIME_RANGE_CUSTOM = "custom"

# Time units
TIME_UNIT_HOURS = "hours"
TIME_UNIT_MINUTES = "minutes"

# Privacy settings
PRIVACY_EVERYONE = "everyone"
PRIVACY_FRIENDS = "friends"
PRIVACY_PRIVATE = "private"

# Item types
ITEM_TYPE_TRACK = "track"
ITEM_TYPE_ALBUM = "album"
ITEM_TYPE_ARTIST = "artist"

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# File upload
ALLOWED_EXTENSIONS = {"json"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB