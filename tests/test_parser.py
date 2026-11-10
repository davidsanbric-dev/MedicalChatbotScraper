from jobs.parser import parse_condition_page
from jobs.scraper import _slugs_in_sitemap, _slugs_linked_from

URL = "https://patients.amwell.com/conditions/acne"

# The 2026 template, trimmed to the parts the parser reads.
REDESIGNED_PAGE = """
<section><p>Talk to a doctor today.</p></section>
<section><h1>Acne treatment online</h1></section>
<section>
  <div class="contact-us-card">
    <h2 class="contact-us-card__heading">Patients typically experience</h2>
    <ul><li>Blackheads</li><li>Cysts</li><li>And more.</li></ul>
  </div>
</section>
<div class="rtf rtf--with-margin">
  <h2>Diagnosing and Treating Acne Online</h2>
  <p><strong>What causes acne?</strong></p>
  <p>Clogged pores.</p>
  <p>Options may include:</p>
  <ul><li>For mild acne:<ul><li>Gentle cleansing</li></ul></li></ul>
  <p> </p>
  <ol><li>Retinoids</li></ol>
  <div><p>A paragraph in an unstyled wrapper.</p></div>
  <div class="cta"><p>Skipped: a styled block.</p></div>
</div>
<section><h2>When to see a doctor</h2><p>If it scars.</p><p>Or hurts.</p></section>
"""


def test_redesigned_page():
    page = parse_condition_page(REDESIGNED_PAGE, URL, "acne")

    assert page["title"] == "Acne treatment online"
    assert page["url"] == URL
    assert page["symptoms"] == {"heading": "Patients typically experience", "list": ["Blackheads", "Cysts"]}
    assert page["onlineDiagnosingAndTreating"] == {
        "heading": "Diagnosing and Treating Acne Online",
        "content": [
            {"type": "strong_paragraph", "text": "What causes acne?"},
            {"type": "paragraph", "text": "Clogged pores."},
            {"type": "paragraph", "text": "Options may include:"},
            # Both lists merge into one, across the empty paragraph between them.
            {"type": "ul", "items": [
                {"text": "For mild acne:", "subitems": [{"text": "Gentle cleansing"}]},
                {"text": "Retinoids"},
            ]},
            {"type": "paragraph", "text": "A paragraph in an unstyled wrapper."},
        ],
    }
    # The two untitled header sections and the symptom card are not repeated here.
    assert page["sections"] == [{"heading": "When to see a doctor", "content": "If it scars.\nOr hurts."}]


def test_original_template_and_title_fallback():
    html = """
    <div class="contact-us-card"><h3 class="contact-us-card__heading">Signs</h3><ul><li>Cough</li></ul></div>
    <section class="rtf"><h2>Treating it</h2><p>Rest.</p></section>
    """
    page = parse_condition_page(html, URL, "sore-throat")

    assert page["title"] == "Sore Throat"
    assert page["symptoms"] == {"heading": "Signs", "list": ["Cough"]}
    assert page["onlineDiagnosingAndTreating"]["content"] == [{"type": "paragraph", "text": "Rest."}]


def test_missing_parts_stay_empty():
    page = parse_condition_page("<h1>Rash</h1>", URL, "rash")
    assert (page["symptoms"], page["onlineDiagnosingAndTreating"], page["sections"]) == ({}, {}, [])


def test_sitemap_lists_only_condition_pages():
    sitemap = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://patients.amwell.com/how-it-works</loc></url>
      <url><loc>https://patients.amwell.com/conditions</loc></url>
      <url><loc>https://patients.amwell.com/conditions/acne</loc></url>
      <url><loc>https://patients.amwell.com/conditions/ear-pain/</loc></url>
    </urlset>"""
    assert _slugs_in_sitemap(sitemap) == {"acne", "ear-pain"}


def test_index_fallback_reads_condition_links():
    html = '<a href="/conditions/">All</a><a href="/conditions/acne">Acne</a><a href="/about">About</a>'
    assert _slugs_linked_from(html) == {"acne"}
