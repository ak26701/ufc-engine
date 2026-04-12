import re
import time
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional

BASE_URL = "http://ufcstats.com"

TARGET_CLASSES = {"lightweight", "welterweight", "heavyweight"}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ufc-engine/1.0)"}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _get(url: str, retries: int = 3, delay: float = 1.2) -> BeautifulSoup:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            time.sleep(delay)
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  Retry {attempt + 1} for {url}: {e}")
            time.sleep(delay * 2)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_height(raw: str) -> Optional[float]:
    m = re.match(r"(\d+)'\s*(\d+)", raw.strip())
    return int(m.group(1)) * 12 + int(m.group(2)) if m else None


def _parse_reach(raw: str) -> Optional[float]:
    m = re.match(r"([\d.]+)", raw.strip())
    return float(m.group(1)) if m else None


def _parse_weight(raw: str) -> Optional[float]:
    m = re.match(r"([\d.]+)", raw.strip())
    return float(m.group(1)) if m else None


def _parse_pct(raw: str) -> float:
    m = re.match(r"([\d.]+)", raw.strip().replace("%", ""))
    return float(m.group(1)) / 100 if m else 0.0


def _parse_time(raw: str) -> int:
    m = re.match(r"(\d+):(\d+)", raw.strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 0


def _parse_of(raw: str) -> tuple[int, int]:
    m = re.match(r"(\d+)\s+of\s+(\d+)", raw.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _cell(rows, row_idx: int, col: int) -> str:
    try:
        return rows[row_idx].select("td")[col].get_text(strip=True)
    except IndexError:
        return ""


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def get_all_events() -> list[dict]:
    """Return all completed events, newest first."""
    soup = _get(f"{BASE_URL}/statistics/events/completed?page=all")
    rows = soup.select("tr.b-statistics__table-row")
    events = []
    for row in rows:
        link = row.select_one("a.b-link")
        if not link:
            continue
        date_cell = row.select_one("span.b-statistics__date")
        location_cell = row.select("td")[1] if len(row.select("td")) > 1 else None
        events.append({
            "name": link.get_text(strip=True),
            "url": link["href"],
            "date": date_cell.get_text(strip=True) if date_cell else None,
            "location": location_cell.get_text(strip=True) if location_cell else None,
        })
    return events


def get_event_fights(event_url: str) -> list[dict]:
    """Return all fights listed on an event page."""
    soup = _get(event_url)
    fights = []
    for row in soup.select("tr.b-fight-details__table-row[data-link]"):
        fight_url = row.get("data-link", "").strip()
        if not fight_url:
            continue

        cells = row.select("td")
        if len(cells) < 7:
            continue

        weight_class = cells[6].get_text(strip=True).lower()
        fights.append({
            "fight_url": fight_url,
            "weight_class": weight_class,
        })
    return fights


# ---------------------------------------------------------------------------
# Fighters
# ---------------------------------------------------------------------------

def get_fighter(fighter_url: str) -> Optional[dict]:
    soup = _get(fighter_url)

    name_tag = soup.select_one("span.b-content__title-highlight")
    if not name_tag:
        return None
    name = name_tag.get_text(strip=True)

    record = {"wins": 0, "losses": 0, "draws": 0}
    record_tag = soup.select_one("span.b-content__title-record")
    if record_tag:
        text = record_tag.get_text(strip=True).replace("Record:", "").strip()
        parts = re.split(r"[-–]", text)
        if len(parts) >= 3:
            record["wins"] = int(re.sub(r"\D", "", parts[0]) or 0)
            record["losses"] = int(re.sub(r"\D", "", parts[1]) or 0)
            record["draws"] = int(re.sub(r"\D", "", parts[2]) or 0)

    info = {}
    for li in soup.select("li.b-list__box-list-item"):
        text = li.get_text(separator="|", strip=True)
        if "|" in text:
            key, val = text.split("|", 1)
            info[key.strip()] = val.strip()

    return {
        "name": name,
        "url": fighter_url,
        "height_in": _parse_height(info.get("Height:", "")),
        "weight_lbs": _parse_weight(info.get("Weight:", "")),
        "reach_in": _parse_reach(info.get("Reach:", "")),
        "stance": info.get("STANCE:") or info.get("Stance:"),
        "dob": info.get("DOB:"),
        "wins": record["wins"],
        "losses": record["losses"],
        "draws": record["draws"],
    }


# ---------------------------------------------------------------------------
# Fight detail
# ---------------------------------------------------------------------------

def get_fight(fight_url: str) -> Optional[dict]:
    """
    Returns a dict with:
      - fight metadata (method, round, time, weight_class)
      - fighters: list of two dicts with fighter url + per-fight stats
    """
    soup = _get(fight_url)

    # ---- metadata ----
    meta = {"method": "", "round": 0, "time_sec": 0, "weight_class": ""}
    for item in soup.select("i.b-fight-details__text-item"):
        text = item.get_text(separator="|", strip=True)
        if "Method:" in text:
            meta["method"] = text.split("|")[-1].strip()
        elif "Round:" in text:
            val = text.split("|")[-1].strip()
            meta["round"] = int(val) if val.isdigit() else 0
        elif "Time:" in text:
            meta["time_sec"] = _parse_time(text.split("|")[-1])

    # weight class from fight details
    for li in soup.select("li.b-fight-details__text-item"):
        raw = li.get_text(strip=True)
        if "weight" in raw.lower():
            meta["weight_class"] = raw.split(":")[-1].strip().lower()
            break

    # ---- fighter links + winner ----
    fighter_sections = soup.select("div.b-fight-details__person")
    if len(fighter_sections) < 2:
        return None

    fighter_urls = []
    winner_url = None
    for section in fighter_sections[:2]:
        link = section.select_one("h3.b-fight-details__person-name a")
        if not link:
            return None
        url = link["href"].strip()
        fighter_urls.append(url)
        if section.select_one("i.b-fight-details__person-status--winner") or \
           "b-fight-details__person--winner" in section.get("class", []):
            winner_url = url

    # Also check the status label
    for i, section in enumerate(fighter_sections[:2]):
        status = section.select_one("i.b-fight-details__person-status")
        if status and status.get_text(strip=True).upper() == "W":
            winner_url = fighter_urls[i]

    # ---- totals table ----
    totals_rows = []
    tables = soup.select("table.b-fight-details__table-inner")
    if tables:
        totals_rows = tables[0].select("tbody tr")

    sig_rows = []
    if len(tables) > 1:
        sig_rows = tables[1].select("tbody tr")

    fighters_stats = []
    for idx in range(2):
        stats = {
            "fighter_url": fighter_urls[idx],
            "is_winner": fighter_urls[idx] == winner_url,
            "kd": int(_cell(totals_rows, idx, 1) or 0),
        }

        sl, sa = _parse_of(_cell(totals_rows, idx, 2))
        stats["sig_str_landed"] = sl
        stats["sig_str_attempted"] = sa
        stats["sig_str_pct"] = _parse_pct(_cell(totals_rows, idx, 3))

        tl, ta = _parse_of(_cell(totals_rows, idx, 4))
        stats["total_str_landed"] = tl
        stats["total_str_attempted"] = ta

        tdl, tda = _parse_of(_cell(totals_rows, idx, 5))
        stats["td_landed"] = tdl
        stats["td_attempted"] = tda
        stats["td_pct"] = _parse_pct(_cell(totals_rows, idx, 6))

        stats["sub_att"] = int(_cell(totals_rows, idx, 7) or 0)
        stats["rev"] = int(_cell(totals_rows, idx, 8) or 0)
        stats["ctrl_sec"] = _parse_time(_cell(totals_rows, idx, 9))

        # sig strike zones
        hl, ha = _parse_of(_cell(sig_rows, idx, 3))
        bl, ba = _parse_of(_cell(sig_rows, idx, 4))
        ll, la = _parse_of(_cell(sig_rows, idx, 5))
        dl, da = _parse_of(_cell(sig_rows, idx, 6))
        cl, ca = _parse_of(_cell(sig_rows, idx, 7))
        gl, ga = _parse_of(_cell(sig_rows, idx, 8))

        stats.update({
            "head_landed": hl, "head_attempted": ha,
            "body_landed": bl, "body_attempted": ba,
            "leg_landed": ll, "leg_attempted": la,
            "distance_landed": dl, "distance_attempted": da,
            "clinch_landed": cl, "clinch_attempted": ca,
            "ground_landed": gl, "ground_attempted": ga,
        })

        fighters_stats.append(stats)

    return {**meta, "fighters": fighters_stats, "fighter_urls": fighter_urls, "winner_url": winner_url}
