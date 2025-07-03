import os
import psycopg2

def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "ozi"),
        user=os.getenv("POSTGRES_USER", "ozi_user"),
        password=os.getenv("POSTGRES_PASSWORD", "supersecret"),
        port=os.getenv("POSTGRES_PORT", "5432"),
  
    )