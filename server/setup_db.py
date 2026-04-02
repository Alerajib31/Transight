"""
Database setup script - creates transight_db if it doesn't exist.
Run: python setup_db.py
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from env_utils import get_database_admin_config, load_project_env_files

load_project_env_files()
DB_CONFIG = get_database_admin_config()

def setup_database():
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_CONFIG["target_db_name"],))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(DB_CONFIG["target_db_name"])
                )
            )
            print(f"[OK] Database '{DB_CONFIG['target_db_name']}' created successfully!")
        else:
            print(f"[INFO] Database '{DB_CONFIG['target_db_name']}' already exists.")
        
        cursor.close()
        conn.close()
        print(
            "[OK] Database setup complete "
            f"({DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['target_db_name']})."
        )
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == "__main__":
    setup_database()
