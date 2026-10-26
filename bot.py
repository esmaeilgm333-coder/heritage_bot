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
MAX_AGE_DAYS = 7
MAX_PER_RUN = 20

QUERIES = [
    "میراث فرهنگی آذربایجان شرقی",
    "میراث فرهنگی آذربایجان غربی",
    "باستان شناسی آذربایجان",
    "کاوش باستان شناسی تبریز",
    "کاوش باستان شناسی ارومیه",
    "میراث فرهنگی تبریز",
    "میراث فرهنگی ارومیه",
    "تخت سلیمان تکاب",
    "بازار تاریخی تبریز",
    "ثبت جهانی آذربایجان",
    "اداره کل میراث فرهنگی آذربایجان",
]


def sources(q):
    google = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "fa", "gl": "IR", "ceid": "IR:fa"}
    )
    bing = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": q, "format": "rss", "setlang": "fa-IR"}
    )
    return [("google", google), ("bing", bing)]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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
    titles = set()
    for q in QUERIES:
        for name, url in sources(q):
            try:
                items = fetch(url)
                fresh = 0
                for link, title, dt in items:
                    key = title.split(" - ")[0].strip()
                    if link in seen_set or dt < cutoff or key in titles:
                        continue
                    titles.add(key)
                    found[link] = (title, dt)
                    fresh += 1
                print(f"{name} | {q}: {len(items)} items, {fresh} new")
            except Exception as e:
                print("fetch error:", name, q, e)

    items = sorted(found.items(), key=lambda x: x[1][1])
    print("to send:", len(items))

    if first_run:
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
