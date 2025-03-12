import psycopg2

# Connect to PostgreSQL database
try:
    print("Connecting to database...")
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="musicmuse_db",
        user="postgres",
        password=""  # Add your password here if needed
    )
    
    # Create a cursor
    cursor = conn.cursor()
    
    # Query to check column types
    print("Executing query...")
    query = """
    SELECT table_name, column_name, data_type, udt_name
    FROM information_schema.columns 
    WHERE table_schema = 'public' 
    AND (table_name = 'artists' OR table_name = 'albums' OR table_name = 'tracks')
    AND (column_name = 'artist_name' OR column_name = 'album_name' OR column_name = 'track_name')
    ORDER BY table_name, column_name;
    """
    
    cursor.execute(query)
    
    # Fetch results
    results = cursor.fetchall()
    
    print("\nColumn Type Information:")
    print("=" * 80)
    print(f"{'Table':<15} {'Column':<15} {'Data Type':<15} {'UDT Name':<15}")
    print("-" * 80)
    
    for row in results:
        print(f"{row[0]:<15} {row[1]:<15} {row[2]:<15} {row[3]:<15}")
    
    # Close cursor and connection
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {str(e)}") 