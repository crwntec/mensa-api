from datetime import datetime
import json
import sqlite3
import requests
from services.pdf_parser import extract_meals

PDF_URL = "https://www.malteser-st-bernhard-gymnasium.de/fileadmin/Files_sites/Fachbereiche/St_Bernhard_Gymnasium/pdf/Mensaplaene/Speisenplan-KW_06-St.B_-_Kopie-zusammengefuegt.pdf"  # Replace with real URL
LOCAL_PDF_PATH = "./tmp/Speisenplan.pdf"
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
        
        with open(LOCAL_PDF_PATH, "wb") as f:
            f.write(response.content)
        
        print(f"[{datetime.now()}] Parsing PDF ...")
        parsed_data = extract_meals(LOCAL_PDF_PATH)
        if parsed_data:
            mealplan_data = parsed_data
            print(f"[{datetime.now()}] Meal plan updated successfully")
        else:
            print(f"[{datetime.now()}] No data found in PDF")

        if parsed_data:
            save_to_db(parsed_data)
            print("Saved to SQLite.")
    except Exception as e:
        print(f"[{datetime.now()}] Error downloading or parsing PDF: {e}")
   

def save_to_db(data):
    conn = sqlite3.connect('mealplan.db')
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS plan (id INTEGER PRIMARY KEY, json_data TEXT)")
    # Overwrite the old plan with the new one (minimalist approach)
    c.execute("INSERT OR REPLACE INTO plan (id, json_data) VALUES (1, ?)", (json.dumps(data),))
    conn.commit()
    conn.close()