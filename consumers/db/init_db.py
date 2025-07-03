from db.schema import SWAP_EVENTS_TABLE_SQL
from db.db import get_connection

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(SWAP_EVENTS_TABLE_SQL)
    conn.commit()
    return conn, cursor