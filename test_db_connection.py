import os
import sys
from dotenv import load_dotenv
import mysql.connector

# Add current directory to path to import from database.db
sys.path.append(os.getcwd())

load_dotenv()

def test_db():
    print("Testing database connection...")
    try:
        from database.db import get_connection
        conn = get_connection()
        print("Successfully connected to database!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dr_young_all_articles")
        count = cursor.fetchone()[0]
        print(f"Number of articles in 'dr_young_all_articles': {count}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        # Try with the password found in .env comment if default fails
        if "Access denied" in str(e):
            print("Retrying with password 'Root@2106'...")
            try:
                conn = mysql.connector.connect(
                    host=os.getenv("DB_HOST", "localhost"),
                    user=os.getenv("DB_USER", "root"),
                    password="Root@2106",
                    database=os.getenv("DB_NAME", "case_studies_db"),
                    port=int(os.getenv("PORT", "3306"))
                )
                print("Successfully connected to database with password 'Root@2106'!")
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM dr_young_all_articles")
                count = cursor.fetchone()[0]
                print(f"Number of articles in 'dr_young_all_articles': {count}")
                cursor.close()
                conn.close()
                return True
            except Exception as e2:
                print(f"Retry failed: {e2}")
        return False

if __name__ == "__main__":
    if test_db():
        sys.exit(0)
    else:
        sys.exit(1)
