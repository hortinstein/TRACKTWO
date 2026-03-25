"""
scraper.py — shared data fetching for TRACKTWO.
Used by both app.py (Streamlit UI) and api.py (JSON endpoint).
"""

import html
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

TWITTER_USERS = {
    "Pete Hegseth": {"handle": "PeteHegseth", "id": "34685502"},
    "Donald Trump": {"handle": "realDonaldTrump", "id": "25073877"},
}

TRUTH_SOCIAL_RSS = {
    "Pete Hegseth": "https://truthsocial.com/@PeteHegseth/feed.rss",
    "Donald Trump": "https://truthsocial.com/@realDonaldTrump/feed.rss",
}

RECENT_THRESHOLD = timedelta(hours=1)


def get_bearer_token(streamlit_secrets=None) -> str:
    """
    Resolve the Twitter Bearer Token.
    Pass st.secrets when calling from Streamlit so it can be checked first.
    Falls back to the TWITTER_BEARER_TOKEN environment variable.
    """
    if streamlit_secrets is not None:
        try:
            return streamlit_secrets["TWITTER_BEARER_TOKEN"]
        except (KeyError, Exception):
            pass
    return os.getenv("TWITTER_BEARER_TOKEN", "")


# ──────────────────────────────────────────────────────────────────────────────
# Fetchers
# ──────────────────────────────────────────────────────────────────────────────

def fetch_tweets(user_id: str, handle: str, bearer_token: str, max_results: int = 10) -> list[dict]:
    """Fetch recent tweets via Twitter API v2."""
    if not bearer_token:
        return []

    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    params = {
        "max_results": max_results,
        "tweet.fields": "created_at,text,public_metrics",
        "expansions": "author_id",
        "exclude": "retweets,replies",
    }
    headers = {"Authorization": f"Bearer {bearer_token}"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        posts = []
        for tweet in data.get("data", []):
            created_at = datetime.fromisoformat(
                tweet["created_at"].replace("Z", "+00:00")
            )
            posts.append(
                {
                    "id": tweet["id"],
                    "text": tweet["text"],
                    "created_at": created_at,
                    "platform": "Twitter/X",
                    "url": f"https://x.com/{handle}/status/{tweet['id']}",
                    "likes": tweet.get("public_metrics", {}).get("like_count", 0),
                    "retweets": tweet.get("public_metrics", {}).get("retweet_count", 0),
                }
            )
        return posts
    except Exception as e:
        return [{"error": str(e)}]


def fetch_truth_social(name: str, max_items: int = 10) -> list[dict]:
    """Fetch Truth Social posts via public RSS feed."""
    feed_url = TRUTH_SOCIAL_RSS[name]
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; TRACKTWO/1.0)"}
        resp = requests.get(feed_url, headers=headers, timeout=10)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        items = (
            channel.findall("item") if channel is not None else root.findall(".//item")
        )

        posts = []
        for item in items[:max_items]:
            title = item.findtext("title", "")
            description = item.findtext("description", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            guid = item.findtext("guid", link)

            try:
                created_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc)
            except Exception:
                created_at = datetime.now(timezone.utc)

            raw = description if description else title
            text = re.sub(r"<[^>]+>", "", html.unescape(raw)).strip()

            posts.append(
                {
                    "id": guid,
                    "text": text or title,
                    "created_at": created_at,
                    "platform": "Truth Social",
                    "url": link,
                    "likes": 0,
                    "retweets": 0,
                }
            )
        return posts
    except Exception as e:
        return [{"error": str(e)}]


def demo_posts(name: str, platform: str, count: int = 5) -> list[dict]:
    """Placeholder posts used when real APIs are unavailable."""
    now = datetime.now(timezone.utc)
    handle_map = {
        ("Pete Hegseth", "Twitter/X"): "PeteHegseth",
        ("Donald Trump", "Twitter/X"): "realDonaldTrump",
        ("Pete Hegseth", "Truth Social"): "PeteHegseth",
        ("Donald Trump", "Truth Social"): "realDonaldTrump",
    }
    handle = handle_map.get((name, platform), "unknown")
    posts = []
    for i in range(count):
        created = now - timedelta(minutes=i * 25)
        url = (
            f"https://x.com/{handle}/status/demo{i}"
            if platform == "Twitter/X"
            else f"https://truthsocial.com/@{handle}"
        )
        posts.append(
            {
                "id": f"demo-{name}-{platform}-{i}",
                "text": (
                    f"[Demo] Sample {platform} post #{i+1} from {name}. "
                    "Set TWITTER_BEARER_TOKEN to see real tweets. "
                    "Truth Social loads via RSS automatically."
                ),
                "created_at": created,
                "platform": platform,
                "url": url,
                "author": name,
                "likes": 0,
                "retweets": 0,
            }
        )
    return posts


# ──────────────────────────────────────────────────────────────────────────────
# High-level fetch-all helper
# ──────────────────────────────────────────────────────────────────────────────

def fetch_all(bearer_token: str = "") -> dict:
    """
    Fetch all posts for both subjects across both platforms.
    Returns a dict suitable for JSON serialisation (datetimes as ISO strings).
    Falls back to demo data when APIs are unavailable.
    """
    results: dict[str, dict] = {}

    for name, info in TWITTER_USERS.items():
        tweets = fetch_tweets(info["id"], info["handle"], bearer_token)
        if not tweets or (len(tweets) == 1 and "error" in tweets[0]):
            tweets = demo_posts(name, "Twitter/X")

        truth = fetch_truth_social(name)
        if not truth or (len(truth) == 1 and "error" in truth[0]):
            truth = demo_posts(name, "Truth Social")

        for p in tweets + truth:
            p["author"] = name

        results[name] = {
            "twitter": _serialise(tweets),
            "truth_social": _serialise(truth),
        }

    # Merged timeline sorted newest-first
    all_posts = []
    for person in results.values():
        all_posts.extend(person["twitter"])
        all_posts.extend(person["truth_social"])
    all_posts.sort(key=lambda p: p["created_at"], reverse=True)

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "subjects": results,
        "timeline": all_posts,
    }


def _serialise(posts: list[dict]) -> list[dict]:
    """Convert datetime objects to ISO-8601 strings for JSON output."""
    out = []
    for p in posts:
        row = dict(p)
        if isinstance(row.get("created_at"), datetime):
            row["created_at"] = row["created_at"].isoformat()
            row["recent"] = (
                datetime.now(timezone.utc) - datetime.fromisoformat(row["created_at"])
            ) < RECENT_THRESHOLD
        out.append(row)
    return out
