"""
Medical Medical Conditions Scraper

A command-line tool for scraping medical condition data from the Medical website.
This refactored version organizes the scraper into a modular package structure.
"""

import argparse
import sys
import re
from pathlib import Path

from jobs.scraper import (
    scrape_condition,
    scrape_all_conditions,
    validate_condition_slug,
    list_available_conditions
)

def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape medical conditions data from Medical website"
    )
    
    parser.add_argument(
        "--condition",
        type=str,
        help="Scrape specific condition by slug (e.g., 'allergies', 'acid-reflux-gerd', 'ear-pain')"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scrape all available conditions (default behavior)"
    )
    parser.add_argument(
        "--list-conditions",
        action="store_true",
        help="List all available conditions that can be scraped"
    )
    
    # Output options
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path("scraped"),
        help="Output directory for scraped JSON files (default: scraped)"
    )
    
    # Persistence options
    parser.add_argument(
        "--database",
        action="store_true",
        help="Store data in PostgreSQL database instead of JSON files"
    )
    
    # Scraping options
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    
    args = parser.parse_args()
    
    # Handle list conditions request
    if args.list_conditions:
        conditions = list_available_conditions()
        if conditions:
            print("\n📋 Available conditions:")
            for condition in sorted(conditions):
                print(f"  - {condition}")
        return
    
    # Ensure output directory exists (only if not using database)
    if not args.database:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = str(args.output_dir)
    
    if args.condition:
        # Validate and clean the condition slug
        condition_slug = args.condition.strip().lower()
        
        # Basic validation - ensure it's not empty and contains valid characters
        if not condition_slug:
            print("❌ Error: Condition slug cannot be empty")
            sys.exit(1)
        
        # Check for invalid characters (only allow alphanumeric, hyphens, and underscores)
        if not re.match(r'^[a-zA-Z0-9_-]+$', condition_slug):
            print(f"❌ Error: Invalid condition slug '{condition_slug}'. Only alphanumeric characters, hyphens, and underscores are allowed.")
            print("💡 Tip: Use --list-conditions to see available condition names")
            sys.exit(1)
        
        # Validate that the condition exists
        if not validate_condition_slug(condition_slug):
            print(f"❌ Condition '{condition_slug}' is not available for scraping")
            sys.exit(1)
        
        print(f"🔎 Scraping condition: {condition_slug}")
        result = scrape_condition(condition_slug, output_dir, args.database)
        if result:
            print(f"✅ Successfully scraped condition: {condition_slug}")
        else:
            print(f"❌ Failed to scrape condition: {condition_slug}")
            print("💡 Tip: Use --list-conditions to verify the condition name is correct")
            sys.exit(1)
    else:
        # --all, or no target at all (default behavior)
        print("🔎 Scraping all conditions...")
        failed = scrape_all_conditions(output_dir, args.delay, args.database)
        if failed is None or failed:
            sys.exit(1)


if __name__ == "__main__":
    main()