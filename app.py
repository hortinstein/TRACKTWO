"""
TRACKTWO — Social Media Tracker
Tracks Pete Hegseth & Donald Trump across Twitter/X and Truth Social.
"""

import os
import time
import html
from datetime import datetime, timezone, timedelta

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# Twitter user IDs (stable even if handles change)
TWITTER_USERS = {
    "Pete Hegseth": {"handle": "PeteHegseth", "id": "34685502"},
    "Donald Trump": {"handle": "realDonaldTrump", "id": "25073877"},
}

# Truth Social RSS feeds
TRUTH_SOCIAL_RSS = {
    "Pete Hegseth": "https://truthsocial.com/@PeteHegseth/feed.rss",
    "Donald Trump": "https://truthsocial.com/@realDonaldTrump/feed.rss",
}

REFRESH_INTERVAL_MS = 60_000  # 1 minute
RECENT_THRESHOLD = timedelta(hours=1)

# ──────────────────────────────────────────────────────────────────────────────
# Data fetching
# ──────────────────────────────────────────────────────────────────────────────

def fetch_tweets(user_id: str, handle: str, max_results: int = 10) -> list[dict]:
    """Fetch recent tweets via Twitter API v2."""
    if not TWITTER_BEARER_TOKEN:
        return []

    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    params = {
        "max_results": max_results,
        "tweet.fields": "created_at,text,public_metrics",
        "expansions": "author_id",
        "exclude": "retweets,replies",
    }
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

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
    """Fetch Truth Social posts via RSS feed using stdlib XML parser."""
    feed_url = TRUTH_SOCIAL_RSS[name]
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; TRACKTWO/1.0)"}
        resp = requests.get(feed_url, headers=headers, timeout=10)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        posts = []
        for item in items[:max_items]:
            title = item.findtext("title", "")
            description = item.findtext("description", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            guid = item.findtext("guid", link)

            # Parse date
            try:
                created_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc)
            except Exception:
                created_at = datetime.now(timezone.utc)

            # Use description if available, else title; strip HTML
            raw = description if description else title
            text = html.unescape(raw)
            text = re.sub(r"<[^>]+>", "", text).strip()

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


# ──────────────────────────────────────────────────────────────────────────────
# UI helpers
# ──────────────────────────────────────────────────────────────────────────────

def is_recent(post: dict) -> bool:
    now = datetime.now(timezone.utc)
    return (now - post["created_at"]) < RECENT_THRESHOLD


