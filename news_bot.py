"""
Bot tin hot GTA 6 → Discord (chạy trên GitHub Actions, ~30 phút/lần).

Nguồn:  Reddit r/GTA6 (top trong ngày) + Google News (Việt & Anh)
Lọc:    - Có ANTHROPIC_API_KEY → Claude chấm điểm độ hot, bỏ tin nhạt/trùng,
          tóm tắt + dịch sang tiếng Việt.
        - Chưa có key → chế độ cơ bản: chỉ đăng bài Reddit cực hot + tin báo Việt.
Đăng:   Webhook Discord (2 kênh: tin chính thức / leak-tin đồn)

Biến môi trường:
  WEBHOOK_OFFICIAL   webhook kênh 📰・tin-chính-thức   (bắt buộc)
  WEBHOOK_RUMOR      webhook kênh 🕵️・leak-tin-đồn     (bắt buộc)
  ANTHROPIC_API_KEY  key Claude API                    (không bắt buộc)
  DRY_RUN=1          chỉ in ra màn hình, không đăng    (để thử)
"""

import html
import json
import os
import re
import time
from urllib.parse import urljoin
from datetime import datetime, timezone

import feedparser
import requests

# ─────────────────────────── CÀI ĐẶT ───────────────────────────
MODEL = os.getenv("MODEL", "claude-sonnet-5-5")
MAX_POSTS_PER_RUN = 3        # tối đa mỗi lần chạy, tránh spam
MIN_HOT_SCORE = 7            # điểm hot tối thiểu (1-10) để được đăng
MIN_REDDIT_SCORE = 1000      # bài Reddit phải có từ chừng này upvote mới xét
BASIC_MODE_REDDIT_SCORE = 3000  # chế độ cơ bản (không AI): ngưỡng cao hơn
MAX_CANDIDATES = 40
STATE_FILE = "state.json"
UA = "GTA6VietNamNewsBot/1.0 (Discord news bot)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

GNEWS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
NEWS_FEEDS = [
    ("vi", GNEWS.format(q="GTA+6+when:1d", hl="vi", gl="VN", ceid="VN:vi")),
    ("en", GNEWS.format(q="%22GTA+6%22+OR+%22GTA+VI%22+when:1d",
                        hl="en-US", gl="US", ceid="US:en")),
]

WEBHOOKS = {
    "official": os.getenv("WEBHOOK_OFFICIAL"),
    "rumor": os.getenv("WEBHOOK_RUMOR"),
}
COLORS = {"official": 0x2ECC71, "rumor": 0xE67E22}
DRY_RUN = os.getenv("DRY_RUN") == "1"


# ─────────────────────────── LƯU TRẠNG THÁI ───────────────────────────
def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"seen": {}, "recent_titles": []}


def save_state(state):
    # chỉ nhớ 7 ngày gần nhất cho file khỏi phình to
    cutoff = time.time() - 7 * 86400
    state["seen"] = {k: v for k, v in state["seen"].items() if v > cutoff}
    state["recent_titles"] = state["recent_titles"][-40:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


# ─────────────────────────── LẤY TIN ───────────────────────────
def reddit_image(p):
    # Bài gắn nhãn leak thì không lấy ảnh (luật server: không đăng file leak)
    if "leak" in (p.get("link_flair_text") or "").lower():
        return None
    if p.get("post_hint") == "image" and p.get("url_overridden_by_dest"):
        return p["url_overridden_by_dest"]
    try:
        return html.unescape(p["preview"]["images"][0]["source"]["url"])
    except (KeyError, IndexError, TypeError):
        return None


def fetch_reddit():
    try:
        r = requests.get("https://www.reddit.com/r/GTA6/top.json",
                         params={"t": "day", "limit": 25},
                         headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"! Reddit lỗi, bỏ qua lần này: {e}")
        return []
    items = []
    for child in r.json().get("data", {}).get("children", []):
        p = child["data"]
        if p.get("stickied") or p.get("over_18"):
            continue
        items.append({
            "id": "reddit_" + p["id"],
            "kind": "reddit",
            "title": p["title"],
            "url": "https://www.reddit.com" + p["permalink"],
            "source": "Reddit r/GTA6",
            "score": p.get("score", 0),
            "comments": p.get("num_comments", 0),
            "flair": p.get("link_flair_text") or "",
            "snippet": (p.get("selftext") or "")[:300],
            "image": reddit_image(p),
        })
    return items


def fetch_news():
    items = []
    for lang, url in NEWS_FEEDS:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"! Google News ({lang}) lỗi, bỏ qua: {e}")
            continue
        for e in feedparser.parse(r.content).entries:
            source = getattr(e, "source", {}).get("title", "Google News")
            title = e.title
            # Google News gắn " - Tên báo" vào cuối tiêu đề, bỏ đi cho gọn
            if title.endswith(" - " + source):
                title = title[: -len(" - " + source)]
            items.append({
                "id": "news_" + (e.get("id") or e.link),
                "kind": "news",
                "lang": lang,
                "title": title,
                "url": e.link,
                "source": source,
                "score": 0,
            })
    return items


