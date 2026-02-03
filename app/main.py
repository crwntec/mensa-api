"""
FastAPI app to serve German meal plans (Speisenplan) with scheduled updates.

Features:
- API endpoint to get current meal plan
- APScheduler job to download & parse PDF periodically
"""

import json
import os
import sqlite3
import requests
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from scheduler import download_and_parse_pdf
from datetime import datetime

# =========================
# CONFIGURATION
# =========================

# FastAPI app
app = FastAPI(title="mensa API")


# Start scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(download_and_parse_pdf, "interval", hours=24)
scheduler.start()

# Initial fetch on startup
download_and_parse_pdf()

def get_stored_plan():
    try:
        conn = sqlite3.connect("mealplan.db")
        c = conn.cursor()
        c.execute("SELECT json_data FROM plan WHERE id = 1")
        row = c.fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None
# =========================
# API ENDPOINTS
# =========================
@app.get("/mealplan")
def get_mealplan():
    data = get_stored_plan()
    if not data:
        return {"success": False, "message": "Meal plan not available"}
    return {"success": True, "data": data}




