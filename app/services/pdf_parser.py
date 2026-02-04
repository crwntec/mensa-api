"""
mealplan_parser.py

PDF parser for meal plans.

Provides functions to extract weekly meals from a PDF and return a structured JSON-like dictionary.

Usage:
    from mealplan_parser import extract_meals

    meals = extract_meals("Speisenplan_KW_xx.pdf")
"""

import re
from typing import Dict, List
from datetime import datetime
import pdfplumber

from models import DayMeals, Mealplan


def extract_meals(pdf_path: str) -> Mealplan:
    """
    Extracts meals from a meal plan PDF using pdfplumber.
    
    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        Mealplan: Parsed meal plan data.
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Extract week number (ISO week)
            week_match = re.search(r"KW\s*(\d+)", text)
            if not week_match:
                continue
            week = int(week_match.group(1))

            # Extract first date to determine year
            date_match = re.search(r"\d{2}\.\d{2}\.\d{2,4}", text)
            if date_match:
                parsed_date = datetime.strptime(date_match.group(), "%d.%m.%y")
                year = parsed_date.year
            else:
                year = datetime.now().year

            for table in page.extract_tables() or []:
                days = parse_table(table)
                if days:
                    return Mealplan(
                        year=year,
                        week=week,
                        days=days
                    )

    return {}



def parse_table(table: List[List[str]]) -> Dict[str, DayMeals]:
    """
    Parse a table structure to extract meal information.
    
    Args:
        table (List[List[str]]): Table data as extracted by pdfplumber.
    Returns:
        Dict[str, DayMeals]: ISO-date → day data
    """
    if not table or len(table) < 2:
        return {}
    
    # Identify header row with days
    header_row = None
    for i, row in enumerate(table):
        if row and any(day in str(cell) for day in ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag'] for cell in row if cell):
            header_row = i
            break
    
    if header_row is None:
        return {}
    
    # Extract days
    days = []
    for cell in table[header_row]:
        if not cell:
            continue
        cell = cell.replace("\n", " ")
        day_match = re.search(r"(Montag|Dienstag|Mittwoch|Donnerstag|Freitag)", cell)
        date_match = re.search(r"(\d{2}\.\d{2}\.\d{2,4})", cell)
        if day_match and date_match:
            date_iso = datetime.strptime(date_match.group(1), "%d.%m.%y").date().isoformat()
            days.append({
                "date": date_iso,
                "weekday": day_match.group(1)
            })
    
    if not days:
        return {}
    
    # Initialize result dict
    result = {d["date"]: {"weekday": d["weekday"], "meals": {}} for d in days}
    
    current_meals = {i: [] for i in range(len(days))}
    category = None
    
    for i in range(header_row + 1, len(table)):
        row = table[i]
        if not row:
            continue
        
        first_cell = str(row[0]).strip() if row[0] else ""
        
        # Check for meal category
        if any(cat in first_cell for cat in ['Tagesgericht', 'Vegetarisch', 'Pizza & Pasta']):
            category = next((cat for cat in ['Tagesgericht', 'Vegetarisch', 'Pizza & Pasta'] if cat in first_cell), None)
            current_meals = {i: [] for i in range(len(days))}
        
        if category:
            for idx, cell in enumerate(row[1:], start=0):
                if cell and idx < len(days):
                    meal_text = str(cell).strip()
                    current_meals[idx].append(meal_text)
            
            # After processing all rows for this category, join meals into single string
            for idx in range(len(days)):
                if current_meals[idx]:
                    # Join multiple meal parts with a space or newline
                    combined_meal = " ".join(current_meals[idx])
                    result[days[idx]["date"]]["meals"][category] = combined_meal
            
            category = None
    
    return result