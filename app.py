"""
TRACKTWO — Social Media Tracker (Streamlit UI)
"""

import html
from datetime import datetime, timedelta, timezone

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from scraper import (
    HANDLES,
    USERS,
    RECENT_THRESHOLD,
    fetch_tweets,
    fetch_truth_social,
    demo_posts,
)

REFRESH_INTERVAL_MS = 60_000  # 1 minute

# ──────────────────────────────────────────────────────────────────────────────
# UI helpers
# ──────────────────────────────────────────────────────────────────────────────

def is_recent(post: dict) -> bool:
    now = datetime.now(timezone.utc)
    dt = post["created_at"]
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return (now - dt) < RECENT_THRESHOLD


def format_time_ago(dt) -> str:
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    now = datetime.now(timezone.utc)
    secs = int((now - dt).total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def render_post_card(post: dict, platform_icon: str = ""):
    if "error" in post:
        st.error(f"Error: {post['error']}")
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
            <div style="font-size:0.75rem; color:#888; margin-bottom:6px;">
                {platform_icon} {time_str}{badge}
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
    valid = [p for p in all_posts if "error" not in p]
    valid.sort(
        key=lambda p: datetime.fromisoformat(p["created_at"])
        if isinstance(p["created_at"], str)
        else p["created_at"],
        reverse=True,
    )

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
        dt = post["created_at"]
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        abs_time = dt.strftime("%Y-%m-%d %H:%M UTC")

        st.markdown(
            f"""
            <div style="display:flex; gap:12px; margin-bottom:12px;">
                <div style="display:flex; flex-direction:column; align-items:center; min-width:20px;">
                    <div style="font-size:1.2rem;">{icon}</div>
                    <div style="flex:1; width:2px; background:{border}; margin-top:4px;"></div>
                </div>
                <div style="flex:1; border-left:3px solid {border}; background:{bg}; border-radius:6px; padding:10px 14px;">
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
# Page setup
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TRACKTWO",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0d0d0d; color: #e0e0e0;
    }
    [data-testid="stHeader"] { background: #0d0d0d; }
    .block-container { padding-top: 1rem; }
    h1, h2, h3 { color: #ffffff; }
    .platform-header {
        font-size: 1.1rem; font-weight: 700;
        padding: 6px 0 10px 0; border-bottom: 2px solid #333; margin-bottom: 12px;
    }
    .quadrant-box {
        background: #141414; border: 1px solid #2a2a2a;
        border-radius: 10px; padding: 16px; height: 420px; overflow-y: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

count = st_autorefresh(interval=REFRESH_INTERVAL_MS, key="auto_refresh")

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

# ── Fetch ────────────────────────────────────────────────────────────────────

with st.spinner("Fetching posts..."):
    hegseth_tweets = fetch_tweets(USERS["Pete Hegseth"]["handle"], USERS["Pete Hegseth"]["id"])
    trump_tweets   = fetch_tweets(USERS["Donald Trump"]["handle"],  USERS["Donald Trump"]["id"])
    hegseth_truth  = fetch_truth_social("Pete Hegseth")
    trump_truth    = fetch_truth_social("Donald Trump")

def _or_demo(posts, name, platform):
    if not posts or (len(posts) == 1 and "error" in posts[0]):
        return demo_posts(name, platform)
    return posts

hegseth_tweets = _or_demo(hegseth_tweets, "Pete Hegseth", "Twitter/X")
trump_tweets   = _or_demo(trump_tweets,   "Donald Trump",  "Twitter/X")
hegseth_truth  = _or_demo(hegseth_truth,  "Pete Hegseth",  "Truth Social")
trump_truth    = _or_demo(trump_truth,    "Donald Trump",  "Truth Social")

for p in hegseth_tweets: p["author"] = "Pete Hegseth"
for p in trump_tweets:   p["author"] = "Donald Trump"
for p in hegseth_truth:  p["author"] = "Pete Hegseth"
for p in trump_truth:    p["author"] = "Donald Trump"

# ── Timestamp ────────────────────────────────────────────────────────────────

st.markdown(
    f"<div style='text-align:right; color:#555; font-size:0.75rem; margin-bottom:12px;'>"
    f"Last refreshed: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
    f"</div>",
    unsafe_allow_html=True,
)

# ── 4 Quadrants ──────────────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.markdown("<div class='platform-header'>🐦 Pete Hegseth — Twitter/X</div>", unsafe_allow_html=True)
    with st.container():
        st.markdown("<div class='quadrant-box'>", unsafe_allow_html=True)
        render_feed(hegseth_tweets, "🐦")
        st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='platform-header'>🐦 Donald Trump — Twitter/X</div>", unsafe_allow_html=True)
    with st.container():
        st.markdown("<div class='quadrant-box'>", unsafe_allow_html=True)
        render_feed(trump_tweets, "🐦")
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
col3, col4 = st.columns(2)

with col3:
    st.markdown("<div class='platform-header'>🟠 Pete Hegseth — Truth Social</div>", unsafe_allow_html=True)
    with st.container():
        st.markdown("<div class='quadrant-box'>", unsafe_allow_html=True)
        render_feed(hegseth_truth, "🟠")
        st.markdown("</div>", unsafe_allow_html=True)

with col4:
    st.markdown("<div class='platform-header'>🟠 Donald Trump — Truth Social</div>", unsafe_allow_html=True)
    with st.container():
        st.markdown("<div class='quadrant-box'>", unsafe_allow_html=True)
        render_feed(trump_truth, "🟠")
        st.markdown("</div>", unsafe_allow_html=True)

# ── Timeline ─────────────────────────────────────────────────────────────────

st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='platform-header' style='font-size:1.2rem; border-bottom:2px solid #444;'>"
    "📋 Combined Timeline</div>",
    unsafe_allow_html=True,
)

all_posts = hegseth_tweets + trump_tweets + hegseth_truth + trump_truth
render_timeline(all_posts)
