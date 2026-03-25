"""
scraper.py — shared data fetching for TRACKTWO.
Used by both app.py (Streamlit UI) and api.py (JSON endpoint).

No API keys required. Twitter/X is scraped via public Nitter RSS feeds;
Truth Social is scraped via its own public RSS feeds.
"""

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

HANDLES = {
    "Pete Hegseth": "PeteHegseth",
    "Donald Trump": "realDonaldTrump",
}

TRUTH_SOCIAL_RSS = {
    "Pete Hegseth": "https://truthsocial.com/@PeteHegseth/feed.rss",
    # trumpstruth.org is a public archive that bypasses Cloudflare on truthsocial.com
    "Donald Trump": "https://trumpstruth.org/feed",
}

# Public Nitter instances — tried in order, first success wins
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.perennialte.ch",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
    "https://nitter.fdn.fr",
]

# RSSHub public instance — fallback when Nitter instances block cloud IPs
RSSHUB_BASE = "https://rsshub.app"

RECENT_THRESHOLD = timedelta(hours=1)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TRACKTWO/1.0)"}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_rss_items(xml_text: str, max_items: int) -> list[ET.Element]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall(".//item")
    return items[:max_items]


def _clean_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(raw)).strip()


def _parse_date(pub_date: str) -> datetime:
    try:
        return parsedate_to_datetime(pub_date).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────────────
# Fetchers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_tweet_items(xml_text: str, max_items: int) -> list[dict]:
    """Parse RSS items into tweet dicts, normalising links to x.com."""
    items = _parse_rss_items(xml_text, max_items)
    posts = []
    for item in items:
        title = item.findtext("title", "")
        description = item.findtext("description", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")
        guid = item.findtext("guid", link)

        xcom_link = re.sub(
            r"https?://[^/]+/([^/]+/status/\d+)",
            r"https://x.com/\1",
            link,
        )

        raw = description if description else title
        text = _clean_html(raw)

        posts.append(
            {
                "id": guid,
                "text": text or title,
                "created_at": _parse_date(pub_date),
                "platform": "Twitter/X",
                "url": xcom_link,
                "likes": 0,
                "retweets": 0,
            }
        )
    return posts


def fetch_tweets(handle: str, max_items: int = 10) -> list[dict]:
    """
    Fetch recent tweets via Nitter RSS, falling back to RSSHub.
    Tries each Nitter instance first; if all fail, tries RSSHub.
    No API key required.
    """
    last_error = ""

    # Try Nitter instances
    for instance in NITTER_INSTANCES:
        url = f"{instance}/{handle}/rss"
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=8)
            resp.raise_for_status()
            if "<item>" not in resp.text:
                raise ValueError("No items in feed")
            return _parse_tweet_items(resp.text, max_items)
        except Exception as e:
            last_error = f"{instance}: {e}"
            continue

    # Fallback: RSSHub (works from cloud/datacenter IPs)
    try:
        url = f"{RSSHUB_BASE}/twitter/user/{handle}"
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        if "<item>" not in resp.text:
            raise ValueError("No items in RSSHub feed")
        return _parse_tweet_items(resp.text, max_items)
    except Exception as e:
        last_error = f"RSSHub: {e}"

    return [{"error": f"All sources failed. Last error: {last_error}"}]


def fetch_truth_social(name: str, max_items: int = 10) -> list[dict]:
    """Fetch Truth Social posts via public RSS feed."""
    feed_url = TRUTH_SOCIAL_RSS[name]
    try:
        resp = requests.get(feed_url, headers=_HEADERS, timeout=10)
        if resp.status_code == 403:
            return [{"error": "unavailable", "detail": "Truth Social is protected by Cloudflare and cannot be scraped directly."}]
        resp.raise_for_status()
        # Check if we got XML/RSS (not a Cloudflare challenge HTML page)
        if not resp.text.strip().startswith("<?xml") and "<rss" not in resp.text[:500]:
            return [{"error": "unavailable", "detail": "Truth Social returned a non-RSS response (possibly a bot-protection page)."}]
        items = _parse_rss_items(resp.text, max_items)
        # trumpstruth.org uses a custom namespace for the canonical Truth Social URL
        NS = "https://truthsocial.com/ns"
        posts = []
        for item in items:
            title = item.findtext("title", "")
            description = item.findtext("description", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            guid = item.findtext("guid", link)

            # Prefer the original Truth Social URL when available (trumpstruth.org feed)
            original_url = item.findtext(f"{{{NS}}}originalUrl", "")
            canonical_url = original_url if original_url else link

            raw = description if description else title
            text = _clean_html(raw)

            posts.append(
                {
                    "id": guid,
                    "text": text or title,
                    "created_at": _parse_date(pub_date),
                    "platform": "Truth Social",
                    "url": canonical_url,
                    "likes": 0,
                    "retweets": 0,
                }
            )
        return posts
    except Exception as e:
        return [{"error": str(e)}]


def demo_posts(name: str, platform: str, count: int = 5) -> list[dict]:
    """Placeholder posts shown when scraping fails."""
    now = datetime.now(timezone.utc)
    handle = HANDLES.get(name, "unknown")
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
                    "Could not reach live data — check network or Nitter instance availability."
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
# High-level fetch-all
# ──────────────────────────────────────────────────────────────────────────────

def fetch_all() -> dict:
    """
    Fetch all posts for both subjects across both platforms.
    Returns a dict ready for JSON serialisation (datetimes as ISO strings).
    Falls back to demo data when scraping fails.
    """
    results: dict[str, dict] = {}

    for name, handle in HANDLES.items():
        tweets = fetch_tweets(handle)
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
