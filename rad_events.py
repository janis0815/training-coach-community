import re
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from cache import cache

logger = logging.getLogger(__name__)

BASE_URL = "https://breitensport.rad-net.de/breitensportkalender/"

_executor = ThreadPoolExecutor(max_workers=1)


def _scrape_events_sync(url: str) -> list[dict]:
    """Synchrones Scraping in separatem Thread (Playwright Sync API)."""
    from playwright.sync_api import sync_playwright

    events = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(3000)

            links = page.query_selector_all("a.terminlink")

            for link in links:
                try:
                    cells = link.query_selector_all("div.zelle")
                    if len(cells) < 5:
                        continue

                    tooltip = link.query_selector("div.tooltip")
                    event_type = tooltip.inner_text().strip() if tooltip else ""

                    date_cell = cells[1].inner_text().strip()
                    date_match = re.search(r"(\w+, \d{2}\.\d{2}\.\d{4})", date_cell)
                    dist_match = re.search(r"~(\d+)\s*km", date_cell)

                    event_date = date_match.group(1) if date_match else date_cell
                    distance_from_plz = dist_match.group(1) + "km" if dist_match else ""

                    name = cells[2].inner_text().strip()
                    strecken = cells[3].inner_text().strip().replace("\n", "")
                    verein = cells[4].inner_text().strip() if len(cells) > 4 else ""

                    href = link.get_attribute("href") or ""
                    if href and not href.startswith("http"):
                        href = f"https://breitensport.rad-net.de/{href.lstrip('/')}"

                    events.append({
                        "type": event_type,
                        "date": event_date,
                        "name": name,
                        "strecken": strecken,
                        "distance_from_plz": distance_from_plz,
                        "verein": verein,
                        "link": href,
                    })
                except Exception as e:
                    logger.warning(f"Event parse error: {e}")
                    continue

            browser.close()
    except Exception as e:
        logger.error(f"Scraping error: {e}")

    return events


def scrape_events(plz: str = "30171", umkreis: int = 20, start_date: str = None, end_date: str = None) -> list[dict]:
    """Scrapt Events vom BDR Breitensportkalender. Cached für 6 Stunden. Thread-safe für asyncio."""
    if not start_date:
        start_date = datetime.now().strftime("%d.%m.%Y")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=270)).strftime("%d.%m.%Y")

    cache_key = f"events_{plz}_{umkreis}_{start_date}_{end_date}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = (
        f"{BASE_URL}?startdate={start_date}&enddate={end_date}"
        f"&art=-1&titel=&lv=-1&umkreis={umkreis}&plz={plz}"
        f"&tid=&formproof=&go=Termine+suchen"
    )

    # In separatem Thread ausführen um asyncio-Konflikt zu vermeiden
    try:
        loop = asyncio.get_running_loop()
        # Wir sind in einer asyncio-Loop → Thread nutzen
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            events = pool.submit(_scrape_events_sync, url).result(timeout=30)
    except RuntimeError:
        # Keine asyncio-Loop → direkt ausführen
        events = _scrape_events_sync(url)

    if events:
        cache.set(cache_key, events, ttl_seconds=21600)
    return events


def get_events_for_week(events: list[dict], week_start: datetime) -> list[dict]:
    """Filtert Events die in einer bestimmten Woche stattfinden."""
    week_end = week_start + timedelta(days=6)
    week_events = []

    for event in events:
        try:
            # Datum parsen (z.B. "So, 19.04.2026")
            date_str = re.search(r"(\d{2}\.\d{2}\.\d{4})", event["date"])
            if date_str:
                event_date = datetime.strptime(date_str.group(1), "%d.%m.%Y")
                if week_start <= event_date <= week_end:
                    event["parsed_date"] = event_date
                    week_events.append(event)
        except (ValueError, AttributeError):
            continue

    return sorted(week_events, key=lambda e: e.get("parsed_date", datetime.max))


def format_events_for_bot(events: list[dict]) -> str:
    """Formatiert Events für Telegram."""
    if not events:
        return ""

    WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    lines = ["🚴 **Rad-Events diese Woche in deiner Nähe:**\n"]
    for event in events:
        dt = event.get("parsed_date")
        weekday = WEEKDAYS[dt.weekday()] if dt else "?"
        lines.append(
            f"🏁 **{weekday}, {event['date']}** — {event['name']}\n"
            f"   Typ: {event['type']} | Strecken: {event['strecken']}km\n"
            f"   📍 {event['distance_from_plz']} entfernt | {event['verein']}\n"
            f"   🔗 [Details]({event['link']})"
        )

    lines.append(
        "\n💡 *Soll ich ein Event in deinen Wochenplan einbauen? "
        "Sag mir welches und ich plane die Woche drumherum!*"
    )
    return "\n".join(lines)


def format_events_for_prompt(events: list[dict]) -> str:
    """Kompakte Event-Info für den Coach-Prompt."""
    if not events:
        return ""

    lines = ["RAD-EVENTS DIESE WOCHE IN DER NÄHE:"]
    for event in events:
        lines.append(
            f"- {event['date']}: {event['name']} ({event['type']}, {event['strecken']}km, {event['distance_from_plz']} entfernt)"
        )
    lines.append("Schlage dem Athleten vor, ein Event als Trainingseinheit einzubauen. Passe den Wochenplan entsprechend an (Recovery davor/danach).")
    return "\n".join(lines)
