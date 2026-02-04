from datetime import datetime
import sqlite3
from models import Mealplan

init_db_query = """
CREATE TABLE IF NOT EXISTS mealplan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    week INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS meal(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS day(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mealplan_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    weekday TEXT NOT NULL,
    tagesgericht_id INTEGER,
    vegetarisch_id INTEGER,
    pizza_pasta_id INTEGER,
    FOREIGN KEY (mealplan_id) REFERENCES mealplan(id),
    FOREIGN KEY (tagesgericht_id) REFERENCES meal(id),
    FOREIGN KEY (vegetarisch_id) REFERENCES meal(id),
    FOREIGN KEY (pizza_pasta_id) REFERENCES meal(id)
);
"""

def connect_db():
    conn = sqlite3.connect('mealplan.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect_db() as conn:
        print(f"{datetime.now()} Creating database")
        cursor = conn.cursor()
        cursor.executescript(init_db_query)
        conn.commit()

def create_mealplan(data: Mealplan):
    with connect_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO mealplan (year, week) VALUES (?, ?)", 
                (data.year, data.week)
            )
            mealplan_id = cursor.lastrowid
            
            for date_iso, day_data in data.days.items():
                # Initialize meal IDs as None
                meal_ids = {
                    "Tagesgericht": None,
                    "Vegetarisch": None,
                    "Pizza & Pasta": None
                }
                
                # Get or create meal IDs for each category
                for category, meal_text in day_data["meals"].items():
                    cursor.execute(
                        "INSERT OR IGNORE INTO meal (name) VALUES (?)", 
                        (meal_text,)
                    )
                    cursor.execute(
                        "SELECT id FROM meal WHERE name = ?", 
                        (meal_text,)
                    )
                    meal_ids[category] = cursor.fetchone()[0]
                
                # Insert day with all meal IDs
                cursor.execute("""
                    INSERT INTO day (mealplan_id, date, weekday, 
                                     tagesgericht_id, vegetarisch_id, pizza_pasta_id) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    mealplan_id, 
                    date_iso, 
                    day_data["weekday"],
                    meal_ids.get("Tagesgericht"),
                    meal_ids.get("Vegetarisch"),
                    meal_ids.get("Pizza & Pasta")
                ))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to create mealplan: {e}")

def fetch_mealplan(year, week):
    with connect_db() as conn:
        cursor = conn.cursor()
        
        # Get mealplan
        cursor.execute("SELECT * FROM mealplan WHERE year = ? AND week = ?", (year, week))
        mealplan_row = cursor.fetchone()
        
        if not mealplan_row:
            return None
        
        # Get days with meals using JOINs
        cursor.execute("""
            SELECT 
                day.date, 
                day.weekday,
                m1.name as tagesgericht,
                m2.name as vegetarisch,
                m3.name as pizza_pasta
            FROM day
            LEFT JOIN meal m1 ON day.tagesgericht_id = m1.id
            LEFT JOIN meal m2 ON day.vegetarisch_id = m2.id
            LEFT JOIN meal m3 ON day.pizza_pasta_id = m3.id
            WHERE day.mealplan_id = ?
            ORDER BY day.date
        """, (mealplan_row["id"],))
        
        days_rows = cursor.fetchall()
        
        # Build the Mealplan object
        days = {}
        for row in days_rows:
            days[row["date"]] = {
                "weekday": row["weekday"],
                "meals": {
                    "Tagesgericht": row["tagesgericht"],
                    "Vegetarisch": row["vegetarisch"],
                    "Pizza & Pasta": row["pizza_pasta"]
                }
            }
        
        return Mealplan(
            year=mealplan_row["year"],
            week=mealplan_row["week"],
            days=days
        )