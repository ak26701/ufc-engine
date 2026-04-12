import requests
import time
import json
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import Optional

BASE_URL = "http://ufcstats.com"

WEIGHT_CLASSES = {
    "Lightweight": 155,
    "Welterweight": 170,
    "Heavyweight": 265,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"
}


@dataclass
class Fighter:
    name: str
    url: str
    height_in: Optional[float]
    weight_lbs: Optional[float]
    reach_in: Optional[float]
    stance: Optional[str]
    dob: Optional[str]
    wins: int
    losses: int
    draws: int


@dataclass
class FightStats:
    fight_url: str
    fighter_name: str
    opponent_name: str
    date: str
    event: str
    result: str          # W / L / D / NC
    method: str          # KO/TKO, SUB, U-DEC, S-DEC, M-DEC, DQ, NC
    round: int
    time_sec: int        # fight duration in seconds

    # Striking
    kd: int
    sig_str_landed: int
    sig_str_attempted: int
    sig_str_pct: float
    total_str_landed: int
    total_str_attempted: int

    # Grappling
    td_landed: int
    td_attempted: int
    td_pct: float
    sub_att: int
    rev: int
    ctrl_sec: int        # control time in seconds

    # Strike zones (landed)
    head_landed: int
    head_attempted: int
    body_landed: int
    body_attempted: int
    leg_landed: int
    leg_attempted: int

    # Strike positions (landed)
    distance_landed: int
    distance_attempted: int
    clinch_landed: int
    clinch_attempted: int
    ground_landed: int
    ground_attempted: int


def _get(url: str, retries: int = 3, delay: float = 1.5) -> BeautifulSoup:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            time.sleep(delay)
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"Retry {attempt + 1} for {url}: {e}")
            time.sleep(delay * 2)


def _parse_height(raw: str) -> Optional[float]:
    """Convert '5' 11"' -> inches as float."""
    match = re.match(r"(\d+)'\s*(\d+)", raw.strip())
    if match:
        return int(match.group(1)) * 12 + int(match.group(2))
    return None


def _parse_reach(raw: str) -> Optional[float]:
    """Convert '72"' -> 72.0"""
    match = re.match(r"([\d.]+)", raw.strip())
    return float(match.group(1)) if match else None


def _parse_weight(raw: str) -> Optional[float]:
    match = re.match(r"([\d.]+)", raw.strip())
    return float(match.group(1)) if match else None


def _parse_pct(raw: str) -> float:
    match = re.match(r"([\d.]+)", raw.strip().replace("%", ""))
    return float(match.group(1)) / 100 if match else 0.0


def _parse_time(raw: str) -> int:
    """Convert 'M:SS' -> total seconds."""
    match = re.match(r"(\d+):(\d+)", raw.strip())
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return 0


def _parse_of(raw: str) -> tuple[int, int]:
    """Parse 'X of Y' -> (X, Y)."""
    match = re.match(r"(\d+)\s+of\s+(\d+)", raw.strip())
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def get_fighters_by_letter(letter: str) -> list[dict]:
    """Fetch all fighters from the A-Z index for a given letter."""
    url = f"{BASE_URL}/statistics/fighters?char={letter}&page=all"
    soup = _get(url)
    rows = soup.select("table.b-statistics__table tbody tr.b-statistics__table-row")
    fighters = []
    for row in rows:
        cells = row.select("td")
        if len(cells) < 3:
            continue
        link = row.select_one("a.b-link")
        if not link:
            continue
        fighters.append({
            "name": link.get_text(strip=True),
            "url": link["href"],
        })
    return fighters


def get_all_fighters() -> list[dict]:
    """Fetch every fighter from the full A-Z index."""
    all_fighters = []
    for char in "abcdefghijklmnopqrstuvwxyz":
        print(f"Fetching fighters: {char.upper()}")
        fighters = get_fighters_by_letter(char)
        all_fighters.extend(fighters)
    return all_fighters


def get_fighter_detail(fighter_url: str) -> Optional[Fighter]:
    """Scrape a fighter's profile page."""
    soup = _get(fighter_url)

    name_tag = soup.select_one("span.b-content__title-highlight")
    if not name_tag:
        return None
    name = name_tag.get_text(strip=True)

    record_tag = soup.select_one("span.b-content__title-record")
    record = {"wins": 0, "losses": 0, "draws": 0}
    if record_tag:
        text = record_tag.get_text(strip=True).replace("Record:", "").strip()
        parts = re.split(r"[-–]", text)
        if len(parts) >= 3:
            record["wins"] = int(re.sub(r"\D", "", parts[0]))
            record["losses"] = int(re.sub(r"\D", "", parts[1]))
            record["draws"] = int(re.sub(r"\D", "", parts[2]))

    info = {}
    for li in soup.select("li.b-list__box-list-item"):
        text = li.get_text(separator="|", strip=True)
        if "|" in text:
            key, val = text.split("|", 1)
            info[key.strip()] = val.strip()

    return Fighter(
        name=name,
        url=fighter_url,
        height_in=_parse_height(info.get("Height:", "")),
        weight_lbs=_parse_weight(info.get("Weight:", "")),
        reach_in=_parse_reach(info.get("Reach:", "")),
        stance=info.get("STANCE:", None),
        dob=info.get("DOB:", None),
        wins=record["wins"],
        losses=record["losses"],
        draws=record["draws"],
    )


def get_fighter_fights(fighter_url: str, fighter_name: str) -> list[FightStats]:
    """Scrape all fight stats for a fighter from their profile page."""
    soup = _get(fighter_url)
    fights = []

    rows = soup.select("tr.b-fight-details__table-row[data-link]")
    for row in rows:
        fight_url = row.get("data-link", "")
        if not fight_url:
            continue
        fight_stats = get_fight_detail(fight_url, fighter_name)
        if fight_stats:
            fights.append(fight_stats)

    return fights


