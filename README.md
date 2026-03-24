# TRACKTWO

Real-time social media tracker for Pete Hegseth and Donald Trump across Twitter/X and Truth Social.

## Features

- **4-quadrant layout** — Twitter/X (top row) and Truth Social (bottom row) for each person
- **Combined timeline** — all posts merged in chronological order below the quadrants
- **Red highlighting** — posts from the last hour get a red border and background
- **Auto-refresh** — updates every 60 seconds automatically

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

#### Option B: Environment variable / `.env` file

```bash
cp .env.example .env
```

Edit `.env`:

```env
TWITTER_BEARER_TOKEN=your_bearer_token_here
```

The app checks Streamlit secrets first, then falls back to the environment variable, so both methods work side-by-side.

### 4. Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Security

`.streamlit/secrets.toml` and `.env` are gitignored. Never commit files containing real tokens.
