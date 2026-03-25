"""
scraper.py — shared data fetching for TRACKTWO.
Used by both app.py (Streamlit UI) and api.py (JSON endpoint).

No API keys required.
- Twitter/X: scraped via Twitter's own guest-token GraphQL API
- Truth Social: scraped via public RSS feed
"""

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

# Stable numeric user IDs — won't change even if handles do
USERS = {
    "Pete Hegseth": {"handle": "PeteHegseth",      "id": "34685502"},
    "Donald Trump":  {"handle": "realDonaldTrump",  "id": "25073877"},
}

HANDLES = {name: info["handle"] for name, info in USERS.items()}

TRUTH_SOCIAL_RSS = {
    "Pete Hegseth": "https://truthsocial.com/@PeteHegseth/feed.rss",
    "Donald Trump":  "https://truthsocial.com/@realDonaldTrump/feed.rss",
}

RECENT_THRESHOLD = timedelta(hours=1)

# Twitter's public web bearer token (embedded in twitter.com's own JS bundle)
_TW_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Known UserTweets GraphQL query IDs — try each until one works.
# Twitter rotates these with deploys; dynamic discovery updates the list at runtime.
_TW_QUERY_IDS = [
    "E3opETHurmVJflFsUBVuUQ",   # 2024 known value
    "H8OjXpWSvT7UeSLgIdGpFA",   # 2023 fallback
    "V7H0Ap3_Hh2FyS75OCDO3Q",   # older fallback
]

# Minimal feature flags required by UserTweets
_TW_FEATURES = json.dumps({
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}, separators=(",", ":"))

# Nitter instances as a secondary fallback (many are down, kept as last resort)
_NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.net",
    "https://nitter.1d4.us",
]

# ──────────────────────────────────────────────────────────────────────────────
# Twitter guest-token helpers
# ──────────────────────────────────────────────────────────────────────────────

def _activate_guest_token() -> str:
    """Obtain a short-lived guest token from Twitter's activation endpoint."""
    resp = requests.post(
        "https://api.twitter.com/1.1/guest/activate.json",
        headers={"Authorization": f"Bearer {_TW_BEARER}", "User-Agent": _UA},
        timeout=8,
    )
    resp.raise_for_status()
    return resp.json()["guest_token"]