def get_fight_detail(fight_url: str, target_fighter: str) -> Optional[FightStats]:
    """Scrape a single fight page and return stats for the target fighter."""
    soup = _get(fight_url)

    # Event + date
    event_tag = soup.select_one("h2.b-content__title a")
    event = event_tag.get_text(strip=True) if event_tag else ""

    date_tag = soup.select_one("li.b-list__box-list-item:-soup-contains('Date')")
    date = ""
    if date_tag:
        date = date_tag.get_text(strip=True).replace("Date:", "").strip()

    # Method / round / time
    method = ""
    round_num = 0
    time_sec = 0

    for li in soup.select("i.b-fight-details__text-item"):
        text = li.get_text(separator="|", strip=True)
        if "Method:" in text:
            method = text.split("|")[-1].strip()
        elif "Round:" in text:
            val = text.split("|")[-1].strip()
            round_num = int(val) if val.isdigit() else 0
        elif "Time:" in text:
            time_sec = _parse_time(text.split("|")[-1])

    # Per-fighter stats table (two rows: fighter 0 and fighter 1)
    stat_rows = soup.select("table.b-fight-details__table-inner tbody tr")
    if len(stat_rows) < 2:
        return None

    # Identify which row is our target fighter
    fighter_cells = [row.select("td") for row in stat_rows[:2]]
    names = [cells[0].get_text(strip=True) if cells else "" for cells in fighter_cells]

    target_idx = None
    for i, n in enumerate(names):
        if target_fighter.lower() in n.lower():
            target_idx = i
            break
    if target_idx is None:
        return None

    opp_idx = 1 - target_idx
    opp_name = names[opp_idx]

    # Result (W/L) — check winner name
    winner_tag = soup.select_one("div.b-fight-details__person--winner i")
    result = "L"
    if winner_tag:
        winner_section = winner_tag.find_parent("div", class_="b-fight-details__person")
        if winner_section:
            winner_name_tag = winner_section.select_one("h3 a")
            if winner_name_tag and target_fighter.lower() in winner_name_tag.get_text(strip=True).lower():
                result = "W"

    # Parse totals table
    def cell_text(row_idx: int, col: int) -> str:
        try:
            return stat_rows[row_idx].select("td")[col].get_text(strip=True)
        except IndexError:
            return ""

    kd = int(cell_text(target_idx, 1) or 0)
    sig_l, sig_a = _parse_of(cell_text(target_idx, 2))
    sig_pct = _parse_pct(cell_text(target_idx, 3))
    tot_l, tot_a = _parse_of(cell_text(target_idx, 4))
    td_l, td_a = _parse_of(cell_text(target_idx, 5))
    td_pct = _parse_pct(cell_text(target_idx, 6))
    sub_att = int(cell_text(target_idx, 7) or 0)
    rev = int(cell_text(target_idx, 8) or 0)
    ctrl_sec = _parse_time(cell_text(target_idx, 9))

    # Significant strikes breakdown table (second table on page)
    sig_rows = soup.select("table.b-fight-details__table-inner")[1].select("tbody tr") if len(
        soup.select("table.b-fight-details__table-inner")) > 1 else []

    head_l = head_a = body_l = body_a = leg_l = leg_a = 0
    dist_l = dist_a = clinch_l = clinch_a = ground_l = ground_a = 0

    if len(sig_rows) > target_idx:
        def sig_cell(col: int) -> str:
            try:
                return sig_rows[target_idx].select("td")[col].get_text(strip=True)
            except IndexError:
                return ""

        head_l, head_a = _parse_of(sig_cell(3))
        body_l, body_a = _parse_of(sig_cell(4))
        leg_l, leg_a = _parse_of(sig_cell(5))
        dist_l, dist_a = _parse_of(sig_cell(6))
        clinch_l, clinch_a = _parse_of(sig_cell(7))
        ground_l, ground_a = _parse_of(sig_cell(8))

    return FightStats(
        fight_url=fight_url,
        fighter_name=target_fighter,
        opponent_name=opp_name,
        date=date,
        event=event,
        result=result,
        method=method,
        round=round_num,
        time_sec=time_sec,
        kd=kd,
        sig_str_landed=sig_l,
        sig_str_attempted=sig_a,
        sig_str_pct=sig_pct,
        total_str_landed=tot_l,
        total_str_attempted=tot_a,
        td_landed=td_l,
        td_attempted=td_a,
        td_pct=td_pct,
        sub_att=sub_att,
        rev=rev,
        ctrl_sec=ctrl_sec,
        head_landed=head_l,
        head_attempted=head_a,
        body_landed=body_l,
        body_attempted=body_a,
        leg_landed=leg_l,
        leg_attempted=leg_a,
        distance_landed=dist_l,
        distance_attempted=dist_a,
        clinch_landed=clinch_l,
        clinch_attempted=clinch_a,
        ground_landed=ground_l,
        ground_attempted=ground_a,
    )


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "fighters"

    if mode == "fighters":
        fighters = get_all_fighters()
        with open("data/raw/fighters_index.json", "w") as f:
            json.dump(fighters, f, indent=2)
        print(f"Saved {len(fighters)} fighters")

    elif mode == "detail":
        # Example: python ufcstats.py detail "http://ufcstats.com/fighter-details/..."
        url = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else "Unknown"
        fighter = get_fighter_detail(url)
        fights = get_fighter_fights(url, name)
        print(fighter)
        print(f"{len(fights)} fights found")
