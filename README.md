# Medical Conditions Scraper

A lightweight web scraping tool to collect medical condition data from the Medical website.

## Purpose

This module is responsible for the **data collection** phase of the ETL pipeline, extracting structured medical condition information from Medical's patient portal.

## Project Structure

```
medical_conditions_scraper/
├── main.py                       # Main CLI interface and entry point
├── jobs/                         # Scraping jobs package
│   ├── __init__.py              # Jobs package initialization
│   ├── parser.py                # HTML parsing utilities
│   ├── scraper.py               # Core scraping functionality
│   └── persistence.py           # Database persistence layer (uses shared DB)
├── Dockerfile                   # Container configuration
├── requirements.txt             # Python dependencies
├── scraped/                     # Default output directory for JSON files
└── README.md                    # This file

# Shared database configuration (mounted from medical_conditions_db)
/app/database/                   # Volume-mounted shared database module
├── database.py                  # Database connection and configuration
└── models.py                    # SQLAlchemy models (RawData, Document, etc.)
```

## Features

- 🌐 **Web Scraping**: Extracts condition data from Medical website via requests + BeautifulSoup
- 📄 **Dual Storage**: Save to JSON files OR PostgreSQL database (RawData table)
- 🔍 **Flexible Targeting**: Scrape individual conditions or all conditions
- 🗺️ **Sitemap Discovery**: Automatically discovers available conditions from Medical sitemap
- ⚡ **Rate Limiting**: Configurable delays to respect server resources (default: 1.0s)
- 🛡️ **Error Handling**: Robust error handling, validation, and retry logic
- 🚫 **Duplicate Prevention**: Checks database for existing conditions before scraping
- 🏗️ **Modular Design**: Clean separation of concerns with organized code structure
- 🐳 **Docker Integration**: Containerized with non-root user for security
- 🗃️ **Database Integration**: Direct persistence to PostgreSQL with shared RawData model
- 🔄 **Service Dependencies**: Waits for postgres health check and db migrations to complete

## Installation

### Local Development
```bash
# Install scraper dependencies
pip install -r requirements.txt

# Run with database (requires DATABASE_URL environment variable)
export DATABASE_URL="postgresql://postgres:password@localhost:5434/medical_conditions_db"
python main.py --list-conditions
python main.py --condition acne --database
```

### Docker (Recommended)
```bash
# Build the scraper container
docker compose build scraper

# Run scraper with database
docker compose run --rm scraper python main.py --all --database
```

## Usage

### Command Line Interface

#### List Available Conditions
```bash
python main.py --list-conditions
```

Queries the Medical sitemap to discover all available medical conditions.

#### Scrape All Conditions to Database (Recommended)
```bash
python main.py --all --database
```

Scrapes all conditions and stores them in PostgreSQL `raw_data` table.

#### Scrape All Conditions to JSON Files
```bash
python main.py --all
```

Scrapes all conditions and saves as JSON files in the `scraped/` directory.

#### Scrape Specific Condition
```bash
# Store in database
python main.py --condition acne --database
python main.py --condition acid-reflux-gerd --database

# Save as JSON file
python main.py --condition acne --output-dir custom_output/
```

#### Rate Limiting
```bash
python main.py --all --delay 2.0 --database  # 2 second delay between requests
```

### Docker Integration

The scraper runs automatically as part of the Docker Compose stack:

```bash
# Run full stack (postgres → db migrations → scraper)
docker compose up

# Run scraper only with database
docker compose up postgres db scraper

# Run scraper with custom command
docker compose run --rm scraper python main.py --condition acne --database
```

**Default Docker Behavior**: The scraper service is commented out in `docker-compose.yml` by default to prevent automatic scraping on every `docker compose up`. Uncomment the command line to enable automatic scraping.

## Output Structure

### Database Storage (Recommended)

Data is stored in the `raw_data` table with the following structure:
- **id**: UUID primary key
- **content**: JSONB containing the scraped data
- **source**: Condition slug (e.g., "acne", "acid-reflux-gerd")
- **created_at**: Timestamp

### JSON File Structure

When using `--output-dir`, files are saved as `{condition-slug}.json`:

