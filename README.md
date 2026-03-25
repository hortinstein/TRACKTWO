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
| Twitter/X | Twitter's own guest GraphQL API (same path the `twitter.com` website uses — no key needed). Falls back to Nitter RSS if unavailable. |
| Truth Social | Public RSS feeds at `truthsocial.com/@handle/feed.rss` |

Twitter's guest API works by activating a short-lived guest token (`POST /1.1/guest/activate.json`) using the same public bearer token embedded in Twitter's own JS bundle, then calling the `UserTweets` GraphQL endpoint. The GraphQL query ID is auto-discovered from Twitter's JS at runtime and falls back to a list of known IDs if discovery fails.

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

## Troubleshooting

**Seeing demo placeholder posts?**
- Twitter guest API: requires outbound access to `api.twitter.com` and `twitter.com`
- Truth Social RSS: requires outbound access to `truthsocial.com`
- If you're behind a restrictive proxy, these connections may be blocked

**Twitter GraphQL query ID changed?**
Twitter occasionally rotates the `UserTweets` query ID when they deploy. `scraper.py` auto-discovers the current ID from Twitter's JS bundle at runtime. If discovery also fails, update `_TW_QUERY_IDS` at the top of `scraper.py` with the current value (findable in Twitter's main JS bundle: search for `queryId:"....",operationName:"UserTweets"`).

**Nitter fallback**
A small list of Nitter instances is tried if the guest API fails. The Nitter project was abandoned by its original maintainer in Jan 2024 but community instances still operate. You can update `_NITTER_INSTANCES` in `scraper.py`.