# ─────────────────────────── LỌC BẰNG AI ───────────────────────────
SYSTEM_PROMPT = """Bạn là biên tập viên của server Discord "GTA 6 Việt Nam".
Từ danh sách tin ứng viên, chỉ chọn những tin game thủ Việt THẬT SỰ muốn đọc:
thông báo chính thức lớn, tin uy tín về ngày ra mắt/giá/preload/review/server,
phát hiện hoặc khoảnh khắc được cộng đồng upvote cực mạnh, tin đang viral.

BỎ QUA: tin nhỏ, giật tít, bài ý kiến, meme/fanart (trừ khi cực viral), tin trùng
với nhau hoặc trùng với "Tin đã đăng gần đây" (nếu nhiều nguồn cùng một tin, chỉ
chọn nguồn tốt nhất), crack/lậu/"tải GTA 6 PC"/lừa đảo, bài chủ yếu chia sẻ file
hay video leak.

Trả về DUY NHẤT JSON, không markdown, đúng dạng:
{"posts":[{"id":"...","hot":8,"channel":"official","title_vi":"...","summary_vi":"...","spoiler":false}]}

- hot: 1-10. Chỉ đưa vào tin có hot >= %d. Tối đa %d tin, xếp hot nhất trước.
- channel: "official" nếu là tin xác nhận từ Rockstar/Take-Two hoặc báo lớn đưa
  tin chính thức; "rumor" cho leak, insider, tin đồn, chuyện cộng đồng Reddit.
- title_vi: tiêu đề tiếng Việt tự nhiên, cuốn hút nhưng không bịa, dưới 100 ký tự.
- summary_vi: 2-3 câu tiếng Việt kiểu game thủ nói chuyện, CHỈ dựa vào thông tin
  được cung cấp, không bịa thêm chi tiết. Tin đồn thì nói rõ là chưa xác nhận.
- spoiler: true nếu tiết lộ cốt truyện, nhân vật chết, kết thúc...
Nếu không có tin nào đủ hot, trả về {"posts":[]}."""


def ai_select(candidates, recent_titles):
    import anthropic
    client = anthropic.Anthropic()
    payload = {
        "Tin đã đăng gần đây": recent_titles[-20:],
        "Ứng viên": [{k: c[k] for k in ("id", "kind", "title", "source", "score")}
                     | ({"flair": c["flair"], "snippet": c["snippet"]}
                        if c["kind"] == "reddit" else {})
                     for c in candidates],
    }
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT % (MIN_HOT_SCORE, MAX_POSTS_PER_RUN),
        messages=[{"role": "user",
                   "content": json.dumps(payload, ensure_ascii=False)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    text = re.sub(r"```(json)?", "", text).strip()
    posts = json.loads(text).get("posts", [])
    by_id = {c["id"]: c for c in candidates}
    result = []
    for p in posts:
        c = by_id.get(p.get("id"))
        if c and p.get("hot", 0) >= MIN_HOT_SCORE:
            result.append({**c, **p})
    return result[:MAX_POSTS_PER_RUN]


def basic_select(candidates):
    """Chế độ không AI: chỉ lấy bài Reddit cực hot + tin báo Việt."""
    reddit = sorted((c for c in candidates if c["kind"] == "reddit"
                     and c["score"] >= BASIC_MODE_REDDIT_SCORE),
                    key=lambda c: -c["score"])
    news_vi = [c for c in candidates if c["kind"] == "news" and c.get("lang") == "vi"]
    picks = []
    for c in reddit[:2]:
        picks.append({**c, "channel": "rumor", "title_vi": c["title"],
                      "summary_vi": c.get("snippet", ""), "hot": 0})
    for c in news_vi[:1]:
        picks.append({**c, "channel": "official", "title_vi": c["title"],
                      "summary_vi": "", "hot": 0})
    return picks[:MAX_POSTS_PER_RUN]


# ─────────────────────────── LÀM ĐẸP TIN ───────────────────────────
def resolve_url(url):
    """Link Google News là link chuyển hướng → đổi về link bài báo thật."""
    if "news.google.com" not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder
        res = gnewsdecoder(url, interval=1)
        if res.get("status"):
            return res["decoded_url"]
    except Exception as e:
        print(f"! Không giải mã được link Google News: {e}")
    return url


def meta(page, name):
    tag = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*>' % re.escape(name),
                    page, re.I)
    if not tag:
        return None
    content = re.search(r'content=["\']([^"\']+)["\']', tag.group(0), re.I)
    return html.unescape(content.group(1)).strip() if content else None


def enrich(item):
    """Lấy ảnh bìa + đoạn mô tả từ bài báo gốc (không được thì bỏ qua)."""
    if item["kind"] != "news":
        return
    url = resolve_url(item["url"])
    if "news.google.com" in url:
        return
    item["url"] = url
    try:
        r = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"! Không đọc được bài gốc: {e}")
        return
    page = r.text[:400000]
    img = meta(page, "og:image") or meta(page, "twitter:image")
    if img:
        item["image"] = urljoin(r.url, img)
    desc = meta(page, "og:description") or meta(page, "description")
    if desc:
        item["og_desc"] = desc if len(desc) <= 350 else desc[:347].rsplit(" ", 1)[0] + "…"


