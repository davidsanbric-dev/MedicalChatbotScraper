"""Find every condition page, then download and save them one at a time.

Steps 1 and 2, "Find every page" and "Visit one at a time", on
https://medicalchatbot.demos.davieldev.com/scraper
"""

import time
from collections.abc import Sequence
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from .parser import parse_condition_page
from .persistence import PageStore

BASE_URL = "https://patients.amwell.com"
CONDITIONS_URL = f"{BASE_URL}/conditions/"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
TIMEOUT = 30  # seconds per request


def open_http_session() -> requests.Session:
    """One keep-alive connection for the whole run.

    Network errors and 429/5xx answers are retried up to 3 times with
    exponential backoff, honoring the server's Retry-After.
    """
    retries = Retry(total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def fetch(http: requests.Session, url: str) -> requests.Response:
    response = http.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def discover_condition_slugs(http: requests.Session) -> set[str]:
    """Every condition page in the sitemap, or linked from /conditions/ if the sitemap is unavailable."""
    try:
        return _slugs_in_sitemap(fetch(http, SITEMAP_URL).content)
    except (requests.RequestException, ElementTree.ParseError) as error:
        print(f"⚠️ Sitemap unavailable ({error}); reading the conditions index instead")
        return _slugs_linked_from(fetch(http, CONDITIONS_URL).text)


def scrape(http: requests.Session, slugs: Sequence[str], store: PageStore, delay: float) -> list[str]:
    """Download, parse and save every page not saved yet. Returns the slugs that failed."""
    saved = store.saved_slugs()
    pending = [slug for slug in slugs if slug not in saved]
    print(f"🔎 To scrape: {len(pending)} (already saved: {len(slugs) - len(pending)})")
    failed = []
    for number, slug in enumerate(pending, 1):
        if number > 1:
            time.sleep(delay)
        url = f"{CONDITIONS_URL}{slug}"
        print(f"📝 {number}/{len(pending)} {url}")
        try:
            page = parse_condition_page(fetch(http, url).text, url, slug)
            print(f"   ✅ saved to {store.save(slug, page)}")
        except Exception as error:  # one bad page must not stop the run
            print(f"   ❌ {error}")
            failed.append(slug)
    return failed


def _slugs_in_sitemap(xml: bytes) -> set[str]:
    urls = ((loc.text or "").strip() for loc in ElementTree.fromstring(xml).iterfind(".//{*}loc"))
    return {url.removeprefix(CONDITIONS_URL).strip("/") for url in urls if url.startswith(CONDITIONS_URL)} - {""}


def _slugs_linked_from(html: str) -> set[str]:
    links = BeautifulSoup(html, "html.parser").select('a[href^="/conditions/"]')
    return {link["href"].removeprefix("/conditions/").strip("/") for link in links} - {""}
