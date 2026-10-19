#!/usr/bin/env python3
"""
update-sd-events.py

Fetches San Diego community events from sandiego.org monthly article pages
and other public sources, parses them, and writes sd-community-events.json
for the GigPilot app.

Strategy: The main sandiego.org/events-festivals page is JS-rendered and
can't be scraped with urllib. Instead, we fetch the monthly "top events"
article pages (e.g., /article/top-october-events) which have real HTML
content with event names, dates, and venues.

Sources:
  - https://www.sandiego.org/article/top-october-events (etc. per month)
  - https://www.sandiego.org/article/san-diegos-top-november-events (etc.)
  - https://dosd.com/san-diego-festivals

Run by GitHub Action weekly, or manually via workflow_dispatch.
"""

import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta
import calendar as cal_mod

# Venue coordinates for distance-based matching in the app
VENUE_COORDS = {
    "Petco Park": [32.7076, -117.1570],
    "Convention Center": [32.7065, -117.1629],
    "Gaslamp Quarter": [32.7109, -117.1604],
    "Balboa Park": [32.7341, -117.1446],
    "Mission Bay": [32.7697, -117.2320],
    "Waterfront Park": [32.7211, -117.1700],
    "Del Mar Fairgrounds": [32.9590, -117.2654],
    "Del Mar Racetrack": [32.9590, -117.2654],
    "Snapdragon Stadium": [32.7830, -117.1196],
    "Pechanga Arena": [32.7563, -117.2108],
    "La Jolla": [32.8328, -117.2713],
    "Birch Aquarium": [32.8663, -117.2510],
    "North Park": [32.7472, -117.1298],
    "Pacific Beach": [32.7970, -117.2505],
    "Ocean Beach": [32.7492, -117.2494],
    "Hillcrest": [32.7479, -117.1614],
    "Little Italy": [32.7233, -117.1685],
    "Liberty Station": [32.7366, -117.2122],
    "MCAS Miramar": [32.8684, -117.1424],
    "Coronado": [32.6859, -117.1831],
    "Fiesta Island": [32.7651, -117.2246],
    "Normal Heights": [32.7683, -117.0993],
    "El Cajon": [32.7948, -116.9625],
    "Escondido": [33.1192, -117.0864],
    "Oceanside": [33.1959, -117.3795],
    "San Marcos": [33.1434, -117.1661],
    "La Mesa": [32.7679, -117.0231],
    "Rancho Bernardo": [33.0127, -117.0733],
    "Julian": [33.0786, -116.6019],
    "Carlsbad": [33.1581, -117.3506],
    "Encinitas": [33.0370, -117.2920],
    "SeaWorld San Diego": [32.7642, -117.2263],
    "San Diego Zoo": [32.7353, -117.1490],
    "San Diego Zoo Safari Park": [33.0986, -116.9977],
    "LEGOLAND California Resort": [33.1267, -117.3116],
    "Belmont Park": [32.7710, -117.2506],
    "Westfield UTC": [32.8696, -117.2063],
    "Old Town San Diego": [32.7543, -117.1962],
    "Carmel Valley": [32.9396, -117.2278],
}

# Month name mapping
MONTH_NAMES = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9,
    'oct': 10, 'nov': 11, 'dec': 12
}

# Known article URL patterns for sandiego.org monthly event pages
MONTHLY_ARTICLE_PATTERNS = [
    'https://www.sandiego.org/article/top-{month}-events',
    'https://www.sandiego.org/article/san-diegos-top-{month}-events',
    'https://www.sandiego.org/article/san-diegos-best-{month}-events',
]

# Category keywords for auto-categorization
CATEGORY_KEYWORDS = {
    'food-drink': ['food', 'wine', 'beer', 'oktoberfest', 'restaurant', 'taste of',
                   'culinary', 'dining', 'cocktail', 'spirits', 'sake', 'coffee',
                   'brunch', 'feast', 'cook', 'chef'],
    'music': ['music', 'concert', 'jazz', 'reggae', 'r&b', 'symphony', 'festival of music',
              'block party', 'dj'],
    'arts': ['film', 'art', 'gallery', 'theater', 'theatre', 'dance', 'ballet',
             'opera', 'museum', 'grinch', 'scrooge', 'lightscape'],
    'sports': ['marathon', 'triathlon', 'run', 'race', 'bike', 'cycling', 'surf',
               'ultimate', 'championship', 'bowl', 'racing', 'walk', '5k', '10k',
               'half marathon'],
    'cultural': ['día de', 'dia de', 'muertos', 'pride', 'indigenous', 'pacific islander',
                 'asian', 'italian', 'cultural'],
    'military': ['fleet week', 'veterans', 'military', 'air show', 'miramar'],
    'family': ['kids', 'halloween', 'pumpkin', 'trick-or-treat', 'spooky',
               'haunted', 'christmas', 'holiday', 'legoland', 'seaworld',
               'zoo', 'aquarium', 'ice rink'],
    'community': ['street fair', 'harvest', 'festival', 'faire', 'parade',
                  'celebration', 'december nights'],
}


