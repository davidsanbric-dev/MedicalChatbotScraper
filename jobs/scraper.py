"""Core scraping functionality for medical conditions from Medical website."""

import requests
from bs4 import BeautifulSoup
import os
import json
import time
import re
from .parser import extract_nested_list
from .persistence import DatabasePersistence

# Configuration constants
BASE_URL = "https://patients.amwell.com"
CONDITIONS_URL = f"{BASE_URL}/conditions/"


def scrape_condition(slug, output_dir="scraped", use_database=False, db_persistence=None):
    """Scrape a specific medical condition from Medical website."""
    url = f"{CONDITIONS_URL}{slug}"
    print(f"🌐 Accessing: {url}")
    
    # Initialize database persistence if requested
    # db_persistence may be provided by the caller to allow connection reuse.
    # If not provided and use_database is True, the function will create
    # its own DatabasePersistence and will be responsible for disconnecting it.
    local_db_owner = False
    if use_database and db_persistence is None:
        db_persistence = DatabasePersistence()
        local_db_owner = True
        if not db_persistence.connect():
            print("⚠️ Database connection failed, falling back to file storage")
            use_database = False
    # If we have a db_persistence, check whether the condition already exists.
    if use_database and db_persistence:
        try:
            if db_persistence.check_existing_condition(slug):
                print(f"ℹ️ Condition '{slug}' already exists in database, skipping...")
                # Only disconnect if we created/own the connection
                if local_db_owner:
                    db_persistence.disconnect()
                return {"status": "skipped", "reason": "already_exists"}
        except Exception:
            # If the provided persistence instance isn't connected or fails,
            # fall back to file storage rather than crashing.
            print("⚠️ Error checking existing condition; falling back to file storage")
            use_database = False
    
    try:
        res = requests.get(url, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error accessing {url}: {e}")
        return None
    
    if res.status_code != 200:
        print(f"❌ HTTP {res.status_code} error accessing {url}")
        if res.status_code == 404:
            print("💡 This condition may not exist. Use --list-conditions to see available conditions.")
        return None

    try:
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"❌ Error parsing HTML content: {e}")
        return None

    # Main title
    title = soup.select_one("h1")
    title = title.get_text(strip=True) if title else slug.replace("-", " ").title()

    # Extract symptoms from the specific structure
    symptoms = {}
    symptoms_card = soup.find("div", class_="contact-us-card")
    if symptoms_card:
        # h3 in the original template, h2 since the 2026 redesign
        heading = symptoms_card.find(["h2", "h3"], class_="contact-us-card__heading")
        heading_text = heading.get_text(strip=True) if heading else ""
        ul = symptoms_card.find("ul")
        if ul:
            symptoms_list = [li.get_text(strip=True) for li in ul.find_all("li") if li.get_text(strip=True) != "And more."]
            symptoms = {
                "heading": heading_text,
                "list": symptoms_list
            }

    # Extract content from "Diagnosing and Treating Online"
    online_diagnosing_treating = {}
    # A <section class="rtf"> in the original template; since the 2026 redesign
    # it is the page-body <div class="rtf rtf--with-margin"> (its <h2> is optional).
    rtf_section = soup.select_one("section.rtf, .rtf.rtf--with-margin")
    if rtf_section:
        heading = rtf_section.find("h2")
        heading_text = heading.get_text(strip=True) if heading else ""
        
        # Extract all HTML content preserving structure
        content_elements = []
        
        # Buffer for consecutive lists to merge
        buffered_lists = []
        
        def flush_buffered_lists():
            """Merge all buffered lists into a single list element"""
            nonlocal buffered_lists, content_elements
            if buffered_lists:
                # Merge all list items from consecutive lists
                merged_items = []
                for list_items in buffered_lists:
                    merged_items.extend(list_items)
                # Use 'ul' as the default type for merged lists
                content_elements.append({"type": "ul", "items": merged_items})
                buffered_lists = []
        
        # Find all direct child elements of the RTF section
        for element in rtf_section.find_all(recursive=False):
            if element.name in ['p', 'ul', 'ol']:
                if element.name in ['ul', 'ol']:
                    # Buffer this list for potential merging with consecutive lists
                    list_items = extract_nested_list(element)
                    buffered_lists.append(list_items)
                else:
                    # For paragraphs, check if it's empty
                    text = element.get_text(' ', strip=True)
                    if text:
                        # Flush any buffered lists before adding the paragraph
                        flush_buffered_lists()
                        # Check if paragraph contains strong or bold tags
                        paragraph_type = "strong_paragraph" if element.find(['strong', 'b']) else "paragraph"
                        content_elements.append({"type": paragraph_type, "text": text})
                    # If empty paragraph, skip it (don't flush buffered lists yet)
            elif element.name in ['div', 'section'] and not element.get('class'):
                # Also check for nested content in plain div/section elements
                for sub_element in element.find_all(['p', 'ul', 'ol'], recursive=False):
                    if sub_element.name in ['ul', 'ol']:
                        list_items = extract_nested_list(sub_element)
                        buffered_lists.append(list_items)
                    else:
                        text = sub_element.get_text(' ', strip=True)
                        if text:
                            # Flush any buffered lists before adding the paragraph
                            flush_buffered_lists()
                            # Check if paragraph contains strong or bold tags
                            paragraph_type = "strong_paragraph" if sub_element.find(['strong', 'b']) else "paragraph"
                            content_elements.append({"type": paragraph_type, "text": text})
                        # If empty paragraph, skip it
        
        # Flush any remaining buffered lists at the end
        flush_buffered_lists()
        
        online_diagnosing_treating = {
            "heading": heading_text,
            "content": content_elements
        }

    # Extract relevant sections
    sections = []
    for section_count, section in enumerate(soup.select("section, div.section"), 1):
        heading = section.find(["h2", "h3"])
        heading_text = heading.get_text(strip=True) if heading else "General"

        # Skip the untitled lead sections (page header boilerplate)
        if section_count <= 2 and heading_text == "General":
            continue

        # Skip sections that contain the symptoms card
        if section.find("div", class_="contact-us-card"):
            continue

        # Skip the section holding the RTF block (already processed)
        if rtf_section and (section is rtf_section or section in rtf_section.parents):
            continue

        # Capture paragraphs
        paragraphs = [p.get_text(" ", strip=True) for p in section.find_all("p")]
        content = "\n".join(paragraphs).strip()

        if content:
            sections.append({
                "heading": heading_text,
                "content": content
            })

    # Assemble JSON. Text is stored as found on the page (non-breaking spaces
    # included); the worker normalizes it, so raw_data stays a faithful copy.
    data = {
        "title": title,
        "url": url,
        "symptoms": symptoms,
        "onlineDiagnosingAndTreating": online_diagnosing_treating,
        "sections": sections,
    }

    # Save data (database or JSON file)
    try:
        if use_database and db_persistence:
            # Save to database
            record_id = db_persistence.save_condition_data(slug, data)
            # Only disconnect if this function created the connection
            if local_db_owner:
                db_persistence.disconnect()
            if record_id:
                print(f"✅ Saved to database with ID: {record_id}")
                return data
            else:
                print("❌ Database save failed, falling back to file storage")
                use_database = False
        
        if not use_database:
            # Save to JSON file (fallback or default)
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{slug}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Saved to file: {file_path}")
        
        return data
        
    except Exception as e:
        print(f"❌ Error saving data for {slug}: {e}")
        if local_db_owner and db_persistence:
            db_persistence.disconnect()
        return None


