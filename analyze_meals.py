#!/usr/bin/env python3
"""
Meal Database Analysis Script

Analyzes the meal database to understand duplicate patterns before deduplication.
"""

import sqlite3
import re
from collections import Counter, defaultdict
import sys


def normalize_simple(name):
    """Simple normalization for pattern analysis"""
    name = name.lower()
    # Remove allergen codes more carefully
    # Pattern: single letter optionally followed by digit, as standalone words
    name = re.sub(r'\s*\b[a-z]\d?\b(?=[,\s]|$)', '', name)
    # Clean up commas and extra spaces
    name = re.sub(r'[,\s]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def analyze_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("="*80)
    print("MEAL DATABASE ANALYSIS")
    print("="*80)
    
    # Basic statistics
    cursor.execute("SELECT COUNT(*) FROM meal")
    total_meals = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM day")
    total_days = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM mealplan")
    total_plans = cursor.fetchone()[0]
    
    print(f"\nBasic Statistics:")
    print(f"  Total unique meals: {total_meals}")
    print(f"  Total days: {total_days}")
    print(f"  Total meal plans: {total_plans}")
    
    # Get all meal names
    cursor.execute("SELECT name FROM meal")
    all_meals = [row[0] for row in cursor.fetchall()]
    
    # Analyze patterns
    print("\n" + "="*80)
    print("PATTERN ANALYSIS")
    print("="*80)
    
    # 1. Allergen code patterns
    print("\n1. Allergen Code Patterns:")
    with_allergens = sum(1 for m in all_meals if re.search(r'[a-z]\d*', m))
    without_allergens = total_meals - with_allergens
    print(f"  Meals with allergen codes: {with_allergens} ({100*with_allergens/total_meals:.1f}%)")
    print(f"  Meals without allergen codes: {without_allergens} ({100*without_allergens/total_meals:.1f}%)")
    
    # 2. Common words
    print("\n2. Most Common Words in Meal Names:")
    word_freq = Counter()
    for meal in all_meals:
        words = meal.lower().split()
        word_freq.update(words)
    
    print("  Top 20 words:")
    for word, count in word_freq.most_common(20):
        print(f"    {word:20s}: {count:4d}")
    
    # 3. Length distribution
    print("\n3. Meal Name Length Distribution:")
    lengths = [len(m) for m in all_meals]
    print(f"  Shortest: {min(lengths)} chars")
    print(f"  Longest: {max(lengths)} chars")
    print(f"  Average: {sum(lengths)/len(lengths):.1f} chars")
    print(f"  Median: {sorted(lengths)[len(lengths)//2]} chars")
    
    # 4. Potential duplicates (simple check)
    print("\n4. Potential Duplicate Patterns:")
    normalized_groups = defaultdict(list)
    for meal in all_meals:
        norm = normalize_simple(meal)
        normalized_groups[norm].append(meal)
    
    duplicates = {k: v for k, v in normalized_groups.items() if len(v) > 1}
    print(f"  Groups with potential duplicates: {len(duplicates)}")
    print(f"  Total meals involved: {sum(len(v) for v in duplicates.values())}")
    print(f"  Average group size: {sum(len(v) for v in duplicates.values())/len(duplicates):.1f}")
    
    # Show some examples
    print("\n  Example duplicate groups (showing first 10):")
    for i, (norm, meals) in enumerate(list(duplicates.items())[:10], 1):
        print(f"\n  {i}. Normalized: {norm}")
        print(f"     Variations ({len(meals)}):")
        for meal in meals[:5]:  # Show max 5 per group
            print(f"       - {meal}")
        if len(meals) > 5:
            print(f"       ... and {len(meals)-5} more")
    
    # 5. Special cases
    print("\n5. Special Cases:")
    
    special_keywords = {
        'Feiertag': 0,
        'geschlossen': 0,
        'Mensa': 0,
        'Kiosk': 0,
        'Weihnachten': 0,
        'Ferien': 0,
    }
    
    for meal in all_meals:
        for keyword in special_keywords:
            if keyword.lower() in meal.lower():
                special_keywords[keyword] += 1
    
    print("  Non-meal entries (holidays, closures, etc.):")
    for keyword, count in special_keywords.items():
        if count > 0:
            print(f"    {keyword}: {count}")
    
    # 6. Protein types
    print("\n6. Protein Type Distribution:")
    protein_keywords = {
        'Hähnchen': 0,
        'Geflügel': 0,
        'Rind': 0,
        'Schwein': 0,
        'Fisch': 0,
        'Vegetarisch': 0,
        'Vegan': 0,
    }
    
    for meal in all_meals:
        meal_lower = meal.lower()
        for keyword in protein_keywords:
            if keyword.lower() in meal_lower:
                protein_keywords[keyword] += 1
    
    for protein, count in sorted(protein_keywords.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {protein:20s}: {count:4d}")
    
    # 7. Side dish patterns
    print("\n7. Common Side Dishes:")
    sides = {
        'Reis': 0,
        'Kartoffeln': 0,
        'Pommes': 0,
        'Nudeln': 0,
        'Spätzle': 0,
        'Püree': 0,
        'Salzkartoffeln': 0,
    }
    
    for meal in all_meals:
        meal_lower = meal.lower()
        for side in sides:
            if side.lower() in meal_lower:
                sides[side] += 1
    
    for side, count in sorted(sides.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {side:20s}: {count:4d}")
    
    # 8. Most frequently served meals
    print("\n8. Most Frequently Served Meals (Top 15):")
    cursor.execute("""
        SELECT m.name, COUNT(*) as appearances
        FROM meal m
        LEFT JOIN day d ON (d.tagesgericht_id = m.id 
                           OR d.vegetarisch_id = m.id 
                           OR d.pizza_pasta_id = m.id 
                           OR d.wok_id = m.id)
        GROUP BY m.name
        HAVING appearances > 0
        ORDER BY appearances DESC
        LIMIT 15
    """)
    
    for i, (name, count) in enumerate(cursor.fetchall(), 1):
        print(f"  {i:2d}. {name[:60]:60s} ({count} times)")
    
    # 9. Orphaned meals
    cursor.execute("""
        SELECT COUNT(*)
        FROM meal m
        WHERE m.id NOT IN (
            SELECT DISTINCT tagesgericht_id FROM day WHERE tagesgericht_id IS NOT NULL
            UNION
            SELECT DISTINCT vegetarisch_id FROM day WHERE vegetarisch_id IS NOT NULL
            UNION
            SELECT DISTINCT pizza_pasta_id FROM day WHERE pizza_pasta_id IS NOT NULL
            UNION
            SELECT DISTINCT wok_id FROM day WHERE wok_id IS NOT NULL
        )
    """)
    orphaned = cursor.fetchone()[0]
    print(f"\n9. Orphaned Meals (never served): {orphaned}")
    
    # 10. Meal category distribution
    print("\n10. Meal Category Usage:")
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN tagesgericht_id IS NOT NULL THEN 1 ELSE 0 END) as tagesgericht,
            SUM(CASE WHEN vegetarisch_id IS NOT NULL THEN 1 ELSE 0 END) as vegetarisch,
            SUM(CASE WHEN pizza_pasta_id IS NOT NULL THEN 1 ELSE 0 END) as pizza_pasta,
            SUM(CASE WHEN wok_id IS NOT NULL THEN 1 ELSE 0 END) as wok
        FROM day
    """)
    tg, veg, pp, wok = cursor.fetchone()
    print(f"  Tagesgericht (daily special): {tg}")
    print(f"  Vegetarisch: {veg}")
    print(f"  Pizza/Pasta: {pp}")
    print(f"  Wok: {wok}")
    
    conn.close()
    
    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)
    print("\nNext steps:")
    print("  1. Review the duplicate patterns above")
    print("  2. Run: python deduplicate_meals.py your_database.db")
    print("     (This will show a preview without making changes)")
    print("  3. If satisfied, run with --apply flag to deduplicate")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_meals.py <database_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    analyze_database(db_path)