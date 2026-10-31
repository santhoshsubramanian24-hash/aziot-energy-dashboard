import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

import database
from tuya_service import TuyaClient

app = FastAPI(title="AZIOT Smart MCB Energy Dashboard")

# Initialize database tables on startup
database.init_db()

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

async def background_sync_worker():
    """Periodically syncs the latest 7 days from Tuya every 4 hours automatically."""
    await asyncio.sleep(10) # Initial wait
    while True:
        try:
            settings = database.get_settings()
            client = get_client()
            dev_id = settings.get("tuya_device_id", "").strip()
            if client and dev_id:
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=7)
                s_day = start_dt.strftime("%Y%m%d")
                e_day = end_dt.strftime("%Y%m%d")
                items = client.get_daily_energy_statistics(dev_id, s_day, e_day)
                for item in items:
                    database.upsert_daily_energy(item["date"], item["energy_kwh"], notes="Cloud Auto-Sync")
                print(f"[Auto-Sync] Synced {len(items)} days from Tuya Cloud at {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"[Auto-Sync Error] {e}")
        # Run every 4 hours
        await asyncio.sleep(4 * 3600)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(background_sync_worker())

class SettingsPayload(BaseModel):
    tuya_region: Optional[str] = "in"
    tuya_client_id: Optional[str] = ""
    tuya_client_secret: Optional[str] = ""
    tuya_device_id: Optional[str] = ""
    flat_rate_per_unit: Optional[float] = 7.5
    currency_symbol: Optional[str] = "₹"
    billing_cycle_start_day: Optional[int] = 1

class ManualEntryPayload(BaseModel):
    date: str
    energy_kwh: float
    cumulative_kwh: Optional[float] = 0.0
    notes: Optional[str] = "Manual entry"

def get_client() -> Optional[TuyaClient]:
    settings = database.get_settings()
    cid = settings.get("tuya_client_id", "").strip()
    csec = settings.get("tuya_client_secret", "").strip()
    reg = settings.get("tuya_region", "in").strip()
    if not cid or not csec:
        return None
    return TuyaClient(cid, csec, reg)

@app.get("/api/settings")
def api_get_settings():
    s = database.get_settings()
    # Mask secret partially for UI display
    sec = s.get("tuya_client_secret", "")
    masked_sec = f"{sec[:4]}...{sec[-4:]}" if len(sec) > 8 else sec
    return {
        "tuya_region": s.get("tuya_region", "in"),
        "tuya_client_id": s.get("tuya_client_id", ""),
        "tuya_client_secret": s.get("tuya_client_secret", ""),
        "tuya_client_secret_masked": masked_sec,
        "tuya_device_id": s.get("tuya_device_id", ""),
        "flat_rate_per_unit": float(s.get("flat_rate_per_unit", 7.5)),
        "currency_symbol": s.get("currency_symbol", "₹"),
        "billing_cycle_start_day": int(s.get("billing_cycle_start_day", 1))
    }

@app.post("/api/settings")
def api_save_settings(payload: SettingsPayload):
    curr = database.get_settings()
    updates = {}
    if payload.tuya_region is not None:
        updates["tuya_region"] = payload.tuya_region
    if payload.tuya_client_id is not None:
        updates["tuya_client_id"] = payload.tuya_client_id
    if payload.tuya_client_secret is not None and not payload.tuya_client_secret.startswith("..."):
        updates["tuya_client_secret"] = payload.tuya_client_secret
    if payload.tuya_device_id is not None:
        updates["tuya_device_id"] = payload.tuya_device_id
    if payload.flat_rate_per_unit is not None:
        updates["flat_rate_per_unit"] = str(payload.flat_rate_per_unit)
    if payload.currency_symbol is not None:
        updates["currency_symbol"] = payload.currency_symbol
    if payload.billing_cycle_start_day is not None:
        updates["billing_cycle_start_day"] = str(payload.billing_cycle_start_day)

    database.update_settings(updates)
    return {"status": "success", "message": "Settings updated"}

@app.post("/api/test-connection")
def api_test_connection():
    settings = database.get_settings()
    client = get_client()
    dev_id = settings.get("tuya_device_id", "").strip()

    if not client:
        raise HTTPException(status_code=400, detail="Tuya Client ID & Secret are required.")
    if not dev_id:
        raise HTTPException(status_code=400, detail="Tuya Device ID is required.")

    try:
        token = client.get_token()
        status = client.get_device_status(dev_id)
        return {
            "status": "success",
            "message": "Successfully connected to Tuya Cloud & AZIOT Smart MCB!",
            "token_acquired": bool(token),
            "device_metrics": status
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/live-status")
def api_live_status():
    settings = database.get_settings()
    client = get_client()
    dev_id = settings.get("tuya_device_id", "").strip()

    if not client or not dev_id:
        return {
            "configured": False,
            "message": "Please configure Tuya credentials in Settings"
        }

    try:
        metrics = client.get_device_status(dev_id)
        # If cumulative kWh was reported, record it in database for today
        if metrics.get("cumulative_kwh", 0) > 0:
            today_str = datetime.now().strftime("%Y-%m-%d")
            # Get latest previous cumulative
            prev = database.get_latest_cumulative()
            delta = 0.0
            if prev and metrics["cumulative_kwh"] >= prev:
                delta = metrics["cumulative_kwh"] - prev
            database.upsert_daily_energy(today_str, delta, metrics["cumulative_kwh"], notes="Live sync")

        return {
            "configured": True,
            "online": True,
            "metrics": metrics,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        return {
            "configured": True,
            "online": False,
            "error": str(e)
        }

@app.post("/api/sync")
def api_sync_data(days: int = 30):
    settings = database.get_settings()
    client = get_client()
    dev_id = settings.get("tuya_device_id", "").strip()

    if not client or not dev_id:
        raise HTTPException(status_code=400, detail="Tuya API credentials or Device ID missing in Settings")

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    s_day = start_dt.strftime("%Y%m%d")
    e_day = end_dt.strftime("%Y%m%d")

    try:
        # Also grab live status to update today's cumulative reading
        try:
            live = client.get_device_status(dev_id)
            if live.get("cumulative_kwh", 0) > 0:
                today_s = datetime.now().strftime("%Y-%m-%d")
                database.upsert_daily_energy(today_s, 0.0, live["cumulative_kwh"], notes="Live snapshot")
        except Exception:
            pass

        items = client.get_daily_energy_statistics(dev_id, s_day, e_day)
        count = 0
        for item in items:
            d_str = item.get("date")
            kwh = item.get("energy_kwh", 0.0)
            if d_str and kwh >= 0:
                database.upsert_daily_energy(d_str, kwh, notes="Tuya API Sync")
                count += 1

        return {"status": "success", "synced_days": count}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sync error: {str(e)}")

@app.get("/api/energy")
def api_get_energy(start_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
                   end_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")):
    records = database.get_energy_range(start_date, end_date)
    settings = database.get_settings()
    rate = float(settings.get("flat_rate_per_unit", 7.5))
    currency = settings.get("currency_symbol", "₹")

    # If no records exist in DB yet, try to auto-sync once if credentials exist
    if not records:
        try:
            client = get_client()
            dev_id = settings.get("tuya_device_id", "").strip()
            if client and dev_id:
                s_day = start_date.replace("-", "")
                e_day = end_date.replace("-", "")
                items = client.get_daily_energy_statistics(dev_id, s_day, e_day)
                for item in items:
                    database.upsert_daily_energy(item["date"], item["energy_kwh"], notes="Auto-sync")
                records = database.get_energy_range(start_date, end_date)
        except Exception:
            pass

    total_kwh = sum(r["energy_kwh"] for r in records)
    total_cost = sum(r["cost"] for r in records)
    num_days = len(records)
    avg_daily = round(total_kwh / num_days, 2) if num_days > 0 else 0.0
    peak_record = max(records, key=lambda x: x["energy_kwh"]) if records else None

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_kwh": round(total_kwh, 2),
        "total_cost": round(total_cost, 2),
        "currency": currency,
        "rate_per_unit": rate,
        "days_count": num_days,
        "avg_daily_kwh": avg_daily,
        "peak_day": {
            "date": peak_record["date"] if peak_record else "-",
            "kwh": peak_record["energy_kwh"] if peak_record else 0.0
        },
        "records": records
    }

@app.post("/api/manual-entry")
def api_manual_entry(payload: ManualEntryPayload):
    database.upsert_daily_energy(
        date_str=payload.date,
        energy_kwh=payload.energy_kwh,
        cumulative_kwh=payload.cumulative_kwh or 0.0,
        notes=payload.notes or "Manual"
    )
    return {"status": "success", "message": f"Saved entry for {payload.date}"}

# Serve Frontend static assets
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5050, reload=True)
