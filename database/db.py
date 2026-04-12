import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("Database initialized.")


def upsert_fighter(conn, fighter: dict) -> int:
    sql = """
        INSERT INTO fighters (name, url, height_in, weight_lbs, reach_in, stance, dob, wins, losses, draws, last_scraped)
        VALUES (%(name)s, %(url)s, %(height_in)s, %(weight_lbs)s, %(reach_in)s, %(stance)s, %(dob)s,
                %(wins)s, %(losses)s, %(draws)s, NOW())
        ON CONFLICT (url) DO UPDATE SET
            name         = EXCLUDED.name,
            height_in    = EXCLUDED.height_in,
            weight_lbs   = EXCLUDED.weight_lbs,
            reach_in     = EXCLUDED.reach_in,
            stance       = EXCLUDED.stance,
            dob          = EXCLUDED.dob,
            wins         = EXCLUDED.wins,
            losses       = EXCLUDED.losses,
            draws        = EXCLUDED.draws,
            last_scraped = NOW(),
            updated_at   = NOW()
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, fighter)
        return cur.fetchone()["id"]


def upsert_event(conn, event: dict) -> int:
    sql = """
        INSERT INTO events (name, url, date, location)
        VALUES (%(name)s, %(url)s, %(date)s, %(location)s)
        ON CONFLICT (url) DO UPDATE SET
            name     = EXCLUDED.name,
            date     = EXCLUDED.date,
            location = EXCLUDED.location
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, event)
        return cur.fetchone()["id"]


def upsert_fight(conn, fight: dict) -> int:
    sql = """
        INSERT INTO fights (fight_url, event_id, date, weight_class, fighter1_id, fighter2_id, winner_id, method, round, time_sec)
        VALUES (%(fight_url)s, %(event_id)s, %(date)s, %(weight_class)s, %(fighter1_id)s, %(fighter2_id)s,
                %(winner_id)s, %(method)s, %(round)s, %(time_sec)s)
        ON CONFLICT (fight_url) DO NOTHING
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, fight)
        row = cur.fetchone()
        return row["id"] if row else None


def upsert_fight_stats(conn, stats: dict):
    sql = """
        INSERT INTO fight_stats (
            fight_id, fighter_id, is_winner,
            kd, sig_str_landed, sig_str_attempted, sig_str_pct,
            total_str_landed, total_str_attempted,
            td_landed, td_attempted, td_pct, sub_att, rev, ctrl_sec,
            head_landed, head_attempted, body_landed, body_attempted,
            leg_landed, leg_attempted, distance_landed, distance_attempted,
            clinch_landed, clinch_attempted, ground_landed, ground_attempted
        ) VALUES (
            %(fight_id)s, %(fighter_id)s, %(is_winner)s,
            %(kd)s, %(sig_str_landed)s, %(sig_str_attempted)s, %(sig_str_pct)s,
            %(total_str_landed)s, %(total_str_attempted)s,
            %(td_landed)s, %(td_attempted)s, %(td_pct)s, %(sub_att)s, %(rev)s, %(ctrl_sec)s,
            %(head_landed)s, %(head_attempted)s, %(body_landed)s, %(body_attempted)s,
            %(leg_landed)s, %(leg_attempted)s, %(distance_landed)s, %(distance_attempted)s,
            %(clinch_landed)s, %(clinch_attempted)s, %(ground_landed)s, %(ground_attempted)s
        )
        ON CONFLICT (fight_id, fighter_id) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.execute(sql, stats)


def get_last_event_date(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT last_event_date FROM scrape_state ORDER BY last_run DESC LIMIT 1")
        row = cur.fetchone()
        return row["last_event_date"] if row else None


def update_scrape_state(conn, last_event_date, events_scraped: int, fights_scraped: int):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO scrape_state (last_event_date, events_scraped, fights_scraped)
            VALUES (%s, %s, %s)
        """, (last_event_date, events_scraped, fights_scraped))


if __name__ == "__main__":
    init_db()
