# UFC Style Matchup Engine

A machine learning system that builds fighter style profiles, clusters them into archetypes, and predicts method-of-victory probabilities for UFC fights — with a focus on Lightweight, Welterweight, and Heavyweight divisions.

## What It Does

- **Style Profiling** — builds a recency-weighted feature vector per fighter from UFCStats data (striking efficiency, grappling control, distance preference, finishing rate, etc.)
- **Archetype Clustering** — groups fighters into style archetypes (pressure striker, counter fighter, wrestler, submission grappler, brawler, complete fighter) using UMAP + HDBSCAN
- **Matchup Engine** — surfaces historical win rates and method-of-victory breakdowns by archetype pairing, and individual fighter records against each archetype
- **Prediction Model** — Bayesian regression predicts win probability + method of victory (KO/TKO, submission, decision) with confidence intervals
- **Dashboard** — Next.js UI for head-to-head matchup analysis, fighter style cards, and upcoming fight breakdowns

## Stack

| Layer | Tech |
|-------|------|
| Scraping | Python, BeautifulSoup |
| Data | PostgreSQL + pgvector |
| ML | scikit-learn, scipy, UMAP, HDBSCAN |
| API | FastAPI |
| Frontend | Next.js, Tailwind CSS |

## Project Structure

```
ufc-engine/
├── scraper/       # UFCStats scraper
├── pipeline/      # Feature engineering
├── ml/            # Clustering, matchup engine, prediction model
├── api/           # FastAPI backend
├── web/           # Next.js dashboard
└── data/          # Raw + processed data (gitignored)
```

## Research Foundation

Built on findings from:
- *Applying Machine Learning Algorithms to Predict UFC Fight Outcomes* — McQuaide, Stanford
- *Predicting UFC Matches Using Regression Models* — Apelgren & Eklund, KTH

Key improvements over prior work:
- Style archetype clustering (neither paper attempted this)
- Method of victory as prediction target (not just win/loss)
- Exponential decay recency weighting
- Pre-UFC data supplementation for fighters with fewer than 5 UFC appearances

## Divisions

Lightweight (155), Welterweight (170), Heavyweight (265)

## Setup

Coming soon.
