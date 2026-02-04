from datetime import datetime
import json
import sqlite3
import requests
from database import create_mealplan
from services.pdf_parser import extract_meals

PDF_URL = "https://www.malteser-st-bernhard-gymnasium.de/fileadmin/Files_sites/Fachbereiche/St_Bernhard_Gymnasium/pdf/Mensaplaene/Speisenplan-KW_06-St.B_-_Kopie-zusammengefuegt.pdf"  # Replace with real URL

UPDATE_INTERVAL_HOURS = 24
def download_and_parse_pdf():
    """
    Download the latest PDF from the given URL and parse it into JSON.
    Stores result in the global `mealplan_data`.
    """
    global mealplan_data
    try:
        print(f"[{datetime.now()}] Downloading PDF from {PDF_URL} ...")
        response = requests.get(PDF_URL, timeout=10)
        response.raise_for_status()

        pdf_path = f"./archive/Speisenplan_KW_{datetime.now().isocalendar()[1]}.pdf"
        
        with open(pdf_path, "wb") as f:
            f.write(response.content)
        
        print(f"[{datetime.now()}] Parsing PDF ...")
        parsed_data = extract_meals(pdf_path)
        if parsed_data:
            mealplan_data = parsed_data
            print(f"[{datetime.now()}] Meal plan updated successfully")
        else:
            print(f"[{datetime.now()}] No data found in PDF")

        if parsed_data:
            create_mealplan(parsed_data)
            print("Saved to SQLite.")
    except Exception as e:
        print(f"[{datetime.now()}] Error downloading or parsing PDF: {e}")
