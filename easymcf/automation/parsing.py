"""ARCH-BOT-02 / REQ-SRCH-03/05/06 — pure HTML parsing for the search-run pipeline.

No I/O, no browser, no clock reads beyond the `today` argument callers already resolved
through `clock.py` — these two functions take an HTML string and return data, so they run
identically against a live-fetched page or the fixture corpus's captured HTML.

Card selectors mirror the mycareerfutures skill's documented, prototype-validated markup:

- card container: any element whose `id` starts with `job-card-`
- title:   `span[data-testid="job-card__job-title"]`
- company: `p[data-testid="company-hire-info"]`
- posted:  `span[data-cy="job-card-date-info"]`, "today"/"yesterday"/"N days ago" text
  resolved against the caller's own `today` argument (ARCH-STO-05 — never wall-clock
  time read directly from this module)
- salary:  the highest `$`-figure under `[data-testid="salary-range"]`
- urlid:   the card's own `<a href>`, the slug after `/job/`, query string stripped

Detail-page selectors were confirmed against real MCF markup by the human-gated live tier
(`10.TC.24`, `10.IS.15`): `job-details-info-job-expiry-date` (open/closed marker and closing
date), `job-details-info-job-post-id` (mcf_ref), `job-details-info-num-of-applications`
(applicants), `job-details-info-job-categories` (industry_classification), and
`description-content` (description). The first hand-crafted fixture corpus guessed a different,
plausible-looking set (`closing-date`, `mcf-reference`, `number-of-applicants`, `industry`,
`job-description`) that never actually appears in real markup — `tests/fixtures/mcf/detail/*.html`
was updated to match the confirmed real testids in the same pass, so the fixture and oracle tiers
exercise the selectors this module actually ships with, not a plausible-sounding guess.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

_DAYS_AGO_RE = re.compile(r"(\d+)\s+days?\s+ago", re.I)
_SALARY_RE = re.compile(r"\$\s?([\d,]+)")
_CLOSING_DATE_RE = re.compile(r"(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})")


class ParseError(Exception):
    """Raised by parse_detail when neither an open nor a closed marker is present."""


def _resolve_posted_date(text: str, today: date) -> date:
    normalized = (text or "").strip().lower()
    if "today" in normalized:
        return today
    if "yesterday" in normalized:
        return today - timedelta(days=1)
    match = _DAYS_AGO_RE.search(normalized)
    if match:
        return today - timedelta(days=int(match.group(1)))
    return today  # an unparsable posted-date string is treated defensively as "today" rather than aborting the card


def _urlid_from_href(href: str) -> str:
    path = (href or "").split("?", 1)[0]
    marker = "/job/"
    idx = path.find(marker)
    slug = path[idx + len(marker):] if idx != -1 else path.strip("/").rsplit("/", 1)[-1]
    return slug.strip("/")


def _salary_high(card) -> int | None:
    container = card.select_one('[data-testid="salary-range"]')
    if container is None:
        return None
    figures = []
    for span in container.find_all("span"):
        match = _SALARY_RE.search(span.get_text())
        if match:
            figures.append(int(match.group(1).replace(",", "")))
    return max(figures) if figures else None


def _parse_one_card(card, today: date) -> dict | None:
    """Returns None on a malformed card (webscraping skill: parse defensively — one bad
    card must not abort the whole page's extraction)."""
    title_el = card.select_one('span[data-testid="job-card__job-title"]')
    company_el = card.select_one('p[data-testid="company-hire-info"]')
    date_el = card.select_one('span[data-cy="job-card-date-info"]')
    link_el = card.select_one("a[href]")
    if title_el is None or company_el is None or link_el is None:
        return None
    urlid = _urlid_from_href(link_el.get("href", ""))
    if not urlid:
        return None
    posted_date = _resolve_posted_date(date_el.get_text() if date_el else "", today)
    return {
        "urlid": urlid,
        "url_ref": f"https://www.mycareersfuture.gov.sg/job/{urlid}",
        "position_title": title_el.get_text(strip=True),
        "company_name": company_el.get_text(strip=True),
        "salary_high": _salary_high(card),
        "posted_date": posted_date,
    }


def parse_cards(html: str, today: date) -> list[dict]:
    """Each card -> {urlid, url_ref, position_title, company_name, salary_high, posted_date}, or []."""
    soup = BeautifulSoup(html, "html5lib")
    cards = soup.select("[id^='job-card-']")
    parsed = [_parse_one_card(card, today) for card in cards]
    return [card for card in parsed if card is not None]


def _parse_closing_date(text: str) -> str | None:
    match = _CLOSING_DATE_RE.search(text)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%d %b %Y").date().isoformat()


def _int_or_none(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def parse_detail(html: str) -> dict:
    """{"is_open": False} on a closed marker, else the full field dict.

    Raises ParseError if neither an open nor a closed marker is found — the detail page's
    open/closed state is read first, before anything else, per the mycareerfutures skill's
    short-circuit (a closed posting's remaining fields are meaningless and never read).
    """
    soup = BeautifulSoup(html, "html5lib")
    marker = soup.select_one('[data-testid="job-details-info-job-expiry-date"]')
    if marker is None:
        raise ParseError("neither an open nor a closed marker was found on the detail page")
    marker_text = marker.get_text(strip=True)
    if "closed" in marker_text.lower():
        return {"is_open": False}

    mcf_ref_el = soup.select_one('[data-testid="job-details-info-job-post-id"]')
    applicants_el = soup.select_one('[data-testid="job-details-info-num-of-applications"]')
    industry_el = soup.select_one('[data-testid="job-details-info-job-categories"]')
    description_el = soup.select_one('[data-testid="description-content"]')
    return {
        "is_open": True,
        "closing_date": _parse_closing_date(marker_text),
        "applicants": _int_or_none(applicants_el.get_text() if applicants_el else None),
        "industry_classification": industry_el.get_text(strip=True) if industry_el else None,
        "description": description_el.get_text(strip=True) if description_el else None,
        "mcf_ref": mcf_ref_el.get_text(strip=True) if mcf_ref_el else None,
    }
