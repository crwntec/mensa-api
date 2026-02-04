"""
FastAPI app to serve German meal plans (Speisenplan) with scheduled updates.

Features:
- API endpoint to get current meal plan
- APScheduler job to download & parse PDF periodically
"""
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from database import fetch_mealplan, init_db
from scheduler import download_and_parse_pdf

# =========================
# CONFIGURATION
# =========================

# FastAPI app
app = FastAPI(title="mensa API")


# Start scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(download_and_parse_pdf, "interval", hours=24)
scheduler.start()
init_db()
# Initial fetch on startup
download_and_parse_pdf()
@app.get("/mealplan")
def get_mealplan():
    """
    Retrieve the meal plan for a specific week and year.
    """
    data = fetch_mealplan(2026,6)
    if not data:
        return {"success": False, "message": "Meal plan not available"}
    return {"success": True, "data": data}




