CREATE TABLE IF NOT EXISTS fighters (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    url         TEXT UNIQUE NOT NULL,
    height_in   FLOAT,
    weight_lbs  FLOAT,
    reach_in    FLOAT,
    stance      TEXT,
    dob         TEXT,
    wins        INT DEFAULT 0,
    losses      INT DEFAULT 0,
    draws       INT DEFAULT 0,
    weight_class TEXT,
    ufc_fights  INT DEFAULT 0,
    last_scraped TIMESTAMP,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    url         TEXT UNIQUE NOT NULL,
    date        DATE,
    location    TEXT,
    scraped_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fights (
    id          SERIAL PRIMARY KEY,
    fight_url   TEXT UNIQUE NOT NULL,
    event_id    INT REFERENCES events(id),
    date        DATE,
    weight_class TEXT,
    fighter1_id INT REFERENCES fighters(id),
    fighter2_id INT REFERENCES fighters(id),
    winner_id   INT REFERENCES fighters(id),
    method      TEXT,
    round       INT,
    time_sec    INT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fight_stats (
    id                  SERIAL PRIMARY KEY,
    fight_id            INT REFERENCES fights(id),
    fighter_id          INT REFERENCES fighters(id),
    is_winner           BOOLEAN,

    kd                  INT DEFAULT 0,
    sig_str_landed      INT DEFAULT 0,
    sig_str_attempted   INT DEFAULT 0,
    sig_str_pct         FLOAT DEFAULT 0,
    total_str_landed    INT DEFAULT 0,
    total_str_attempted INT DEFAULT 0,

    td_landed           INT DEFAULT 0,
    td_attempted        INT DEFAULT 0,
    td_pct              FLOAT DEFAULT 0,
    sub_att             INT DEFAULT 0,
    rev                 INT DEFAULT 0,
    ctrl_sec            INT DEFAULT 0,

    head_landed         INT DEFAULT 0,
    head_attempted      INT DEFAULT 0,
    body_landed         INT DEFAULT 0,
    body_attempted      INT DEFAULT 0,
    leg_landed          INT DEFAULT 0,
    leg_attempted       INT DEFAULT 0,

    distance_landed     INT DEFAULT 0,
    distance_attempted  INT DEFAULT 0,
    clinch_landed       INT DEFAULT 0,
    clinch_attempted    INT DEFAULT 0,
    ground_landed       INT DEFAULT 0,
    ground_attempted    INT DEFAULT 0,

    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE(fight_id, fighter_id)
);

-- Tracks scrape runs for incremental updates
CREATE TABLE IF NOT EXISTS scrape_state (
    id              SERIAL PRIMARY KEY,
    last_event_date DATE,
    last_run        TIMESTAMP DEFAULT NOW(),
    events_scraped  INT DEFAULT 0,
    fights_scraped  INT DEFAULT 0
);
