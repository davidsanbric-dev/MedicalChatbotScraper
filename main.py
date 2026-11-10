"""Scraper CLI: station 1 of the medical chatbot pipeline.

Collects every condition page of patients.amwell.com into the shared
database (or into JSON files). How it works, visually:
https://medicalchatbot.demos.davieldev.com/scraper
"""

import argparse
import os
import re
import sys
from pathlib import Path

import requests
from sqlalchemy.exc import SQLAlchemyError

from jobs.persistence import DatabaseStore, JsonFileStore
from jobs.scraper import discover_condition_slugs, open_http_session, scrape

SLUG = re.compile(r"[a-z0-9_-]+")


def condition_slug(value: str) -> str:
    """argparse type for a page slug such as 'acne' or 'acid-reflux-gerd'."""
    slug = value.strip().lower()
    if not SLUG.fullmatch(slug):
        raise argparse.ArgumentTypeError(f"{value!r} is not a slug (letters, digits, '-' and '_' only)")
    return slug


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape the condition pages of patients.amwell.com.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--all", action="store_true", help="scrape every condition page (the default)")
    target.add_argument("--condition", type=condition_slug, metavar="SLUG", help="scrape one page, e.g. acne")
    target.add_argument("--list-conditions", action="store_true", help="list the pages that can be scraped")
    parser.add_argument("--database", action="store_true", help="save to the raw_data table instead of JSON files")
    parser.add_argument("--output-dir", "-o", type=Path, default=Path("scraped"), help="JSON folder (default: scraped)")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between two pages (default: 1.0)")
    args = parser.parse_args()
    if args.database and not os.getenv("DATABASE_URL"):
        parser.error("--database needs the DATABASE_URL environment variable")
    return args


def main() -> int:
    args = parse_args()
    with open_http_session() as http:
        try:
            slugs = sorted(discover_condition_slugs(http))
        except requests.RequestException as error:
            print(f"❌ Could not list the condition pages: {error}")
            return 1

        if args.list_conditions:
            print(f"📋 {len(slugs)} condition pages:", *(f"  - {slug}" for slug in slugs), sep="\n")
            return 0
        if args.condition:
            if args.condition not in slugs:
                print(f"❌ There is no condition page called '{args.condition}'. See --list-conditions.")
                return 1
            slugs = [args.condition]

        store = DatabaseStore() if args.database else JsonFileStore(args.output_dir)
        try:
            failed = scrape(http, slugs, store, args.delay)
        except SQLAlchemyError as error:
            print(f"❌ Database unavailable ({type(error).__name__}): check DATABASE_URL")
            return 1

    if not failed:
        print("✅ Done: every page is saved")
        return 0
    print(f"⚠️ {len(failed)} of {len(slugs)} pages failed: {', '.join(failed)}")
    if args.database:
        print("💡 Re-run to fill the gaps: pages already in the database are skipped")
    else:
        print("💡 Re-run, or retry one page with --condition <slug>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