def scrape_all_conditions(output_dir="scraped", delay=0, use_database=False):
    """Scrape all available conditions from Medical website."""
    print("🔎 Searching for all conditions from the sitemap...")
    
    # Initialize database connection if using database
    db_persistence = None
    # When scraping all conditions, create a single DatabasePersistence and
    # connect once to reuse the DB session across all scrapes. Ownership: this
    # function is responsible for disconnecting the instance it creates.
    if use_database:
        db_persistence = DatabasePersistence()
        if db_persistence.connect():
            existing_count = db_persistence.get_condition_count()
            print(f"ℹ️ Found {existing_count} existing conditions in database")
        else:
            print("⚠️ Database connection failed, falling back to file storage")
            use_database = False
    
    # Get all condition URLs from the sitemap
    sitemap_url = f"{BASE_URL}/sitemap.xml"
    res = requests.get(sitemap_url, timeout=30)
    
    if res.status_code != 200:
        print(f"❌ Error {res.status_code} accessing sitemap. Trying alternative method...")
        # Fallback to original method if sitemap doesn't work
        res = requests.get(CONDITIONS_URL, timeout=30)
        if res.status_code != 200:
            print("❌ Could not access the conditions index.")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        links = soup.select("a")
        slugs = set()
        for link in links:
            href = link.get("href", "")
            if href.startswith("/conditions/") and href != "/conditions/":
                slug = href.split("/conditions/")[-1].strip("/")
                slugs.add(slug)
    else:
        # Extract condition URLs from sitemap using regex
        condition_urls = re.findall(r'<loc>(https://patients\.amwell\.com/conditions/[^<]+)</loc>', res.text)
        
        # Extract slugs from the URLs
        slugs = set()
        for url in condition_urls:
            if "/conditions/" in url:
                slug = url.split("/conditions/")[-1].strip("/")
                if slug:  # Ensure it's not empty
                    slugs.add(slug)
        
        print(f"✅ Found {len(condition_urls)} URLs in the sitemap")

    print(f"🔎 Total conditions to process: {len(slugs)}")

    # Scraping of each condition. There is no automatic retry: a failed page is
    # reported at the end and left for the next run.
    failed = []
    for i, slug in enumerate(sorted(slugs), 1):
        print(f"📝 Processing condition {i}/{len(slugs)}: {slug}")
        # Pass the shared db_persistence so scrape_condition doesn't reconnect
        if scrape_condition(slug, output_dir, use_database, db_persistence=db_persistence) is None:
            failed.append(slug)
        time.sleep(delay)  # avoid overloading the server

    # Close database connection if this function created it
    if db_persistence:
        db_persistence.disconnect()

    if failed:
        print(f"⚠️ {len(failed)} of {len(slugs)} conditions failed: {', '.join(failed)}")
        if use_database:
            print("💡 Re-run to fill the gaps: conditions already in the database are skipped")
        else:
            print("💡 Retry each with --condition <slug>, or re-run --all (JSON files are rewritten)")
    else:
        print(f"✅ All {len(slugs)} conditions processed")
    return failed


