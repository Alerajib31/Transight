"""
Database setup script - creates transight_db if it doesn't exist.
Run: python setup_db.py
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_HOST = "localhost"
DB_USER = "postgres"
DB_PASS = "R@jibale3138"
DB_NAME = "transight_db"

def setup_database():
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"[OK] Database '{DB_NAME}' created successfully!")
        else:
            print(f"[INFO] Database '{DB_NAME}' already exists.")
        
        cursor.close()
        conn.close()
        print("[OK] Database setup complete.")
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == "__main__":
    setup_database()
