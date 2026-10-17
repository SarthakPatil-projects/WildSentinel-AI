import os, json
from pathlib import Path
import streamlit as st
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="WildSentinel AI", layout="wide")
st.title("WildSentinel AI — Leopard Monitoring")
st.caption("Detection events received from the edge device")

def db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3307")),
        database=os.getenv("DB_NAME", "wildsentinel"),
        user=os.getenv("DB_USER", "wildsentinel_app"),
        password=os.getenv("DB_PASSWORD", "")
    )

try:
    conn = db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM events ORDER BY id DESC LIMIT 100")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    st.metric("Events received", len(rows))
    if not rows:
        st.info("No leopard events received yet.")
    else:
        st.dataframe([
            {k: v for k, v in row.items() if k not in ("details",)}
            for row in rows
        ], use_container_width=True)
        st.subheader("Recent evidence")
        for row in rows[:10]:
            path = Path(row["evidence_path"])
            if path.exists():
                st.image(str(path), caption=f'Event #{row["id"]} — {row["event_time"]}', width=500)
except Exception as exc:
    st.error(f"Could not load events: {exc}")
    st.info("Check that MySQL is running and the .env credentials are correct.")