def validate_condition_slug(slug):
    """Validate if a condition slug exists on Medical website."""
    print(f"🔍 Validating condition: {slug}")
    
    # First check our cached list of conditions
    try:
        available_conditions = list_available_conditions()
        if slug in available_conditions:
            print(f"✅ Condition '{slug}' found in available conditions")
            return True
        else:
            print(f"⚠️  Condition '{slug}' not found in available conditions list")
            print("💡 Tip: Use --list-conditions to see all available conditions")
            return False
    except Exception as e:
        print(f"⚠️  Could not validate condition locally: {e}")
        print("   Proceeding with scrape attempt...")
        return True  # Allow the attempt if we can't validate locally


def list_available_conditions():
    """List all available conditions that can be scraped."""
    print("🔎 Checking available conditions from Medical sitemap...")
    
    # Try to get conditions from sitemap
    sitemap_url = f"{BASE_URL}/sitemap.xml"
    res = requests.get(sitemap_url, timeout=30)
    
    if res.status_code != 200:
        print(f"❌ Error {res.status_code} accessing sitemap. Trying fallback method...")
        # Fallback to main conditions page
        res = requests.get(CONDITIONS_URL, timeout=30)
        if res.status_code != 200:
            print("❌ Could not access conditions index.")
            return set()
        
        soup = BeautifulSoup(res.text, "html.parser")
        links = soup.select("a")
        slugs = set()
        for link in links:
            href = link.get("href", "")
            if href.startswith("/conditions/") and href != "/conditions/":
                slug = href.split("/conditions/")[-1].strip("/")
                slugs.add(slug)
    else:
        # Extract condition URLs from sitemap
        condition_urls = re.findall(r'<loc>(https://patients\.amwell\.com/conditions/[^<]+)</loc>', res.text)
        
        # Extract slugs from URLs
        slugs = set()
        for url in condition_urls:
            if "/conditions/" in url:
                slug = url.split("/conditions/")[-1].strip("/")
                if slug:
                    slugs.add(slug)
    
    print(f"✅ Found {len(slugs)} available conditions")
    return slugs