def format_time_ago(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def render_post_card(post: dict, platform_icon: str = ""):
    if "error" in post:
        st.error(f"Error fetching posts: {post['error']}")
        return

    recent = is_recent(post)
    time_str = format_time_ago(post["created_at"])

    border_color = "#ff4444" if recent else "#333333"
    bg_color = "#2a0a0a" if recent else "#1a1a1a"
    badge = " 🔴 LIVE" if recent else ""

    st.markdown(
        f"""
        <div style="
            border-left: 4px solid {border_color};
            background: {bg_color};
            border-radius: 6px;
            padding: 10px 14px;
            margin-bottom: 10px;
        ">
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                <span style="font-size:0.75rem; color:#888;">{platform_icon} {time_str}{badge}</span>
            </div>
            <div style="font-size:0.9rem; color:#e0e0e0; line-height:1.5;">
                {html.escape(post['text'])}
            </div>
            {"<div style='margin-top:6px;'><a href='" + post['url'] + "' target='_blank' style='font-size:0.75rem; color:#4a9eff;'>View post →</a></div>" if post.get('url') else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feed(posts: list[dict], platform_icon: str = ""):
    if not posts:
        st.info("No posts to display.")
        return
    for post in posts:
        render_post_card(post, platform_icon)


def render_timeline(all_posts: list[dict]):
    """Render a merged chronological timeline of all posts."""
    valid = [p for p in all_posts if "error" not in p]
    valid.sort(key=lambda p: p["created_at"], reverse=True)

    if not valid:
        st.info("No posts available for timeline.")
        return

    for post in valid:
        recent = is_recent(post)
        border = "#ff4444" if recent else "#555"
        bg = "#2a0a0a" if recent else "#111"
        badge = " 🔴" if recent else ""
        icon = "🐦" if post["platform"] == "Twitter/X" else "🟠"
        name = post.get("author", "")
        time_str = format_time_ago(post["created_at"])
        abs_time = post["created_at"].strftime("%Y-%m-%d %H:%M UTC")

        st.markdown(
            f"""
            <div style="
                display:flex;
                gap:12px;
                margin-bottom:12px;
            ">
                <div style="
                    display:flex;
                    flex-direction:column;
                    align-items:center;
                    min-width:20px;
                ">
                    <div style="font-size:1.2rem;">{icon}</div>
                    <div style="flex:1; width:2px; background:{border}; margin-top:4px;"></div>
                </div>
                <div style="
                    flex:1;
                    border-left: 3px solid {border};
                    background: {bg};
                    border-radius:6px;
                    padding:10px 14px;
                ">
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span style="color:#aaa; font-size:0.75rem; font-weight:600;">
                            {name} · {post['platform']}{badge}
                        </span>
                        <span style="color:#666; font-size:0.75rem;" title="{abs_time}">{time_str}</span>
                    </div>
                    <div style="color:#ddd; font-size:0.88rem; line-height:1.5;">
                        {html.escape(post['text'])}
                    </div>
                    {"<div style='margin-top:6px;'><a href='" + post['url'] + "' target='_blank' style='font-size:0.72rem; color:#4a9eff;'>View →</a></div>" if post.get('url') else ""}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Demo / fallback data
# ──────────────────────────────────────────────────────────────────────────────

def demo_posts(name: str, platform: str, count: int = 5) -> list[dict]:
    """Return placeholder posts when API is unavailable."""
    now = datetime.now(timezone.utc)
    handle_map = {
        ("Pete Hegseth", "Twitter/X"): "PeteHegseth",
        ("Donald Trump", "Twitter/X"): "realDonaldTrump",
        ("Pete Hegseth", "Truth Social"): "PeteHegseth",
        ("Donald Trump", "Truth Social"): "realDonaldTrump",
    }
    handle = handle_map.get((name, platform), "unknown")
    demo = []
    for i in range(count):
        offset = timedelta(minutes=i * 25)
        created = now - offset
        if platform == "Twitter/X":
            url = f"https://x.com/{handle}/status/demo{i}"
        else:
            url = f"https://truthsocial.com/@{handle}"
        demo.append(
            {
                "id": f"demo-{name}-{platform}-{i}",
                "text": (
                    f"[Demo] This is a sample {platform} post #{i+1} from {name}. "
                    "Set TWITTER_BEARER_TOKEN in .env to see real tweets. "
                    "Truth Social posts load via RSS automatically."
                ),
                "created_at": created,
                "platform": platform,
                "url": url,
                "author": name,
                "likes": 0,
                "retweets": 0,
            }
        )
    return demo


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TRACKTWO",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Dark theme overrides
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0d0d0d;
        color: #e0e0e0;
    }
    [data-testid="stHeader"] { background: #0d0d0d; }
    .block-container { padding-top: 1rem; }
    h1, h2, h3 { color: #ffffff; }
    .platform-header {
        font-size: 1.1rem;
        font-weight: 700;
        padding: 6px 0 10px 0;
        border-bottom: 2px solid #333;
        margin-bottom: 12px;
    }
    .quadrant-box {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 10px;
        padding: 16px;
        height: 420px;
        overflow-y: auto;
    }
    .stInfo { background: #1a1a2e; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Auto-refresh every 60 seconds
count = st_autorefresh(interval=REFRESH_INTERVAL_MS, key="auto_refresh")

# Header
st.markdown(
    """
    <div style="text-align:center; padding: 10px 0 20px 0;">
        <h1 style="margin:0; font-size:2rem; letter-spacing:3px;">📡 TRACKTWO</h1>
        <p style="color:#666; margin:4px 0 0 0; font-size:0.85rem;">
            Live social media tracker · Auto-refreshes every 60s · 🔴 = posted in the last hour
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Fetch all data ──────────────────────────────────────────────────────────

with st.spinner("Fetching posts..."):
    # Twitter
    hegseth_tweets = fetch_tweets(
        TWITTER_USERS["Pete Hegseth"]["id"],
        TWITTER_USERS["Pete Hegseth"]["handle"],
    )
    trump_tweets = fetch_tweets(
        TWITTER_USERS["Donald Trump"]["id"],
        TWITTER_USERS["Donald Trump"]["handle"],
    )

    # Truth Social
    hegseth_truth = fetch_truth_social("Pete Hegseth")
    trump_truth = fetch_truth_social("Donald Trump")

# Fall back to demo data if APIs are unavailable
if not hegseth_tweets or (len(hegseth_tweets) == 1 and "error" in hegseth_tweets[0]):
    hegseth_tweets = demo_posts("Pete Hegseth", "Twitter/X")
if not trump_tweets or (len(trump_tweets) == 1 and "error" in trump_tweets[0]):
    trump_tweets = demo_posts("Donald Trump", "Twitter/X")
if not hegseth_truth or (len(hegseth_truth) == 1 and "error" in hegseth_truth[0]):
    hegseth_truth = demo_posts("Pete Hegseth", "Truth Social")
if not trump_truth or (len(trump_truth) == 1 and "error" in trump_truth[0]):
    trump_truth = demo_posts("Donald Trump", "Truth Social")

# Tag author onto each post for timeline
for p in hegseth_tweets:
    p["author"] = "Pete Hegseth"
for p in trump_tweets:
    p["author"] = "Donald Trump"
for p in hegseth_truth:
    p["author"] = "Pete Hegseth"
for p in trump_truth:
    p["author"] = "Donald Trump"

# ── Last refresh timestamp ──────────────────────────────────────────────────

st.markdown(
    f"<div style='text-align:right; color:#555; font-size:0.75rem; margin-bottom:12px;'>"
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
    f"</div>",
    unsafe_allow_html=True,
)

# ── 4 Quadrants ────────────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        "<div class='platform-header'>🐦 Pete Hegseth — Twitter/X</div>",
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown("<div class='quadrant-box'>", unsafe_allow_html=True)
        render_feed(hegseth_tweets, "🐦")
        st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown(
        "<div class='platform-header'>🐦 Donald Trump — Twitter/X</div>",
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown("<div class='quadrant-box'>", unsafe_allow_html=True)
        render_feed(trump_tweets, "🐦")
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

col3, col4 = st.columns(2)

with col3:
    st.markdown(
        "<div class='platform-header'>🟠 Pete Hegseth — Truth Social</div>",
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown("<div class='quadrant-box'>", unsafe_allow_html=True)
        render_feed(hegseth_truth, "🟠")
        st.markdown("</div>", unsafe_allow_html=True)

with col4:
    st.markdown(
        "<div class='platform-header'>🟠 Donald Trump — Truth Social</div>",
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown("<div class='quadrant-box'>", unsafe_allow_html=True)
        render_feed(trump_truth, "🟠")
        st.markdown("</div>", unsafe_allow_html=True)

# ── Combined Timeline ───────────────────────────────────────────────────────

st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='platform-header' style='font-size:1.2rem; border-bottom: 2px solid #444;'>"
    "📋 Combined Timeline"
    "</div>",
    unsafe_allow_html=True,
)

all_posts = hegseth_tweets + trump_tweets + hegseth_truth + trump_truth
render_timeline(all_posts)
