# Backend Structure

## Architecture Overview

The MusicMuse backend follows a modular architecture designed around the Flask web framework. The application utilizes a PostgreSQL database for data storage, Redis for caching, and Celery for background task processing.

## Core Components

### Main Application (app.py)
- **Entry point** for the Flask application
- Contains **route handlers** for all web endpoints
- Implements **security middleware** (CSRF protection)
- Handles **database connections**
- Provides **utility functions** for common operations

### Database Schema

#### Primary Tables
- **users**: User account information and credentials
- **listening_history**: Individual song plays with timestamps and duration
- **tracks**: Music track information
- **albums**: Album information with relations to artists
- **artists**: Music artist information

#### Relational Tables
- **user_events**: Life events associated with users
- **user_follows**: User following relationships
- **user_hall_of_fame**: Users' selected favorite items
- **user_settings**: User preferences and configuration

### Natural Language Processing (musicnlp/)

The NLP system uses a pipeline architecture to process natural language queries:

1. **Parser** (parser.py): Extracts intents, entities, time ranges, and other parameters from text
2. **Analyzer** (analyzer.py): Enhances parsed data with context and determines query attributes
3. **Executor** (executor.py): Translates structured data into database queries
4. **DB Connector** (db_connector.py): Interfaces with PostgreSQL
5. **Client** (client.py): Orchestrates the entire pipeline

### Background Processing (tasks/)

Asynchronous tasks utilizing Celery:

- **Data Import** (data_import.py): Process uploaded streaming history files
- **Analytics** (analytics.py): Generate user summaries and statistics
- **Scheduled Tasks** (scheduled_tasks.py): Database maintenance and cleanup

### Utilities (utils/)

Shared utility functions and helpers:

- **Security** (security.py): CSRF protection, password hashing
- **Caching** (cache.py): Redis cache decorators and utilities
- **Error Handlers** (error_handlers.py): Exception handling decorators
- **Date Utilities** (date_utils.py): Date range calculations and formatting
- **Constants** (constants.py): Application-wide constants and configuration

## Database Optimization

### Materialized Views
Materialized views are used to pre-compute expensive queries:
- **user_listening_summary**: Aggregate listening statistics
- **user_top_tracks**: Most played tracks by user
- **user_top_artists**: Most played artists by user
- **user_listening_by_hour**: Listening patterns by hour of day
- **user_listening_by_day**: Listening patterns by day of week

### Indexes
Strategic indexes improve query performance:
- User-based indexes on listening history
- Timestamp indexes for time-range queries
- Foreign key indexes for join operations
- Compound indexes for common query patterns

## API Endpoints

### Public APIs
- **/api/top_items**: Retrieve top tracks, albums, or artists with filtering
- **/api/user_profile**: User profile data and statistics
- **/api/music_muse**: Natural language query processing

## Security Measures

- **CSRF Protection**: Token validation for all state-changing operations
- **Password Security**: One-way hashing with werkzeug
- **Input Validation**: Form data validation and sanitization
- **File Upload Security**: Size limits, extension validation, secure naming

## Scaling Considerations

- **Connection Pooling**: Database connections are managed efficiently
- **Background Processing**: Heavy tasks are offloaded to worker processes
- **Caching Strategy**: Frequently accessed data is cached in Redis
- **Database Optimizations**: Indexes and constraints to improve performance
- **Modular Design**: Components can be scaled independently
