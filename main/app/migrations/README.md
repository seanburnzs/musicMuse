# Migration to Case-Insensitive Database

This folder contains scripts to migrate your PostgreSQL database to use case-insensitive collation for text columns. This will allow queries to match results regardless of case (e.g., searching for "Michael Jackson" will also match "michael jackson").

## Prerequisites

- PostgreSQL 10 or higher
- Python 3.6 or higher
- Required Python packages (install from requirements.txt)
- A backup of your database (VERY IMPORTANT!)

## Installation

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Migration Steps

### 1. Create Configuration File

Create a `config.ini` file in the same directory with the following structure:

```ini
[postgresql]
host=localhost
port=5432
database=your_database_name
user=your_username
password=your_password
```

Replace the values with your actual PostgreSQL connection information.

### 2. Back Up Your Database

Before running any migration, make a full backup of your database using pgAdmin 4 or the following command:

```bash
pg_dump -h localhost -U your_username -d your_database_name -F c -f database_backup.dump
```

### 3. Run the Deduplication Script

This is a critical step before applying the case-insensitive migration. The deduplication script identifies and merges duplicate entries that differ only by case (e.g., "Charli XCX" and "charli xcx").

First, run a dry run to see what duplicates would be merged without making any changes:

```bash
python run_deduplication.py --dry-run
```

Review the output to ensure you understand which duplicates will be merged. Then run the actual deduplication:

```bash
python run_deduplication.py
```

The deduplication script will:
1. Find and merge duplicate artists that differ only by case
2. Handle special cases where different case versions of the same artist have albums with the same name
3. Find and merge duplicate albums that differ only by case (within the same artist)
4. Handle special cases where different case versions of the same album have tracks with the same name
5. Find and merge duplicate tracks that differ only by case (within the same album)
6. Update all references to point to the canonical version of each entity

This step is necessary because the case-insensitive migration creates unique constraints that would fail if duplicates exist.

### 4. Apply the Case-Insensitive Migration

After deduplication is complete, you can apply the case-insensitive migration:

```bash
python apply_case_insensitive.py
```

If your database has views or materialized views that depend on the columns being changed, use the following flag:

```bash
python apply_case_insensitive.py --force-recreate-views
```

This flag will automatically drop and recreate dependent views during the migration.

### 5. Test the Case-Insensitive Functionality

After completing the migration, you can verify that the case-insensitive functionality is working correctly by running:

```bash
python test_case_insensitive.py
```

This will run test queries with different case variations to ensure that searches are now case-insensitive.

## Migration Details

The migration performs these changes:

1. Identifies all text columns in the target tables
2. Converts each text column to use case-insensitive collation (`C.UTF-8`)
3. Creates case-insensitive indexes for these columns
4. Creates case-insensitive unique constraints where needed

## Handling Database Views

If your database has views that depend on the tables being modified, you have two options:

1. **Automatic approach**: Run the migration with the `--force-recreate-views` flag, which will:
   - Drop dependent views using CASCADE before making changes
   - Apply the migration to the underlying tables
   - Recreate all the views afterward

2. **Manual approach**: If you have views with custom definitions that need special handling:
   - Get the definitions of all views using the SQL query below
   - Manually drop the views before migration
   - Apply the migration
   - Recreate the views with their definitions

SQL to get view definitions:
```sql
SELECT schemaname, viewname, definition
FROM pg_views
WHERE schemaname NOT IN ('pg_catalog', 'information_schema');

SELECT schemaname, matviewname, definition
FROM pg_matviews
WHERE schemaname NOT IN ('pg_catalog', 'information_schema');
```

## Troubleshooting

### Dependency Errors

If you encounter errors about dependent objects:

```
ERROR - Error during migration: cannot drop column "artist_name" of table "artists" because other objects depend on it
DETAIL - view potential_track_duplicates depends on column "artist_name" of table "artists"
HINT - Use DROP ... CASCADE to drop the dependent objects too.
```

Use the `--force-recreate-views` flag to automatically handle dependent views or manually drop the views before migration.

### Duplicate Entries Error

If you encounter errors about duplicate entries:

```
ERROR - Error during migration: could not create unique index "artists_artist_name_key"
DETAIL - Key (artist_name)=(Charli XCX) is duplicated.
```

This means you have entries that are duplicates when case is ignored. Run the deduplication script first:

```bash
python run_deduplication.py
```

### Constraint Violation Errors

If you encounter errors about constraint violations during deduplication:

```
ERROR - Error executing statement: duplicate key value violates unique constraint "unique_album_artist"
DETAIL: Key (album_name, artist_id)=(Charli, 23821) already exists.
```

This can happen when:
1. Two different case versions of the same artist (e.g., "Charli XCX" and "Charli xcx") both have albums with the same name
2. The database has a unique constraint on album name + artist ID

Or when:
```
ERROR - Error executing statement: duplicate key value violates unique constraint "unique_track_album" 
DETAIL: Key (track_name, album_id)=(I. The Worst Guys, 34189) already exists.
```

This can happen when:
1. Two different case versions of the same album both have tracks with the same name
2. The database has a unique constraint on track name + album ID

The updated deduplication script now handles these cases automatically by:
1. First identifying potential conflicts at each level (artist-album and album-track)
2. Merging those entries before updating their parent references
3. Then proceeding with the regular deduplication process for each entity type

### Compatibility Issues

The updated deduplication script is designed to work with all versions of psycopg2 and PostgreSQL. If you encounter any issues:

1. Make sure all files in the migrations directory have the correct permissions
2. Try running with Python 3.7 or later for the best compatibility
3. If you get "no results to fetch" errors, the script has been updated to handle this scenario
4. For older psycopg2 versions, the script now uses separate SQL queries instead of relying on multiple result sets

### Connection Issues

If you have trouble connecting to your database, check your `config.ini` file and ensure all connection details are correct.

## After Migration

After completing the migration, you should:

1. Test your application to ensure queries work correctly with the case-insensitive collation.
2. Run sample queries with different capitalizations to verify case-insensitive matching is working.
3. Update your application code to reflect that string comparisons are now case-insensitive.

## Data Processing Code Update

When using the updated schema, make sure to set `SCHEMA_CASE_INSENSITIVE = True` in your data processing code. This will optimize queries for the case-insensitive schema. 