def _guest_headers(guest_token: str) -> dict:
    return {
        "Authorization": f"Bearer {_TW_BEARER}",
        "X-Guest-Token": guest_token,
        "User-Agent": _UA,
        "X-Twitter-Active-User": "yes",
        "X-Twitter-Client-Language": "en",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _discover_query_id() -> str | None:
    """
    Try to extract the current UserTweets queryId from Twitter's JS bundle.
    Returns None if discovery fails (callers fall back to _TW_QUERY_IDS).
    """
    try:
        page = requests.get(
            "https://twitter.com/home",
            headers={"User-Agent": _UA},
            timeout=10,
            allow_redirects=True,
        )
        # Find main JS bundle URL
        match = re.search(
            r'"(https://abs\.twimg\.com/responsive-web/client-web/main\.[a-f0-9]+\.js)"',
            page.text,
        )
        if not match:
            return None
        bundle = requests.get(match.group(1), headers={"User-Agent": _UA}, timeout=15)
        qid = re.search(r'queryId:"([^"]+)",operationName:"UserTweets"', bundle.text)
        return qid.group(1) if qid else None
    except Exception:
        return None


def _parse_tweet_timeline(data: dict, handle: str) -> list[dict]:
    """Walk Twitter's deeply nested GraphQL response and extract tweets."""
    posts = []
    try:
        instructions = (
            data["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]
        )
        for instruction in instructions:
            entries = instruction.get("entries", [])
            for entry in entries:
                content = entry.get("content", {})
                item_content = content.get("itemContent", {})
                tweet_results = item_content.get("tweet_results", {}).get("result", {})

                # Skip non-tweet entries (cursors, promotions, etc.)
                if tweet_results.get("__typename") not in ("Tweet", "TweetWithVisibilityResults"):
                    continue

                # TweetWithVisibilityResults wraps the actual tweet
                if tweet_results.get("__typename") == "TweetWithVisibilityResults":
                    tweet_results = tweet_results.get("tweet", {})

                core = tweet_results.get("core", {})
                legacy = tweet_results.get("legacy", {})
                if not legacy:
                    continue

                # Skip retweets and replies
                if legacy.get("retweeted_status_id_str") or legacy.get("in_reply_to_status_id_str"):
                    continue

                tweet_id = legacy.get("id_str", "")
                text = legacy.get("full_text", legacy.get("text", ""))
                created_raw = legacy.get("created_at", "")

                try:
                    created_at = datetime.strptime(
                        created_raw, "%a %b %d %H:%M:%S +0000 %Y"
                    ).replace(tzinfo=timezone.utc)
                except Exception:
                    created_at = datetime.now(timezone.utc)

                metrics = legacy.get("public_metrics") or {}
                posts.append({
                    "id": tweet_id,
                    "text": text,
                    "created_at": created_at,
                    "platform": "Twitter/X",
                    "url": f"https://x.com/{handle}/status/{tweet_id}",
                    "likes": legacy.get("favorite_count", 0),
                    "retweets": legacy.get("retweet_count", 0),
                })
    except (KeyError, TypeError):
        pass
    return posts


# ──────────────────────────────────────────────────────────────────────────────
# Public fetchers
# ──────────────────────────────────────────────────────────────────────────────

def fetch_tweets(handle: str, user_id: str, max_items: int = 10) -> list[dict]:
    """
    Fetch recent tweets without an API key using Twitter's guest GraphQL API.
    Falls back to Nitter RSS if the guest API is unavailable.
    """
    # 1. Try Twitter guest GraphQL API
    try:
        guest_token = _activate_guest_token()
        headers = _guest_headers(guest_token)

        # Try known query IDs + optionally a freshly discovered one
        discovered = _discover_query_id()
        query_ids = ([discovered] if discovered else []) + _TW_QUERY_IDS

        variables = json.dumps({
            "userId": user_id,
            "count": max_items,
            "includePromotedContent": False,
            "withQuickPromoteEligibilityTweetFields": True,
            "withVoice": True,
            "withV2Timeline": True,
        }, separators=(",", ":"))

        for qid in query_ids:
            try:
                resp = requests.get(
                    f"https://api.twitter.com/graphql/{qid}/UserTweets",
                    params={"variables": variables, "features": _TW_FEATURES},
                    headers=headers,
                    timeout=10,
                )
                if resp.status_code == 200:
                    posts = _parse_tweet_timeline(resp.json(), handle)
                    if posts:
                        return posts
            except Exception:
                continue
    except Exception:
        pass

    # 2. Fallback: Nitter RSS
    return _fetch_tweets_nitter(handle, max_items)


def _fetch_tweets_nitter(handle: str, max_items: int = 10) -> list[dict]:
    """Secondary fallback: scrape a Nitter RSS feed."""
    headers = {"User-Agent": _UA}
    last_error = ""
    for instance in _NITTER_INSTANCES:
        try:
            resp = requests.get(
                f"{instance}/{handle}/rss", headers=headers, timeout=8
            )
            resp.raise_for_status()
            posts = _parse_rss(resp.text, "Twitter/X", handle, max_items)
            if posts:
                return posts
        except Exception as e:
            last_error = str(e)
            continue
    return [{"error": f"Twitter guest API and all Nitter instances failed. Last: {last_error}"}]


def fetch_truth_social(name: str, max_items: int = 10) -> list[dict]:
    """Fetch Truth Social posts via public RSS feed."""
    try:
        resp = requests.get(
            TRUTH_SOCIAL_RSS[name],
            headers={"User-Agent": _UA},
            timeout=10,
        )
        resp.raise_for_status()
        return _parse_rss(resp.text, "Truth Social", None, max_items)
    except Exception as e:
        return [{"error": str(e)}]


# ──────────────────────────────────────────────────────────────────────────────
# RSS parsing
# ──────────────────────────────────────────────────────────────────────────────

def _parse_rss(xml_text: str, platform: str, handle: str | None, max_items: int) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    items = (channel.findall("item") if channel is not None else root.findall(".//item"))
    posts = []
    for item in items[:max_items]:
        title       = item.findtext("title", "")
        description = item.findtext("description", "")
        link        = item.findtext("link", "")
        pub_date    = item.findtext("pubDate", "")
        guid        = item.findtext("guid", link)

        # Rewrite Nitter links → canonical x.com links
        if platform == "Twitter/X" and handle:
            link = re.sub(
                r"https?://[^/]+/([^/]+/status/\d+)",
                r"https://x.com/\1",
                link,
            )

        try:
            created_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc)
        except Exception:
            created_at = datetime.now(timezone.utc)

        raw  = description if description else title
        text = re.sub(r"<[^>]+>", "", html.unescape(raw)).strip()

        posts.append({
            "id":         guid,
            "text":       text or title,
            "created_at": created_at,
            "platform":   platform,
            "url":        link,
            "likes":      0,
            "retweets":   0,
        })
    return posts


# ──────────────────────────────────────────────────────────────────────────────
# Demo / placeholder data
# ──────────────────────────────────────────────────────────────────────────────

def demo_posts(name: str, platform: str, count: int = 5) -> list[dict]:
    now    = datetime.now(timezone.utc)
    handle = HANDLES.get(name, "unknown")
    posts  = []
    for i in range(count):
        created = now - timedelta(minutes=i * 25)
        url = (
            f"https://x.com/{handle}/status/demo{i}"
            if platform == "Twitter/X"
            else f"https://truthsocial.com/@{handle}"
        )
        posts.append({
            "id":         f"demo-{name}-{platform}-{i}",
            "text":       (
                f"[Demo] Could not reach live {platform} data for {name}. "
                "Check network connectivity or see README for troubleshooting."
            ),
            "created_at": created,
            "platform":   platform,
            "url":        url,
            "author":     name,
            "likes":      0,
            "retweets":   0,
        })
    return posts


# ──────────────────────────────────────────────────────────────────────────────
# High-level fetch-all
# ──────────────────────────────────────────────────────────────────────────────

def fetch_all() -> dict:
    results: dict[str, dict] = {}

    for name, info in USERS.items():
        tweets = fetch_tweets(info["handle"], info["id"])
        if not tweets or (len(tweets) == 1 and "error" in tweets[0]):
            tweets = demo_posts(name, "Twitter/X")

        truth = fetch_truth_social(name)
        if not truth or (len(truth) == 1 and "error" in truth[0]):
            truth = demo_posts(name, "Truth Social")

        for p in tweets + truth:
            p["author"] = name

        results[name] = {
            "twitter":      _serialise(tweets),
            "truth_social": _serialise(truth),
        }

    all_posts = []
    for person in results.values():
        all_posts.extend(person["twitter"])
        all_posts.extend(person["truth_social"])
    all_posts.sort(key=lambda p: p["created_at"], reverse=True)

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "subjects":   results,
        "timeline":   all_posts,
    }


def _serialise(posts: list[dict]) -> list[dict]:
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