# ─────────────────────────── ĐĂNG LÊN DISCORD ───────────────────────────
LABELS = {"official": "📰 TIN CHÍNH THỨC", "rumor": "🕵️ TIN ĐỒN • CỘNG ĐỒNG"}


def post_to_discord(item):
    channel = item.get("channel", "rumor")
    title = item["title_vi"]
    desc = item.get("summary_vi") or item.get("og_desc") or ""
    if item.get("spoiler"):
        title = "⚠️ [CÓ SPOIL] " + title
        desc = f"||{desc}||" if desc else ""
    footer = item["source"]
    if item.get("hot"):
        footer += f" • 🔥 Độ hot {item['hot']}/10"
    embed = {
        "author": {"name": LABELS.get(channel, "📰 TIN GTA 6")},
        "title": title[:256],
        "url": item["url"],
        "description": desc[:4000],
        "color": COLORS.get(channel, 0x95A5A6),
        "footer": {"text": footer},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # Tin có spoil thì không gắn ảnh, tránh lộ nội dung
    if item.get("image") and not item.get("spoiler"):
        embed["image"] = {"url": item["image"]}
    if item["kind"] == "reddit":
        embed["fields"] = [
            {"name": "🔺 Upvote", "value": f"{item['score']:,}", "inline": True},
            {"name": "💬 Bình luận", "value": f"{item.get('comments', 0):,}", "inline": True},
        ]
    if DRY_RUN:
        print(f"[DRY RUN → {channel}] {json.dumps(embed, ensure_ascii=False)}")
        return
    url = WEBHOOKS.get(channel)
    if not url:
        print(f"! Thiếu webhook cho kênh {channel}")
        return
    r = requests.post(url, json={"username": "GTA 6 News", "embeds": [embed]},
                      timeout=20)
    if r.status_code >= 300:
        print(f"! Discord lỗi {r.status_code}: {r.text[:200]}")
    time.sleep(1.5)


# ─────────────────────────── CHẠY ───────────────────────────
def main():
    state = load_state()
    fetched = fetch_reddit() + fetch_news()

    candidates = []
    for c in fetched:
        if c["id"] in state["seen"]:
            continue
        # Bài Reddit chưa đủ upvote thì để lần sau xét lại (có thể sẽ hot lên)
        if c["kind"] == "reddit" and c["score"] < MIN_REDDIT_SCORE:
            continue
        candidates.append(c)

    # Reddit hot nhất trước, sau đó tới tin báo
    candidates.sort(key=lambda c: (c["kind"] != "reddit", -c["score"]))
    candidates = candidates[:MAX_CANDIDATES]
    print(f"Lấy được {len(fetched)} tin, {len(candidates)} tin mới cần xét.")

    if candidates:
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                picks = ai_select(candidates, state["recent_titles"])
            except Exception as e:  # AI lỗi thì lần sau thử lại, không đánh dấu đã xem
                print(f"! AI lỗi, thử lại lần sau: {e}")
                return
        else:
            print("(Chưa có API key → chế độ cơ bản)")
            picks = basic_select(candidates)

        for item in picks:
            enrich(item)
            post_to_discord(item)
            state["recent_titles"].append(item["title_vi"])
            print(f"+ Đã đăng: {item['title_vi']}")

        now = time.time()
        for c in candidates:
            state["seen"][c["id"]] = now
        # tin không lọt vào top MAX_CANDIDATES cũng đánh dấu luôn, tránh dồn ứ
        for c in fetched:
            if c["kind"] == "news":
                state["seen"].setdefault(c["id"], now)

    save_state(state)
    print("Xong.")


if __name__ == "__main__":
    main()
