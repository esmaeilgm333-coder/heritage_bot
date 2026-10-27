import json
import os
import re
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
    "میراث فرهنگی اردبیل",
    "باستان شناسی اردبیل",
    "شیخ صفی الدین اردبیل",
    "میراث فرهنگی زنجان",
    "باستان شناسی زنجان",
    "گنبد سلطانیه",
    "میراث فرهنگی مراغه",
    "میراث فرهنگی خوی",
    "میراث فرهنگی مرند",
    "میراث فرهنگی جلفا",
    "میراث فرهنگی اهر",
    "میراث فرهنگی سراب",
    "میراث فرهنگی میانه",
    "میراث فرهنگی ماکو",
    "میراث فرهنگی سلماس",
    "میراث فرهنگی مشگین شهر",
    "میراث فرهنگی بناب",
    "ارسباران میراث فرهنگی",
]


def sources(q):
    google = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "fa", "gl": "IR", "ceid": "IR:fa"}
    )
    bing = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": q, "format": "rss", "setlang": "fa-IR"}
    )
    return [("google", google), ("bing", bing)]


def clean_link(link):
    try:
        p = urllib.parse.urlparse(link)
        if "bing.com" in p.netloc:
            u = urllib.parse.parse_qs(p.query).get("url")
            if u:
                return u[0]
    except Exception:
        pass
    return link


def norm_title(title):
    t = title.split(" - ")[0]
    t = t.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    t = re.sub(r"[^\w]+", "", t.lower())
    return "t:" + t


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
            items.append((clean_link(link), title, dt))
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
    silent = first_run or not any(s.startswith("t:") for s in seen)
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
                    key = norm_title(title)
                    if dt < cutoff or link in seen_set or key in seen_set or key in titles:
                        continue
                    titles.add(key)
                    found[link] = (title, dt, key)
                    fresh += 1
                print(f"{name} | {q}: {len(items)} items, {fresh} new")
            except Exception as e:
                print("fetch error:", name, q, e)

    items = sorted(found.items(), key=lambda x: x[1][1])
    print("to send:", len(items), "silent:", silent)

    if silent:
        for link, (_, _, key) in items:
            seen.extend([link, key])
        if first_run:
            send("ربات اخبار میراث و باستان‌شناسی آذربایجان فعال شد ✅")
    else:
        for link, (title, _, key) in items[:MAX_PER_RUN]:
            if send(f"{title}\n{link}"):
                seen.extend([link, key])
            time.sleep(1)

    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[-4000:], f, ensure_ascii=False)


if __name__ == "__main__":
    main()
