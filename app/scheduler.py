from datetime import datetime
import os
import re
import requests
from database import create_mealplan, fetch_mealplan
from services.pdf_parser import extract_meals
from bs4 import BeautifulSoup
UPDATE_INTERVAL_HOURS = 24

def get_current_week_range():
    """
    Get the current two-week range based on the pattern:
    Weeks 6,7 → published in week 6
    Weeks 8,9 → published in week 8
    
    Returns:
        tuple: (first_week, second_week) for the current range
    """
    current_week = datetime.now().isocalendar()[1]
    
    # Determine which two-week block we're in
    # Even weeks start a new block: 6-7, 8-9, 10-11, etc.
    if current_week % 2 == 0:
        first_week = current_week
        second_week = current_week + 1
    else:
        first_week = current_week - 1
        second_week = current_week
    
    return first_week, second_week

def scrape_pdf_url():
    """
    Scrape the PDF URL from the website.
    """
    BASE_URL = "https://www.malteser-st-bernhard-gymnasium.de/"
    page = requests.get(BASE_URL)
    soup = BeautifulSoup(page.content, "html.parser")
    mensa_link = soup.find('h3', string='Mensa Angebot der nächsten 2 Wochen').find_parent('a')
    
    if mensa_link:
        return BASE_URL + mensa_link['href']
    else:
        print(f"Scraping failed: No link found")
        return None

def download_and_parse_pdf():
    """
    Download the latest PDF from the given URL and parse it.
    The PDF contains two weeks of meal plans.
    Stores each week separately in the database.
    """
    try:
        first_week, second_week = get_current_week_range()
        
        # Check if both weeks already exist in database
        year = datetime.now().year
        week1_exists = fetch_mealplan(year, first_week) is not None
        week2_exists = fetch_mealplan(year, second_week) is not None
        
        if week1_exists and week2_exists:
            print(f"[{datetime.now()}] Weeks {first_week} and {second_week} already in database. Skipping download.")
            return True
        
        # Construct PDF URL with the first week number
        pdf_url = scrape_pdf_url()
        if not pdf_url:
            return False
        
        print(f"[{datetime.now()}] Downloading PDF for weeks {first_week}-{second_week} from {pdf_url} ...")
        response = requests.get(pdf_url, timeout=10)
        response.raise_for_status()
        
        # Create archive directory if it doesn't exist
        os.makedirs("./archive", exist_ok=True)
        
        pdf_path = f"./archive/Speisenplan_KW_{first_week:02d}.pdf"
        
        with open(pdf_path, "wb") as f:
            f.write(response.content)
        
        print(f"[{datetime.now()}] Parsing PDF ...")
        parsed_data = extract_meals(pdf_path)
        
        if not parsed_data:
            print(f"[{datetime.now()}] No data found in PDF")
            return False
        
        # The PDF contains two weeks, so we need to split the data
        # Group days by their week number
        week1_days = {}
        week2_days = {}
        
        for date_iso, day_data in parsed_data.days.items():
            # Parse the date to get its week number
            date_obj = datetime.fromisoformat(date_iso)
            day_week = date_obj.isocalendar()[1]
            
            if day_week == first_week:
                week1_days[date_iso] = day_data
            elif day_week == second_week:
                week2_days[date_iso] = day_data
        
        # Create separate Mealplan objects for each week
        from models import Mealplan
        
        if week1_days and not week1_exists:
            mealplan1 = Mealplan(
                year=year,
                week=first_week,
                days=week1_days
            )
            create_mealplan(mealplan1)
            print(f"[{datetime.now()}] Week {first_week} saved to SQLite.")
        
        if week2_days and not week2_exists:
            mealplan2 = Mealplan(
                year=year,
                week=second_week,
                days=week2_days
            )
            create_mealplan(mealplan2)
            print(f"[{datetime.now()}] Week {second_week} saved to SQLite.")
        
        print(f"[{datetime.now()}] Meal plan updated successfully")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error downloading PDF: {e}")
        return False
    except Exception as e:
        print(f"[{datetime.now()}] Error parsing PDF: {e}")
        return False

if __name__ == "__main__":
    # Test the script
    download_and_parse_pdf()