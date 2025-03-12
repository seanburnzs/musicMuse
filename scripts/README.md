# Database Optimization Scripts

This directory contains scripts for optimizing the MusicMuse database performance and implementing data deduplication.

## Available Scripts

### 1. add_indexes.py
Adds essential indexes to improve query performance across the database. This script creates indexes on frequently queried columns to speed up database operations.

### 2. add_constraints.py
Adds data integrity constraints to ensure valid data throughout the database. These constraints enforce business rules and prevent invalid data from being inserted.

### 3. create_analytics_views.py
Creates materialized views for frequently accessed analytics, improving read performance for complex queries. This includes views for user listening summaries, top tracks, and more.

### 4. optimize_database.py
A comprehensive optimization script that implements:
- Additional strategic indexes
- Metadata enhancements for better track identification
- Track deduplication infrastructure
- Database optimization for performance

### 5. identify_duplicates.py
A tool for identifying and merging duplicate tracks in the database. This script provides:
- Interactive duplicate review and merging
- Automated merging of highly similar tracks
- Detailed logging of merge operations

## Recommended Execution Order

For initial database optimization, run these scripts in the following order:

1. `add_constraints.py` - To establish data integrity
2. `add_indexes.py` - To improve basic query performance
3. `optimize_database.py` - To set up deduplication infrastructure
4. `identify_duplicates.py` - To find and merge duplicate tracks
5. `create_analytics_views.py` - To create materialized views after deduplication

## Usage

To run any script, execute it directly using Python:

```bash
python scripts/optimize_database.py
```

For the interactive duplicate identification tool:

```bash
python scripts/identify_duplicates.py
```

## Important Notes

- These scripts use PostgreSQL-specific features and are designed for the MusicMuse database schema.
- Always make a backup of your database before running optimization scripts.
- Some operations (particularly in identify_duplicates.py) modify data and cannot be easily reversed.
- Database partitioning (commented out in optimize_database.py) is an advanced operation and should be tested thoroughly in a non-production environment first. 