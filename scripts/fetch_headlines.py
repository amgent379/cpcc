"""Fetch recent biotech/pharma headlines from public RSS feeds into headlines.json.

Run daily by .github/workflows/headlines.yml. Uses only the standard library.
"""
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS = [
    ("BioPharma Dive", "https://www.biopharmadive.com/feeds/news/"),
    ("Fierce Biotech", "https://www.fiercebiotech.com/rss/xml"),
    ("Fierce Pharma", "https://www.fiercepharma.com/rss/xml"),
    ("STAT", "https://www.statnews.com/category/biotech/feed/"),
]
PER_SOURCE = 4
TOTAL = 16
ATOM = "{http://www.w3.org/2005/Atom}"


def parse_date(text):
    if not text:
        return None
    text = text.strip()
    try:
        d = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def fetch(source, url):
    req = urllib.request.Request(url, headers={"User-Agent": "CPCC-headlines/1.0 (+https://capeporpoiseclinical.com)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read()
    root = ET.fromstring(body)
    channel = root.find("channel")
    base = root.get("{http://www.w3.org/XML/1998/namespace}base") or (channel.findtext("link") if channel is not None else None) or url
    items = []
    for it in root.iter("item"):
        items.append((it.findtext("title"), it.findtext("link"), parse_date(it.findtext("pubDate"))))
    for it in root.iter(ATOM + "entry"):
        link = it.find(ATOM + "link")
        items.append((it.findtext(ATOM + "title"), link.get("href") if link is not None else None,
                      parse_date(it.findtext(ATOM + "updated") or it.findtext(ATOM + "published"))))
    out = []
    for title, link, date in items:
        if not title or not link:
            continue
        link = urljoin(base, link.strip())
        if not link.startswith("http"):
            continue
        out.append({"title": " ".join(title.split()), "link": link, "source": source,
                    "date": date.isoformat() if date else None})
    out.sort(key=lambda x: x["date"] or "", reverse=True)
    print(f"{source}: {len(items)} items in feed, {len(out)} usable, {len(body)} bytes, root <{root.tag}>")
    if not out:
        first = next(root.iter("item"), None)
        if first is not None:
            print(ET.tostring(first)[:700].decode("utf-8", "replace"))
    return out[:PER_SOURCE]


def main():
    collected, seen = [], set()
    for source, url in FEEDS:
        try:
            for item in fetch(source, url):
                key = item["title"].lower()
                if key not in seen:
                    seen.add(key)
                    collected.append(item)
        except Exception as e:  # one failing feed should not stop the others
            print(f"warning: {source}: {e}", file=sys.stderr)
    collected.sort(key=lambda x: x["date"] or "", reverse=True)
    collected = collected[:TOTAL]
    if not collected:
        print("no headlines fetched; leaving existing file unchanged", file=sys.stderr)
        return
    with open("headlines.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "items": collected}, f, indent=1)
    print(f"wrote {len(collected)} headlines")


if __name__ == "__main__":
    main()