def fetch_page(url):
    """Fetch a web page and return its text content."""
    print(f"Fetching: {url}")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'GigPilot-Events/2.0 (GitHub Action; event calendar sync)'
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        print(f"  Fetched {len(html)} bytes")
        return html
    except urllib.error.HTTPError as e:
        print(f"  HTTP error {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"  Fetch failed: {e}")
        return None


def categorize_event(name, venue=''):
    """Auto-categorize an event based on its name and venue."""
    text = (name + ' ' + venue).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return 'community'


def parse_date_text(text, year=None):
    """Try to parse a date string like 'Oct 3', 'October 3-4', 'Nov. 6-15'.
    Returns (start_date_str, end_date_str) or (None, None).
    """
    if year is None:
        year = date.today().year

    text = text.strip().replace('.', '').replace(',', '')

    # "Month Day-Day" pattern (e.g., "Oct 3-4", "November 6-15")
    m = re.match(r'(\w+)\s+(\d{1,2})\s*[-–]\s*(\d{1,2})', text)
    if m:
        month_name = m.group(1).lower()
        if month_name in MONTH_NAMES:
            month = MONTH_NAMES[month_name]
            d1, d2 = int(m.group(2)), int(m.group(3))
            try:
                return (date(year, month, d1).isoformat(),
                        date(year, month, d2).isoformat())
            except ValueError:
                pass

    # "Month Day – Month Day" pattern (e.g., "Nov 6 – Jan 3")
    m = re.match(r'(\w+)\s+(\d{1,2})\s*[-–]\s*(\w+)\s+(\d{1,2})', text)
    if m:
        m1, d1 = m.group(1).lower(), int(m.group(2))
        m2, d2 = m.group(3).lower(), int(m.group(4))
        if m1 in MONTH_NAMES and m2 in MONTH_NAMES:
            month1 = MONTH_NAMES[m1]
            month2 = MONTH_NAMES[m2]
            y2 = year + 1 if month2 < month1 else year
            try:
                return (date(year, month1, d1).isoformat(),
                        date(y2, month2, d2).isoformat())
            except ValueError:
                pass

    # "Month Day" pattern (single day)
    m = re.match(r'(\w+)\s+(\d{1,2})', text)
    if m:
        month_name = m.group(1).lower()
        if month_name in MONTH_NAMES:
            month = MONTH_NAMES[month_name]
            d = int(m.group(2))
            try:
                ds = date(year, month, d).isoformat()
                return (ds, ds)
            except ValueError:
                pass

    return (None, None)


def parse_sandiego_org_article(html, year=None):
    """Parse events from a sandiego.org article page.

    These pages have event names as headings or bold text, followed by
    date and venue information. We look for JSON-LD first, then fall back
    to text extraction.
    """
    events = []
    if year is None:
        year = date.today().year

    # Try JSON-LD structured data first
    ld_matches = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    for ld_text in ld_matches:
        try:
            data = json.loads(ld_text)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get('@type') == 'Event':
                    venue = ''
                    location = item.get('location', {})
                    if isinstance(location, dict):
                        venue = location.get('name', location.get('address', ''))
                    elif isinstance(location, str):
                        venue = location
                    events.append({
                        'name': item.get('name', ''),
                        'start': item.get('startDate', '')[:10],
                        'end': item.get('endDate', item.get('startDate', ''))[:10],
                        'venue': venue,
                        'attendance': 0,
                        'category': categorize_event(item.get('name', ''), venue),
                        'source': 'sandiego.org'
                    })
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    # Also try extracting from text content
    # Strip HTML but preserve structure with newlines
    text = re.sub(r'<h[1-6][^>]*>', '\n### ', html)
    text = re.sub(r'<strong>', '**', text)
    text = re.sub(r'</strong>', '**', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&\w+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    # Look for patterns like "Event Name | Oct 3 | Venue"
    # or "**Event Name** Oct 3-4"
    bold_events = re.findall(r'\*\*([^*]{5,80})\*\*', text)
    for event_name in bold_events:
        event_name = event_name.strip()
        if not event_name or len(event_name) < 5:
            continue
        # Skip navigation/header text
        if any(skip in event_name.lower() for skip in
               ['read more', 'learn more', 'click here', 'subscribe',
                'sign up', 'view all', 'san diego events', 'featured',
                'advertisement', 'sponsored']):
            continue

        # Look for date nearby in the text
        idx = text.find(event_name)
        if idx >= 0:
            context = text[idx:idx + 200]
            # Try to find a date pattern in the surrounding text
            date_match = re.search(
                r'(\w+\.?\s+\d{1,2}(?:\s*[-–]\s*(?:\w+\.?\s+)?\d{1,2})?)',
                context
            )
            if date_match:
                start, end = parse_date_text(date_match.group(1), year)
                if start:
                    events.append({
                        'name': event_name,
                        'start': start,
                        'end': end or start,
                        'venue': 'San Diego',
                        'attendance': 0,
                        'category': categorize_event(event_name),
                        'source': 'sandiego.org'
                    })

    return events


def get_monthly_urls(months_ahead=3):
    """Generate URLs for the next N months of event articles."""
    urls = []
    today = date.today()
    for offset in range(months_ahead + 1):
        m = (today.month + offset - 1) % 12 + 1
        month_name = cal_mod.month_name[m].lower()
        for pattern in MONTHLY_ARTICLE_PATTERNS:
            urls.append(pattern.format(month=month_name))
    return urls


def merge_events(existing_events, new_events):
    """Merge new events into existing list, deduplicating by normalized name+start."""
    seen = set()
    for e in existing_events:
        # Normalize: strip parentheticals, ordinals, extra whitespace
        name_norm = re.sub(r'\s*\([^)]*\)', '', e['name']).strip().lower()
        name_norm = re.sub(r'\d+(st|nd|rd|th)\s+annual\s*', '', name_norm).strip()
        key = (name_norm, e.get('start', ''))
        seen.add(key)

    merged = list(existing_events)
    added = 0
    for e in new_events:
        if not e.get('name'):
            continue
        name_norm = re.sub(r'\s*\([^)]*\)', '', e['name']).strip().lower()
        name_norm = re.sub(r'\d+(st|nd|rd|th)\s+annual\s*', '', name_norm).strip()
        key = (name_norm, e.get('start', ''))
        if key not in seen:
            seen.add(key)
            merged.append(e)
            added += 1

    print(f"  Merged {added} new events (total: {len(merged)})")
    return merged


def prune_old_events(events, cutoff_days=7):
    """Remove events that ended more than cutoff_days ago."""
    cutoff = (date.today() - timedelta(days=cutoff_days)).isoformat()
    before = len(events)
    events = [e for e in events if e.get('end', e.get('start', '9999')) >= cutoff]
    pruned = before - len(events)
    if pruned > 0:
        print(f"  Pruned {pruned} old events")
    return events


def build_events_json(output_path):
    """Main function: fetch events, merge, write JSON."""
    # Load existing JSON as baseline
    existing_events = []
    try:
        with open(output_path) as f:
            data = json.load(f)
            existing_events = data.get('events', [])
        print(f"Loaded {len(existing_events)} existing events from {output_path}")
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"No existing {output_path} found, starting fresh")

    # Fetch monthly article pages from sandiego.org
    urls = get_monthly_urls(months_ahead=3)
    for url in urls:
        html = fetch_page(url)
        if html:
            new_events = parse_sandiego_org_article(html)
            if new_events:
                print(f"  Found {len(new_events)} events from {url}")
                existing_events = merge_events(existing_events, new_events)

    # Also try the main events page for JSON-LD
    html = fetch_page('https://www.sandiego.org/events-festivals')
    if html:
        sd_events = parse_sandiego_org_article(html)
        if sd_events:
            existing_events = merge_events(existing_events, sd_events)

    # Try dosd.com festivals page
    html2 = fetch_page('https://dosd.com/san-diego-festivals')
    if html2:
        dosd_events = parse_sandiego_org_article(html2)
        if dosd_events:
            existing_events = merge_events(existing_events, dosd_events)

    # Prune events that ended >7 days ago
    existing_events = prune_old_events(existing_events)

    # Sort by start date
    existing_events.sort(key=lambda e: e.get('start', '9999'))

    calendar = {
        'lastUpdated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': 'https://www.sandiego.org/events-festivals',
        'events': existing_events
    }

    with open(output_path, 'w') as f:
        json.dump(calendar, f, indent=2)

    print(f"\nWrote {output_path} with {len(existing_events)} events")

    # Show upcoming events
    today = date.today().isoformat()
    upcoming = [e for e in existing_events
                if e.get('end', e.get('start', '')) >= today]
    print(f"  {len(upcoming)} upcoming/active events")
    for e in upcoming[:10]:
        print(f"    {e['start']} - {e.get('end','')} | {e['name']} @ {e.get('venue','')}")
    if len(upcoming) > 10:
        print(f"    ... and {len(upcoming)-10} more")

    return True


if __name__ == '__main__':
    output = sys.argv[1] if len(sys.argv) > 1 else 'sd-community-events.json'
    success = build_events_json(output)
    sys.exit(0 if success else 1)
