#!/usr/bin/env python3
"""
Enhanced Meal Database Deduplication Script

Improvements over v1:
- Better handling of incomplete descriptions (e.g., missing "dazu Reis")
- Fuzzy matching on main dish names
- Special handling for Wok dishes
"""

import sqlite3
import re
from collections import defaultdict
from difflib import SequenceMatcher
import sys


class EnhancedMealDeduplicator:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
    def normalize_meal_name(self, name):
        """
        Normalize a meal name for comparison by removing noise.
        Returns (normalized_name, allergen_codes, clean_name_without_allergens)
        """
        if not name:
            return "", [], ""
        
        # Extract allergen/additive codes
        letter_codes = re.findall(r'(?:^|[,\s])([a-z]\d?)(?=[,\s]|$)', name)
        number_codes = re.findall(r'(?:^|[,\s])(\d)(?=[,\s]|$)', name)
        all_codes = letter_codes + number_codes
        
        # Remove both types of codes
        name_no_codes = name
        name_no_codes = re.sub(r'(?:^|[,\s])([a-z]\d?)(?=[,\s]|$)', ' ', name_no_codes)
        name_no_codes = re.sub(r'(?:^|[,\s])(\d)(?=[,\s]|$)', ' ', name_no_codes)
        
        # Remove parentheses (often used for allergen codes)
        name_no_codes = re.sub(r'\([^)]*\)', ' ', name_no_codes)
        
        # Clean up the result
        name_no_codes = re.sub(r'\s*,\s*', ' ', name_no_codes)  # Replace commas with spaces
        name_no_codes = re.sub(r'\s*&\s*', ' ', name_no_codes)  # Normalize & to space
        name_no_codes = re.sub(r'\s+', ' ', name_no_codes).strip()  # Normalize spaces
        
        # Clean the name without codes (for canonical output)
        clean_name = name_no_codes
        clean_name = re.sub(r'\s*-\s*', ' ', clean_name)  # Normalize dashes to spaces
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        clean_name = re.sub(r'^[\s,\-]+|[\s,\-]+$', '', clean_name)
        
        # Create normalized version for comparison
        name_normalized = clean_name.lower()
        
        # Normalize German special characters for comparison only
        replacements = {
            'ä': 'ae',
            'ö': 'oe',
            'ü': 'ue',
            'ß': 'ss',
        }
        
        for old, new in replacements.items():
            name_normalized = name_normalized.replace(old, new)
        
        # Remove extra spaces again
        name_normalized = re.sub(r'\s+', ' ', name_normalized).strip()
        
        # Store allergen/additive codes
        allergen_codes = sorted(set(all_codes))
        
        return name_normalized, allergen_codes, clean_name
    
    def extract_dish_name(self, name):
        """
        Extract just the main dish name (before ingredients/sides).
        Examples:
        - "Wok Jakarta Gemüsemischung..." -> "Wok Jakarta"
        - "Power & Sweet Wok mit Geflügel..." -> "Power & Sweet Wok"
        """
        # Normalize first
        norm, codes, clean = self.normalize_meal_name(name)
        
        # For Wok dishes, extract "Wok [Name]" pattern
        if 'wok' in clean.lower():
            # Pattern: "Wok Name" or "Name Wok"
            words = clean.split()
            wok_idx = -1
            
            # Find where "Wok" appears
            for i, word in enumerate(words):
                if word.lower() == 'wok':
                    wok_idx = i
                    break
            
            if wok_idx >= 0:
                # If "Wok" is first word: "Wok Jakarta", "Wok Bangkok"
                if wok_idx == 0 and len(words) > 1:
                    # Take "Wok" + next word (the location/name)
                    return ' '.join(words[:2])
                # If "Wok" comes after: "Power & Sweet Wok", "Curry Wok"
                elif wok_idx > 0:
                    # Take everything up to and including "Wok"
                    return ' '.join(words[:wok_idx+1])
        
        # For non-Wok dishes, use common separators
        words = clean.split()
        if len(words) <= 3:
            return clean
        
        # Find the first separator
        for i, word in enumerate(words):
            if word.lower() in ['mit', 'dazu', 'in', 'an']:
                if i > 0:
                    return ' '.join(words[:i])
        
        # Default: first 3 words
        return ' '.join(words[:min(3, len(words))])
    
    def similarity_score(self, s1, s2):
        """Calculate similarity between two strings (0-1)"""
        return SequenceMatcher(None, s1, s2).ratio()
    
    def extract_main_components(self, name):
        """
        Extract the main dish component from a meal name.
        Returns the core dish without sides.
        """
        separators = [
            'dazu', 'mit', 'und', ',', 'an', 'in', 'auf'
        ]
        
        name_lower = name.lower()
        
        # Find the first separator
        first_sep_pos = len(name)
        for sep in separators:
            pos = name_lower.find(sep)
            if pos > 0 and pos < first_sep_pos:
                first_sep_pos = pos
        
        # Return the main component
        main = name[:first_sep_pos].strip()
        sides = name[first_sep_pos:].strip() if first_sep_pos < len(name) else ""
        
        return main, sides
    
    def are_duplicates(self, name1, name2, threshold=0.88):
        """
        Determine if two meal names are duplicates.
        Enhanced with dish name matching and protein detection.
        """
        # Normalize both names
        norm1, allergens1, clean1 = self.normalize_meal_name(name1)
        norm2, allergens2, clean2 = self.normalize_meal_name(name2)
        
        # Check for different proteins (these should NOT be merged)
        protein_keywords = [
            ('rind', 'rindfleisch', 'beef'),
            ('schwein', 'schweinefleisch', 'pork'),
            ('hähnchen', 'huhn', 'hühnchen', 'geflügel', 'pute', 'chicken', 'poultry'),
            ('lamm', 'lammfleisch', 'lamb'),
            ('fisch', 'fish', 'lachs', 'seelachs', 'thunfisch'),
        ]
        
        def get_protein_type(text):
            """Determine protein type from text"""
            text_lower = text.lower()
            for i, group in enumerate(protein_keywords):
                if any(keyword in text_lower for keyword in group):
                    return i
            return None
        
        protein1 = get_protein_type(norm1)
        protein2 = get_protein_type(norm2)
        
        # If both have proteins specified and they're different, NOT duplicates
        if protein1 is not None and protein2 is not None and protein1 != protein2:
            return False
        
        # Exact match after normalization
        if norm1 == norm2:
            return True
        
        # Very high similarity (exact duplicates with minor variations)
        if self.similarity_score(norm1, norm2) >= 0.95:
            return True
        
        # Check dish names
        dish1 = self.extract_dish_name(name1).lower()
        dish2 = self.extract_dish_name(name2).lower()
        
        # Normalize dish names for comparison
        dish1_norm = dish1
        dish2_norm = dish2
        for old, new in {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'}.items():
            dish1_norm = dish1_norm.replace(old, new)
            dish2_norm = dish2_norm.replace(old, new)
        
        # If dish names are very similar or identical, likely duplicates
        if dish1_norm == dish2_norm and len(dish1_norm) > 5:
            return True
        
        if self.similarity_score(dish1_norm, dish2_norm) >= 0.90 and len(dish1_norm) > 5:
            return True
        
        # Overall similarity check
        if self.similarity_score(norm1, norm2) >= threshold:
            return True
        
        # Check if main components match
        main1, sides1 = self.extract_main_components(norm1)
        main2, sides2 = self.extract_main_components(norm2)
        
        # If main dishes are very similar, likely duplicates
        if self.similarity_score(main1, main2) >= 0.92:
            return True
        
        return False
    
    def choose_canonical_name(self, names):
        """
        Choose the best canonical name from a group of duplicates.
        Returns the cleanest version WITHOUT allergen codes.
        """
        # Get clean versions of all names
        clean_versions = []
        for name in names:
            norm, allergens, clean = self.normalize_meal_name(name)
            clean_versions.append((clean, len(clean), norm, name))
        
        # Score each clean name
        scored = []
        for clean, length, norm, orig in clean_versions:
            score = 0
            
            # Prefer more complete descriptions
            score += len(clean.split()) * 2
            
            # Prefer names with "dazu" (indicates complete meal)
            if 'dazu' in clean.lower():
                score += 10
            if 'mit' in clean.lower():
                score += 5
            
            # Prefer medium length (not too short, not too verbose)
            ideal_length = 70
            score -= abs(length - ideal_length) * 0.05
            
            # Prefer names without formatting artifacts
            if '  ' not in clean:
                score += 2
            if clean.count('-') <= 2:
                score += 1
            
            # Prefer more detailed ingredient lists
            if any(word in clean for word in ['Gemüse', 'Reis', 'Kartoffeln', 'Sauce']):
                score += 3
            
            scored.append((score, -length, clean))  # Negative length for tiebreaker (prefer longer)
        
        # Sort by score (desc), then by length (prefer longer for completeness)
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        
        return scored[0][2]
    
    def find_duplicate_groups(self):
        """
        Find all groups of duplicate meals.
        Returns: dict mapping canonical_name -> list of duplicate names
        """
        # Get all unique meal names
        self.cursor.execute("SELECT DISTINCT name FROM meal ORDER BY name")
        all_meals = [row[0] for row in self.cursor.fetchall()]
        
        print(f"Total unique meal names in database: {len(all_meals)}")
        print("Finding duplicate groups...")
        
        # Group duplicates
        processed = set()
        duplicate_groups = []
        
        for i, meal1 in enumerate(all_meals):
            if meal1 in processed:
                continue
            
            # Start a new group
            group = [meal1]
            processed.add(meal1)
            
            # Find all duplicates of this meal
            for meal2 in all_meals[i+1:]:
                if meal2 in processed:
                    continue
                
                if self.are_duplicates(meal1, meal2):
                    group.append(meal2)
                    processed.add(meal2)
            
            if len(group) > 1:
                duplicate_groups.append(group)
            
            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"Processed {i + 1}/{len(all_meals)} meals...")
        
        print(f"\nFound {len(duplicate_groups)} duplicate groups")
        
        # Create canonical mapping
        canonical_mapping = {}
        for group in duplicate_groups:
            canonical = self.choose_canonical_name(group)
            for name in group:
                canonical_mapping[name] = canonical
        
        return canonical_mapping, duplicate_groups
    
    def preview_deduplication(self, limit=30):
        """Preview what will be deduplicated without making changes"""
        canonical_mapping, duplicate_groups = self.find_duplicate_groups()
        
        print("\n" + "="*80)
        print("DEDUPLICATION PREVIEW")
        print("="*80)
        print(f"\nTotal duplicate groups found: {len(duplicate_groups)}")
        print(f"Total meals that will be merged: {sum(len(g)-1 for g in duplicate_groups)}")
        
        print(f"\nShowing first {min(limit, len(duplicate_groups))} groups:\n")
        
        for i, group in enumerate(duplicate_groups[:limit], 1):
            canonical = self.choose_canonical_name(group)
            print(f"\n{i}. Canonical: {canonical}")
            print(f"   Duplicates ({len(group)-1}):")
            for name in group:
                if name != canonical:
                    marker = "  →" if name == group[0] else "   "
                    print(f"   {marker} {name}")
        
        if len(duplicate_groups) > limit:
            print(f"\n... and {len(duplicate_groups) - limit} more groups")
        
        return canonical_mapping, duplicate_groups
    
    def apply_deduplication(self, canonical_mapping, dry_run=True):
        """
        Apply the deduplication to the database.
        """
        if dry_run:
            print("\n" + "="*80)
            print("DRY RUN - No changes will be made")
            print("="*80)
        else:
            print("\n" + "="*80)
            print("APPLYING DEDUPLICATION")
            print("="*80)
            self.conn.execute("BEGIN TRANSACTION")
        
        updates_made = 0
        
        try:
            for old_name, canonical_name in canonical_mapping.items():
                if old_name == canonical_name:
                    continue
                
                # Get IDs
                self.cursor.execute("SELECT id FROM meal WHERE name = ?", (old_name,))
                old_result = self.cursor.fetchone()
                if not old_result:
                    continue
                old_id = old_result[0]
                
                self.cursor.execute("SELECT id FROM meal WHERE name = ?", (canonical_name,))
                canonical_result = self.cursor.fetchone()
                if not canonical_result:
                    # Rename the old one to canonical
                    if not dry_run:
                        self.cursor.execute("UPDATE meal SET name = ? WHERE id = ?", 
                                          (canonical_name, old_id))
                    print(f"Renamed: {old_name[:60]} -> {canonical_name[:60]}")
                    updates_made += 1
                else:
                    canonical_id = canonical_result[0]
                    
                    # Update all references in day table
                    for column in ['tagesgericht_id', 'vegetarisch_id', 'pizza_pasta_id', 'wok_id']:
                        if not dry_run:
                            self.cursor.execute(f"""
                                UPDATE day 
                                SET {column} = ? 
                                WHERE {column} = ?
                            """, (canonical_id, old_id))
                    
                    # Delete the duplicate meal
                    if not dry_run:
                        self.cursor.execute("DELETE FROM meal WHERE id = ?", (old_id,))
                    
                    print(f"Merged: {old_name[:60]} -> {canonical_name[:60]}")
                    updates_made += 1
            
            if not dry_run:
                self.conn.commit()
                print(f"\n✓ Successfully deduplicated {updates_made} meals")
            else:
                print(f"\nWould deduplicate {updates_made} meals")
                
        except Exception as e:
            if not dry_run:
                self.conn.rollback()
            print(f"\n✗ Error: {e}")
            raise
        
        return updates_made
    
    def get_statistics(self):
        """Get current database statistics"""
        self.cursor.execute("SELECT COUNT(*) FROM meal")
        meal_count = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM day")
        day_count = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM mealplan")
        mealplan_count = self.cursor.fetchone()[0]
        
        print("\n" + "="*80)
        print("DATABASE STATISTICS")
        print("="*80)
        print(f"Unique meals: {meal_count}")
        print(f"Total days: {day_count}")
        print(f"Meal plans: {mealplan_count}")
        
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python deduplicate_meals_enhanced.py <database_path> [--apply]")
        print("\nWithout --apply: Preview mode (shows what would be changed)")
        print("With --apply: Actually applies the deduplication")
        sys.exit(1)
    
    db_path = sys.argv[1]
    apply_changes = '--apply' in sys.argv
    
    print("Enhanced Meal Database Deduplication Tool")
    print("="*80)
    
    deduplicator = EnhancedMealDeduplicator(db_path)
    
    # Show initial statistics
    deduplicator.get_statistics()
    
    # Preview deduplication
    canonical_mapping, duplicate_groups = deduplicator.preview_deduplication(limit=30)
    
    if not canonical_mapping:
        print("\n✓ No duplicates found! Database is already clean.")
        deduplicator.close()
        return
    
    # Ask for confirmation if applying
    if apply_changes:
        print("\n" + "="*80)
        response = input("\nAre you sure you want to apply these changes? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            deduplicator.close()
            return
        
        # Apply changes
        deduplicator.apply_deduplication(canonical_mapping, dry_run=False)
        
        # Show final statistics
        deduplicator.get_statistics()
    else:
        print("\n" + "="*80)
        print("This was a preview only. No changes were made.")
        print("To apply these changes, run with --apply flag:")
        print(f"  python deduplicate_meals_enhanced.py {db_path} --apply")
    
    deduplicator.close()


if __name__ == "__main__":
    main()