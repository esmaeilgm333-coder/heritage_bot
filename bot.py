import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE = "seen.json"
MAX_AGE_DAYS = 3      # خبرهای قدیمی‌تر از این نادیده گرفته می‌شن
MAX_PER_RUN = 20      # حداکثر تعداد پیام در هر اجرا

# کلمات جستجو: هر خط یک جستجوی جدا. می‌تونید خطی اضافه یا کم کنید.
QUERIES = [
    "باستان شناسی آذربایجان شرقی",
    "باستان شناسی آذربایجان غربی",
    "میراث فرهنگی آذربایجان شرقی",
    "میراث فرهنگی آذربایجان غربی",
    "میراث فرهنگی تبریز",
    "میراث فرهنگی ارومیه",
    "کاوش باستان شناسی آذربایجان",
    "تخت سلیمان تکاب",
    "اداره کل میراث فرهنگی آذربایجان",
]


def feed_url(q):
    params = {"q": q, "hl": "fa", "gl": "IR", "ceid": "IR:fa"}
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)


def fetch(q):
    req = urllib.request.Request(feed_url(q), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        try:
            dt = parsedate_to_datetime(it.findtext("pubDate"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
        if link:
            items.append((link, title, dt))
    return items


def send(text):
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
            return r.status == 200
    except Exception as e:
        print("send error:", e)
        return False


def main():
    first_run = not os.path.exists(SEEN_FILE)
    seen = []
    if not first_run:
        with open(SEEN_FILE, encoding="utf-8") as f:
            seen = json.load(f)
    seen_set = set(seen)

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    found = {}
    for q in QUERIES:
        try:
            for link, title, dt in fetch(q):
                if link not in seen_set and dt >= cutoff:
                    found[link] = (title, dt)
        except Exception as e:
            print("fetch error:", q, e)

    items = sorted(found.items(), key=lambda x: x[1][1])  # قدیمی‌ترین اول

    if first_run:
        # بار اول: همه رو فقط علامت می‌زنیم تا سیل پیام نیاد
        seen.extend(link for link, _ in items)
        send("ربات اخبار میراث و باستان‌شناسی آذربایجان فعال شد ✅")
    else:
        for link, (title, _) in items[:MAX_PER_RUN]:
            if send(f"{title}\n{link}"):
                seen.append(link)
            time.sleep(1)

    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[-3000:], f, ensure_ascii=False)


if __name__ == "__main__":
    main()
