# TRACKTWO

Real-time social media tracker for Pete Hegseth and Donald Trump across Twitter/X and Truth Social.

**No API keys required.** All data is scraped from public RSS feeds.

## Features

- **4-quadrant layout** — Twitter/X (top row) and Truth Social (bottom row) for each person
- **Combined timeline** — all posts merged in chronological order below the quadrants
- **Red highlighting** — posts from the last hour get a red border and background
- **Auto-refresh** — Streamlit UI updates every 60 seconds automatically
- **JSON API** — FastAPI endpoint serving all scraped data as JSON

## How it works

| Platform | Source |
|---|---|
| Twitter/X | Public [Nitter](https://github.com/zedeus/nitter) RSS feeds (tries multiple instances, first success wins) |
| Truth Social | Public RSS feeds at `truthsocial.com/@handle/feed.rss` |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run

**Streamlit UI** (port 8501):

```bash
streamlit run app.py
```

**JSON API** (port 8502):

```bash
uvicorn api:app --port 8502
```

Run both at once:

```bash
streamlit run app.py & uvicorn api:app --port 8502
```

---

## JSON API

Interactive docs available at `http://localhost:8502/docs` (Swagger UI) when the API is running.

| Endpoint | Description |
|---|---|
| `GET /data` | All posts for all subjects + merged timeline |
| `GET /data/timeline` | Merged timeline only, newest first |
| `GET /data/pete-hegseth` | All posts for Pete Hegseth |
| `GET /data/pete-hegseth/twitter` | Pete Hegseth's Twitter/X posts only |
| `GET /data/pete-hegseth/truth` | Pete Hegseth's Truth Social posts only |
| `GET /data/donald-trump` | All posts for Donald Trump |
| `GET /data/donald-trump/twitter` | Donald Trump's Twitter/X posts only |
| `GET /data/donald-trump/truth` | Donald Trump's Truth Social posts only |

### Example response — `GET /data`

```json
{
  "fetched_at": "2026-03-25T14:00:00+00:00",
  "subjects": {
    "Pete Hegseth": {
      "twitter": [ ... ],
      "truth_social": [ ... ]
    },
    "Donald Trump": {
      "twitter": [ ... ],
      "truth_social": [ ... ]
    }
  },
  "timeline": [
    {
      "id": "...",
      "author": "Donald Trump",
      "platform": "Truth Social",
      "text": "...",
      "created_at": "2026-03-25T13:45:00+00:00",
      "recent": true,
      "url": "https://truthsocial.com/...",
      "likes": 0,
      "retweets": 0
    }
  ]
}
```

Each post includes `"recent": true/false` indicating whether it was posted within the last hour.

## Nitter instances

Twitter/X scraping uses public Nitter instances tried in this order:

1. `nitter.privacydev.net`
2. `nitter.poast.org`
3. `nitter.net`
4. `nitter.it`
5. `nitter.1d4.us`
6. `nitter.fdn.fr`

If all instances are unreachable, the app falls back to demo placeholder posts. You can add or reorder instances in `NITTER_INSTANCES` inside `scraper.py`.
