"""
TRACKTWO — JSON API
Serves scraped data as JSON. Run with:  uvicorn api:app --port 8502

Endpoints
---------
GET /data                  All posts for all subjects + merged timeline
GET /data/timeline         Merged timeline only (newest first)
GET /data/{name}           All posts for one subject  (pete-hegseth | donald-trump)
GET /data/{name}/twitter   Twitter/X posts only
GET /data/{name}/truth     Truth Social posts only
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scraper import fetch_all, TWITTER_USERS, fetch_tweets, fetch_truth_social, demo_posts, get_bearer_token

app = FastAPI(
    title="TRACKTWO API",
    description="Live social media posts for Pete Hegseth and Donald Trump.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Slug → canonical name mapping
SLUG_MAP = {
    "pete-hegseth": "Pete Hegseth",
    "donald-trump": "Donald Trump",
}


def _bearer() -> str:
    return get_bearer_token()  # reads from env var


def _fetch_person(name: str) -> dict:
    info = TWITTER_USERS[name]
    bearer = _bearer()

    tweets = fetch_tweets(info["id"], info["handle"], bearer)
    if not tweets or (len(tweets) == 1 and "error" in tweets[0]):
        tweets = demo_posts(name, "Twitter/X")

    truth = fetch_truth_social(name)
    if not truth or (len(truth) == 1 and "error" in truth[0]):
        truth = demo_posts(name, "Truth Social")

    from scraper import _serialise
    return {
        "author": name,
        "twitter": _serialise(tweets),
        "truth_social": _serialise(truth),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/data", summary="All posts for all subjects + merged timeline")
def get_all_data():
    return fetch_all(bearer_token=_bearer())


@app.get("/data/timeline", summary="Merged timeline only (newest first)")
def get_timeline():
    data = fetch_all(bearer_token=_bearer())
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
    return {"fetched_at": data.get("fetched_at"), "author": name, "posts": data["twitter"]}


@app.get("/data/{slug}/truth", summary="Truth Social posts for one subject")
def get_person_truth(slug: str):
    name = SLUG_MAP.get(slug.lower())
    if not name:
        raise HTTPException(status_code=404, detail=f"Unknown subject '{slug}'.")
    data = _fetch_person(name)
    return {"fetched_at": data.get("fetched_at"), "author": name, "posts": data["truth_social"]}
