"""HTML → JSON: keep the parts of a condition page the chatbot learns from.

Each output field matches a row of the "HTML → JSON" table on
https://medicalchatbot.demos.davieldev.com/scraper#mapping
Text is kept exactly as found, non-breaking spaces included: the worker normalizes it.
"""

from collections.abc import Iterator

from bs4 import BeautifulSoup, Tag

SYMPTOMS_CARD = "div.contact-us-card"
# A <section class="rtf"> in the original template, a <div class="rtf rtf--with-margin"> since the 2026 redesign
CLINICAL_TEXT = "section.rtf, .rtf.rtf--with-margin"
PLACEHOLDER_SYMPTOM = "And more."


def parse_condition_page(html: str, url: str, slug: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    clinical_text = soup.select_one(CLINICAL_TEXT)
    return {
        "title": _text(soup.select_one("h1"), default=slug.replace("-", " ").title()),
        "url": url,
        "symptoms": _symptoms(soup),
        "onlineDiagnosingAndTreating": _diagnosis_and_treatment(clinical_text),
        "sections": _other_sections(soup, clinical_text),
    }


def nested_list_items(list_tag: Tag) -> list[dict]:
    """<ul>/<ol> → [{"text": ...}, {"text": ..., "subitems": [...]}], recursing into nested lists."""
    items = []
    for li in list_tag.find_all("li", recursive=False):
        nested_list = li.find(["ul", "ol"])
        if nested_list is None:
            items.append({"text": li.get_text(" ", strip=True)})
            continue
        lead_in = []  # the item's own text, before its nested list starts
        for child in li.contents:
            if child.name in ("ul", "ol"):
                break
            lead_in.append(child.strip() if isinstance(child, str) else child.get_text(" ", strip=True))
        items.append({"text": " ".join(lead_in).strip(), "subitems": nested_list_items(nested_list)})
    return items


def _text(tag: Tag | None, default: str = "") -> str:
    return tag.get_text(strip=True) if tag else default


def _symptoms(soup: BeautifulSoup) -> dict:
    card = soup.select_one(SYMPTOMS_CARD)
    bullets = card.find("ul") if card else None
    if bullets is None:
        return {}
    # An <h3> in the original template, an <h2> since the 2026 redesign
    heading = card.find(["h2", "h3"], class_="contact-us-card__heading")
    return {
        "heading": _text(heading),
        "list": [text for li in bullets.find_all("li") if (text := li.get_text(strip=True)) != PLACEHOLDER_SYMPTOM],
    }


def _diagnosis_and_treatment(clinical_text: Tag | None) -> dict:
    if clinical_text is None:
        return {}
    return {"heading": _text(clinical_text.find("h2")), "content": _content_blocks(clinical_text)}


def _content_blocks(container: Tag) -> list[dict]:
    """Typed paragraphs and lists. Consecutive lists merge into one, even across empty paragraphs."""
    blocks: list[dict] = []
    for element in _paragraphs_and_lists(container):
        if element.name == "p":
            if text := element.get_text(" ", strip=True):
                kind = "strong_paragraph" if element.find(["strong", "b"]) else "paragraph"
                blocks.append({"type": kind, "text": text})
        elif blocks and blocks[-1]["type"] == "ul":
            blocks[-1]["items"].extend(nested_list_items(element))
        else:
            blocks.append({"type": "ul", "items": nested_list_items(element)})
    return blocks


def _paragraphs_and_lists(container: Tag) -> Iterator[Tag]:
    """Direct <p>, <ul> and <ol> children, looking one level into unstyled <div>/<section> wrappers."""
    for element in container.find_all(recursive=False):
        if element.name in ("p", "ul", "ol"):
            yield element
        elif element.name in ("div", "section") and not element.get("class"):
            yield from element.find_all(["p", "ul", "ol"], recursive=False)


def _other_sections(soup: BeautifulSoup, clinical_text: Tag | None) -> list[dict]:
    """Every other headed section that has paragraphs."""
    sections = []
    for number, section in enumerate(soup.select("section, div.section"), 1):
        heading = _text(section.find(["h2", "h3"]), default="General")
        is_untitled_page_header = number <= 2 and heading == "General"
        is_already_parsed = section.select_one(SYMPTOMS_CARD) or (
            clinical_text and (section is clinical_text or section in clinical_text.parents)
        )
        if is_untitled_page_header or is_already_parsed:
            continue
        if content := "\n".join(p.get_text(" ", strip=True) for p in section.find_all("p")).strip():
            sections.append({"heading": heading, "content": content})
    return sections
