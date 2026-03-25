"""
TRACKTWO — JSON API
Serves scraped data as JSON. Run with:  uvicorn api:app --port 8502

No API keys required — all data is scraped from public RSS feeds.

Endpoints
---------
GET /data                  All posts for all subjects + merged timeline
GET /data/timeline         Merged timeline only (newest first)
GET /data/{slug}           All posts for one subject  (donald-trump)
GET /data/{slug}/twitter   Twitter/X posts only
GET /data/{slug}/truth     Truth Social posts only
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scraper import HANDLES, _serialise, fetch_all, fetch_truth_social, fetch_tweets, demo_posts

app = FastAPI(
    title="TRACKTWO API",
    description="Live social media posts for Donald Trump. No API key required.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

SLUG_MAP = {
    "donald-trump": "Donald Trump",
}


def _fetch_person(name: str) -> dict:
    handle = HANDLES[name]

    tweets = fetch_tweets(handle)
    if not tweets or (len(tweets) == 1 and "error" in tweets[0]):
        tweets = demo_posts(name, "Twitter/X")

    truth = fetch_truth_social(name)
    if not truth or (len(truth) == 1 and "error" in truth[0]):
        truth = demo_posts(name, "Truth Social")

    for p in tweets + truth:
        p["author"] = name

    return {
        "author": name,
        "twitter": _serialise(tweets),
        "truth_social": _serialise(truth),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/data", summary="All posts for all subjects + merged timeline")
def get_all_data():
    return fetch_all()


@app.get("/data/timeline", summary="Merged timeline only (newest first)")
def get_timeline():
    data = fetch_all()
    return {"fetched_at": data["fetched_at"], "timeline": data["timeline"]}


@app.get("/data/{slug}", summary="All posts for one subject")
def get_person(slug: str):
    name = SLUG_MAP.get(slug.lower())
    if not name:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown subject '{slug}'. Valid slugs: {list(SLUG_MAP)}",
        )
    return _fetch_person(name)


@app.get("/data/{slug}/twitter", summary="Twitter/X posts for one subject")
def get_person_twitter(slug: str):
    name = SLUG_MAP.get(slug.lower())
    if not name:
        raise HTTPException(status_code=404, detail=f"Unknown subject '{slug}'.")
    data = _fetch_person(name)
    return {"author": name, "posts": data["twitter"]}


@app.get("/data/{slug}/truth", summary="Truth Social posts for one subject")
def get_person_truth(slug: str):
    name = SLUG_MAP.get(slug.lower())
    if not name:
        raise HTTPException(status_code=404, detail=f"Unknown subject '{slug}'.")
    data = _fetch_person(name)
    return {"author": name, "posts": data["truth_social"]}
