# TRACKTWO

Real-time social media tracker for Pete Hegseth and Donald Trump across Twitter/X and Truth Social.

## Features

- **4-quadrant layout** — Twitter/X (top row) and Truth Social (bottom row) for each person
- **Combined timeline** — all posts merged in chronological order below the quadrants
- **Red highlighting** — posts from the last hour get a red border and background
- **Auto-refresh** — Streamlit UI updates every 60 seconds automatically
- **JSON API** — FastAPI endpoint serving all scraped data as JSON

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a Twitter/X Bearer Token

1. Go to [developer.twitter.com](https://developer.twitter.com) and create a project/app
2. Copy the **Bearer Token** from the "Keys and Tokens" page
3. The free Basic tier is sufficient for reading user timelines

> **Note:** Truth Social posts are fetched via public RSS feeds and require no credentials.

### 3. Configure credentials

TRACKTWO supports two ways to provide your Bearer Token — pick one:

#### Option A: Streamlit Secrets (recommended for Streamlit Cloud)

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
TWITTER_BEARER_TOKEN = "your_bearer_token_here"
```

When deploying to **Streamlit Cloud**, paste the token under **App settings → Secrets** in the same TOML format.

> The JSON API reads the token from the `TWITTER_BEARER_TOKEN` environment variable (Streamlit secrets are only available inside the Streamlit process).

#### Option B: Environment variable / `.env` file

```bash
cp .env.example .env
```

Edit `.env`:

```env
TWITTER_BEARER_TOKEN=your_bearer_token_here
```

The Streamlit app checks Streamlit secrets first, then falls back to the environment variable. The JSON API always uses the environment variable.

### 4. Run

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

Each post includes a `"recent": true/false` field indicating whether it was posted within the last hour.

---

## Security

`.streamlit/secrets.toml` and `.env` are gitignored. Never commit files containing real tokens.
