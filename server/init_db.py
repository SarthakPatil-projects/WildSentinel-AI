import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3307")),
    database=os.getenv("DB_NAME", "wildsentinel"),
    user=os.getenv("DB_USER", "wildsentinel_app"),
    password=os.getenv("DB_PASSWORD", "")
)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_time VARCHAR(40),
    camera_id VARCHAR(100),
    confidence FLOAT,
    details JSON,
    evidence_path VARCHAR(500),
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
cur.close()
conn.close()
print("WildSentinel database table is ready.")
