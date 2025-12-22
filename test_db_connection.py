"""Test database connection using pyodbc."""

import pyodbc
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def test_connection():
    """Test connection to JobMatchPipeline database."""
    
    # Build connection string
    server = os.getenv('DB_SERVER', 'localhost')
    database = os.getenv('DB_DATABASE', 'JobMatchPipeline')
    driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    
    # Check if using SQL Auth or Windows Auth
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')
    
    if username and password:
        # SQL Authentication
        conn_str = (
            f'DRIVER={{{driver}}};\
SERVER={server};DATABASE={database};'
            f'UID={username};PWD={password}'
        )
    else:
        # Windows Authentication
        conn_str = (
            f'DRIVER={{{driver}}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'Trusted_Connection=yes;'
        )
    
    print("Testing database connection...")
    print(f"Server: {server}")
    print(f"Database: {database}")
    print(f"Driver: {driver}")
    print()
    
    try:
        # Attempt connection
        conn = pyodbc.connect(conn_str)
        print("✅ Connection successful!")
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"\nSQL Server Version:\n{version[:100]}...")
        
        # Check schemas exist
        cursor.execute("""
            SELECT name FROM sys.schemas 
            WHERE name IN ('staging', 'results')
            ORDER BY name
        """)
        schemas = [row[0] for row in cursor.fetchall()]
        print(f"\nSchemas found: {schemas}")
        
        # Check tables exist
        cursor.execute("""
            SELECT 
                SCHEMA_NAME(schema_id) as schema_name,
                name as table_name
            FROM sys.tables
            ORDER BY SCHEMA_NAME(schema_id), name
        """)
        tables = cursor.fetchall()
        print(f"\nTables found:")
        for schema, table in tables:
            print(f"  - {schema}.{table}")
        
        cursor.close()
        conn.close()
        
        print("\n✅ ALL DATABASE TESTS PASSED!")
        return True
        
    except pyodbc.Error as e:
        print(f"\n❌ Connection failed!")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check SQL Server service is running")
        print("2. Verify server name in .env file")
        print("3. Check ODBC driver is installed: 'ODBC Driver 17 for SQL Server'")
        print("4. If using SQL Auth, verify username/password in .env")
        return False

if __name__ == "__main__":
    test_connection()