import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "energy_data.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Table for daily energy consumption
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_energy (
            date TEXT PRIMARY KEY,
            energy_kwh REAL NOT NULL DEFAULT 0.0,
            cumulative_kwh REAL DEFAULT 0.0,
            cost REAL DEFAULT 0.0,
            notes TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for app settings & tariff config
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Insert default settings if not exists
    defaults = {
        "tariff_type": "flat",         # "flat" or "slabs"
        "flat_rate_per_unit": os.getenv("FLAT_RATE_PER_UNIT", "7.50"),  # INR per kWh
        "currency_symbol": os.getenv("CURRENCY_SYMBOL", "₹"),
        "billing_cycle_start_day": os.getenv("BILLING_CYCLE_START_DAY", "1"),
        "tuya_region": os.getenv("TUYA_REGION", "in"),
        "tuya_client_id": os.getenv("TUYA_CLIENT_ID", "yganpgxmqnw4uqhcgk55"),
        "tuya_client_secret": os.getenv("TUYA_CLIENT_SECRET", "8f63b42442b348f7954345755b6a9f51"),
        "tuya_device_id": os.getenv("TUYA_DEVICE_ID", "d742607eadedc5fa30bwcz")
    }
    
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        # If env var is set, update it
        if os.getenv(k.upper()):
            cursor.execute("UPDATE settings SET value = ? WHERE key = ?", (os.getenv(k.upper()), k))
        
    conn.commit()
    conn.close()

def get_settings() -> Dict[str, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def update_settings(settings: Dict[str, str]):
    conn = get_connection()
    cursor = conn.cursor()
    for k, v in settings.items():
        cursor.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (k, str(v)))
    conn.commit()
    conn.close()

def upsert_daily_energy(date_str: str, energy_kwh: float, cumulative_kwh: float = 0.0, notes: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate cost using flat rate or slabs
    cursor.execute("SELECT value FROM settings WHERE key = 'flat_rate_per_unit'")
    row = cursor.fetchone()
    rate = float(row["value"]) if row and row["value"] else 7.5
    cost = round(energy_kwh * rate, 2)
    
    cursor.execute("""
        INSERT INTO daily_energy (date, energy_kwh, cumulative_kwh, cost, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(date) DO UPDATE SET
            energy_kwh = CASE WHEN excluded.energy_kwh > 0 THEN excluded.energy_kwh ELSE daily_energy.energy_kwh END,
            cumulative_kwh = CASE WHEN excluded.cumulative_kwh > 0 THEN excluded.cumulative_kwh ELSE daily_energy.cumulative_kwh END,
            cost = CASE WHEN excluded.energy_kwh > 0 THEN excluded.cost ELSE daily_energy.cost END,
            notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE daily_energy.notes END,
            updated_at = CURRENT_TIMESTAMP
    """, (date_str, round(energy_kwh, 3), round(cumulative_kwh, 3), cost, notes))
    
    conn.commit()
    conn.close()

def get_energy_range(start_date: str, end_date: str) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, energy_kwh, cumulative_kwh, cost, notes, updated_at
        FROM daily_energy
        WHERE date >= ? AND date <= ?
        ORDER BY date ASC
    """, (start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_latest_cumulative() -> Optional[float]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT cumulative_kwh FROM daily_energy WHERE cumulative_kwh > 0 ORDER BY date DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row["cumulative_kwh"] if row else None