```json
{
  "title": "Condition Name",
  "url": "https://patients.amwell.com/conditions/condition-slug",
  "introduction": "Brief description...",
  "symptoms": {
    "heading": "Symptoms heading",
    "list": ["symptom1", "symptom2"]
  },
  "onlineDiagnosingAndTreating": {
    "heading": "Treatment heading",
    "content": [
      {"type": "p", "text": "paragraph text"},
      {"type": "ul", "items": ["list item 1", "list item 2"]}
    ]
  },
  "sections": [...],
  "faqs": [...]
}
```

## Architecture

This scraper features a clean, modular architecture with shared database configuration:

- **`main.py`**: Command-line interface and argument parsing
- **`jobs/scraper.py`**: Core scraping logic and web requests
- **`jobs/parser.py`**: HTML parsing and data extraction utilities
- **`jobs/persistence.py`**: Database operations using shared DB models

### 🔄 Shared Database Configuration

The scraper uses the **same database configuration** as the main application:
- **Volume mount**: `./medical_conditions_db:/app/database` contains shared `database.py` and `models.py`
- **Single source of truth**: No duplicate database configurations
- **Consistent models**: Uses the exact same `RawData` model as the main DB service
- **Import path**: Adds `/app/database` to `sys.path` for shared module access

The scraper is **intentionally separated** from the main API to:

- ✅ Keep API dependencies minimal and lightweight
- ✅ Allow independent deployment and scaling
- ✅ Enable scheduled data collection jobs without affecting the API
- ✅ Provide clear separation of concerns (ETL collection vs data processing vs serving)
- ✅ Share database configuration across services without code duplication
- ✅ Run as a one-off job or scheduled task

## Programmatic Usage

You can also import and use the scraper programmatically:

```python
from jobs.scraper import scrape_condition, scrape_all_conditions, list_available_conditions
from jobs.parser import extract_nested_list

# Get list of available conditions from Medical sitemap
conditions = list_available_conditions()
print(f"Found {len(conditions)} conditions")

# Scrape a specific condition to database
# Basic usage (the function will create/disconnect its own DB connection):
data = scrape_condition("acne", use_database=True)

# Advanced: reuse a DatabasePersistence instance across multiple calls to avoid
# reconnecting/disconnecting for each condition (recommended when scraping many):
# db = DatabasePersistence()
# if db.connect():
#     data = scrape_condition("acne", use_database=True, db_persistence=db)

# Scrape a specific condition to JSON file
data = scrape_condition("acne", output_dir="my_output", use_database=False)

# Scrape all conditions with custom delay
scrape_all_conditions(output_dir="output", delay=2.0, use_database=True)
```

## Dependencies

- **requests** (>=2.31.0): HTTP client for web requests
- **beautifulsoup4** (>=4.12.0): HTML parsing and extraction
- **lxml** (>=4.9.3): Fast XML/HTML parsing backend
- **sqlalchemy** (>=2.0.0): Database ORM
- **psycopg2-binary** (>=2.9.0): PostgreSQL adapter
- **alembic** (>=1.12.0): Database migrations
- **pgvector** (>=0.2.0): Vector similarity search support

## Best Practices

1. **Use Database Storage**: Prefer `--database` flag for production use
2. **Check for Duplicates**: Scraper automatically skips existing conditions in database
3. **Respect robots.txt**: Always check site's robots.txt policy before scraping
4. **Rate limiting**: Use appropriate delays between requests (default: 1.0s, recommended: 2.0s+)
5. **Error handling**: Monitor logs for 404 errors and validation failures
6. **Data validation**: Validate condition slugs with `--list-conditions` before scraping
7. **Service Dependencies**: Ensure postgres is healthy and migrations are complete before scraping

## Integration

This scraper is the **first stage** of the 3-stage ETL pipeline:

```
Stage 1: Scraper → RawData (PostgreSQL)
Stage 2: Worker → ProcessedData (PostgreSQL) 
Stage 3: Worker → Documents with Embeddings (PostgreSQL + pgvector)
```

### Data Flow:
1. **Scraper** collects raw HTML and stores in `raw_data` table
2. **Worker** processes raw data and stores structured content in `processed_data` table
3. **Worker** generates embeddings and stores chunks in `documents` table
4. **API** serves processed data via RAG-powered chat interface
5. **Frontend** provides user-facing Streamlit interface

### Docker Compose Dependency Chain:
```
postgres (healthy) → db (migrations) → scraper → worker → api → frontend
```