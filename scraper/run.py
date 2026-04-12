"""
Main scrape orchestrator.

Full run:   python scraper/run.py
Incremental: python scraper/run.py --incremental   (only new events since last run)
"""

import sys
import argparse
from datetime import date, datetime

sys.path.insert(0, ".")

from scraper.ufcstats import (
    get_all_events,
    get_event_fights,
    get_fighter,
    get_fight,
    TARGET_CLASSES,
)
from database.db import (
    get_conn,
    upsert_fighter,
    upsert_event,
    upsert_fight,
    upsert_fight_stats,
    get_last_event_date,
    update_scrape_state,
)


def parse_date(raw: str) -> date | None:
    if not raw:
        return None
    for fmt in ("%B %d, %Y", "%b. %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def run(incremental: bool = False):
    conn = get_conn()

    last_date = get_last_event_date(conn) if incremental else None
    if incremental and last_date:
        print(f"Incremental mode: only scraping events after {last_date}")
    else:
        print("Full scrape mode")

    events = get_all_events()
    print(f"Found {len(events)} total events")

    events_done = 0
    fights_done = 0
    newest_date = last_date

    # Fighter URL → DB id cache to avoid repeat scrapes
    fighter_cache: dict[str, int] = {}

    for event in events:
        event_date = parse_date(event["date"])

        # Skip already-scraped events in incremental mode
        if incremental and last_date and event_date and event_date <= last_date:
            continue

        print(f"\n[EVENT] {event['name']} ({event['date']})")

        fights = get_event_fights(event["url"])
        target_fights = [f for f in fights if any(wc in f["weight_class"] for wc in TARGET_CLASSES)]

        if not target_fights:
            print(f"  No LW/WW/HW fights — skipping")
            continue

        # Upsert event
        event_id = upsert_event(conn, {
            "name": event["name"],
            "url": event["url"],
            "date": event_date,
            "location": event.get("location"),
        })
        conn.commit()
        events_done += 1

        for fight_meta in target_fights:
            fight_url = fight_meta["fight_url"]
            print(f"  [FIGHT] {fight_url}")

            try:
                fight = get_fight(fight_url)
            except Exception as e:
                print(f"    Error scraping fight: {e}")
                continue

            if not fight or len(fight["fighters"]) < 2:
                print(f"    Skipping — incomplete data")
                continue

            # Scrape + upsert both fighters
            fighter_ids = []
            for f_stat in fight["fighters"]:
                f_url = f_stat["fighter_url"]
                if f_url in fighter_cache:
                    fighter_ids.append(fighter_cache[f_url])
                    continue

                try:
                    fighter_data = get_fighter(f_url)
                except Exception as e:
                    print(f"    Error scraping fighter {f_url}: {e}")
                    fighter_ids.append(None)
                    continue

                if not fighter_data:
                    fighter_ids.append(None)
                    continue

                fid = upsert_fighter(conn, fighter_data)
                conn.commit()
                fighter_cache[f_url] = fid
                fighter_ids.append(fid)

            if None in fighter_ids or len(fighter_ids) < 2:
                print(f"    Skipping — could not resolve both fighters")
                continue

            f1_id, f2_id = fighter_ids
            winner_id = None
            for i, f_stat in enumerate(fight["fighters"]):
                if f_stat["is_winner"]:
                    winner_id = fighter_ids[i]

            # Upsert fight
            fight_id = upsert_fight(conn, {
                "fight_url": fight_url,
                "event_id": event_id,
                "date": event_date,
                "weight_class": fight.get("weight_class") or fight_meta["weight_class"],
                "fighter1_id": f1_id,
                "fighter2_id": f2_id,
                "winner_id": winner_id,
                "method": fight["method"],
                "round": fight["round"],
                "time_sec": fight["time_sec"],
            })

            if fight_id is None:
                print(f"    Could not resolve fight ID — skipping")
                continue

            # Upsert stats for both fighters
            for i, f_stat in enumerate(fight["fighters"]):
                upsert_fight_stats(conn, {
                    "fight_id": fight_id,
                    "fighter_id": fighter_ids[i],
                    "is_winner": f_stat["is_winner"],
                    "kd": f_stat["kd"],
                    "sig_str_landed": f_stat["sig_str_landed"],
                    "sig_str_attempted": f_stat["sig_str_attempted"],
                    "sig_str_pct": f_stat["sig_str_pct"],
                    "total_str_landed": f_stat["total_str_landed"],
                    "total_str_attempted": f_stat["total_str_attempted"],
                    "td_landed": f_stat["td_landed"],
                    "td_attempted": f_stat["td_attempted"],
                    "td_pct": f_stat["td_pct"],
                    "sub_att": f_stat["sub_att"],
                    "rev": f_stat["rev"],
                    "ctrl_sec": f_stat["ctrl_sec"],
                    "head_landed": f_stat["head_landed"],
                    "head_attempted": f_stat["head_attempted"],
                    "body_landed": f_stat["body_landed"],
                    "body_attempted": f_stat["body_attempted"],
                    "leg_landed": f_stat["leg_landed"],
                    "leg_attempted": f_stat["leg_attempted"],
                    "distance_landed": f_stat["distance_landed"],
                    "distance_attempted": f_stat["distance_attempted"],
                    "clinch_landed": f_stat["clinch_landed"],
                    "clinch_attempted": f_stat["clinch_attempted"],
                    "ground_landed": f_stat["ground_landed"],
                    "ground_attempted": f_stat["ground_attempted"],
                })

            conn.commit()
            fights_done += 1
            print(f"    Saved fight + stats")

        if event_date and (newest_date is None or event_date > newest_date):
            newest_date = event_date

    # Record scrape state
    if newest_date:
        update_scrape_state(conn, newest_date, events_done, fights_done)
        conn.commit()

    conn.close()
    print(f"\nDone. Events: {events_done} | Fights: {fights_done}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--incremental", action="store_true",
                        help="Only scrape events newer than last run")
    args = parser.parse_args()
    run(incremental=args.incremental)
