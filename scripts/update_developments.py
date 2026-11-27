#!/usr/bin/env python3
"""Hourly updater for developments.json. Standard library only.

Reads the feeds in sources.json, keeps stories that are about AI and tied by their own
headline or summary to Stanford, Silicon Valley or San Francisco, scores them with the
rubric stored in developments.json, and adds at most 3 per run.

This is an automated, rules-based assessment. It cannot check whether a story supports
its headline, so every item it adds is labelled assessed_by = "automated".
"""
import html, json, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
MAX_NEW, MAX_AGE_DAYS, TIMEOUT = 3, 14, 20
AREAS = ["Stanford", "Silicon Valley", "San Francisco"]
AI = re.compile(r"\b(AI|A\.I\.|artificial intelligence|machine learning|deep learning|generative|large language model|LLMs?|chatbots?|robotaxis?|autonomous|neural network|data cent(?:er|re)s?)\b", re.I)
PLACES = {
    "Stanford": [r"Stanford"],
    "Silicon Valley": [r"Silicon Valley", r"Santa Clara", r"Palo Alto", r"Mountain View", r"Sunnyvale", r"Cupertino",
                       r"San Jos[eé]", r"Menlo Park", r"Redwood City", r"San Mateo", r"Los Altos", r"Milpitas"],
    "San Francisco": [r"San Francisco", r"\bSF\b"],
}
CATEGORIES = [  # first match wins
    ("funding", r"raises?|raised|funding|round|valuation|acquir|IPO|investors?|venture"),
    ("mobility", r"robotaxi|autonomous|self-driving|driverless|Waymo"),
    ("public sector", r"city|county|council|board|commission|court|law|ordinance|mayor|state|regulator|permit|approv"),
    ("education", r"student|school|course|campus|teach|curriculum|college|university"),
    ("infrastructure", r"data cent(?:er|re)|chips?|power|energy|facility|supercomputer"),
]
UA = {"User-Agent": "BayAreaAINavigator/1.0 (coursework site; +https://github.com/wgu-smith/Bay_Area_AI_Navigator)"}

def strip(text):
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()

def parse_date(text):
    if not text:
        return None
    try:
        d = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def local(tag):
    return tag.rsplit("}", 1)[-1]

def parse_feed(xml_text):
    root = ET.fromstring(xml_text)
    out = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        f = {"title": "", "link": "", "summary": "", "date": None}
        for c in el:
            t = local(c.tag)
            if t == "title":
                f["title"] = strip("".join(c.itertext()))
            elif t == "link":
                f["link"] = c.get("href") or (c.text or "").strip() or f["link"]
            elif t in ("description", "summary", "encoded", "content") and len(f["summary"]) < 1500:
                f["summary"] = strip("".join(c.itertext()))[:1500]
            elif t in ("pubDate", "published", "updated", "date") and not f["date"]:
                f["date"] = parse_date((c.text or "").strip())
        if f["title"] and f["link"]:
            out.append(f)
    return out

def fetch(feed, fixtures):
    if fixtures:
        p = Path(fixtures) / (re.sub(r"\W+", "_", feed["name"]).lower() + ".xml")
        return p.read_text(encoding="utf-8") if p.exists() else None
    req = urllib.request.Request(feed["url"], headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")

def norm_url(u):
    return re.sub(r"[?#].*$", "", u.strip().lower()).rstrip("/")

def tokens(t):
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 3}

def similar(a, b):
    ta, tb = tokens(a), tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb)

def relevance(f, home):
    out, place = {}, {}
    for area in AREAS:
        score, first = 0, None
        for pat in PLACES[area]:
            in_title = len(re.findall(pat, f["title"]))
            in_text = len(re.findall(pat, f["summary"]))
            if in_title or in_text:
                first = first or re.sub(r"\\b|\\", "", pat)
            score += 40 * min(in_title, 2) + 15 * min(in_text, 3)
        if home == area:
            score = max(score, 60)
        out[area] = min(100, score)
        place[area] = first or area
    return out, place

def category(f):
    text = f["title"] + " " + f["summary"][:300]
    for name, pat in CATEGORIES:
        if re.search(pat, text, re.I):
            return name
    return "research"

def score(f, feed, corroborated):
    text = f["title"] + " " + f["summary"]
    source = 35 if feed["kind"] == "primary" else 30
    corr = 12 if corroborated else 0
    spec = 5 * sum([
        bool(re.search(r"\$\s?\d|\d+(\.\d+)?\s?(%|percent|billion|million)", text)),
        bool(re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b", text)),
        len(f["summary"]) > 200,
        bool(re.search(r"\b(County|City|Board|Commission|Council|University|Institute|Court|Department)\b", text)),
    ])
    sig = 0
    if re.search(r"billion", text, re.I): sig += 8
    elif re.search(r"million", text, re.I): sig += 4
    if re.search(r"approv|permit|ruling|ordinance|lawsuit|law\b", text, re.I): sig += 5
    if re.search(r"first[- ]|launch|unveil|opens?\b", text, re.I): sig += 3
    if re.search(r"raises?|raised|funding round|acquir|IPO", text, re.I): sig += 5
    sig = min(15, sig)
    return source, corr, spec, sig

def run(root, fixtures=None, now=None):
    now = now or datetime.now(timezone.utc)
    data = json.loads((root / "developments.json").read_text(encoding="utf-8"))
    feeds = json.loads((root / "sources.json").read_text(encoding="utf-8"))["feeds"]
    threshold = data.get("rubric", {}).get("admission_threshold", 50)
    existing = data["items"]
    seen_urls = {norm_url(i["source_url"]) for i in existing}
    cands, status = [], []
    for feed in feeds:
        try:
            xml = fetch(feed, fixtures)
            if xml is None:
                status.append((feed["name"], "no fixture")); continue
            stories = parse_feed(xml)
            status.append((feed["name"], f"ok, {len(stories)} stories"))
        except Exception as e:  # one bad feed must not stop the run
            status.append((feed["name"], f"FAILED: {type(e).__name__}: {str(e)[:80]}")); continue
        for s in stories:
            s["feed"] = feed
            cands.append(s)
    pool = []
    for f in cands:
        if not f["date"] or f["date"] < now - timedelta(days=MAX_AGE_DAYS) or f["date"] > now + timedelta(days=1):
            continue
        if not f["link"].lower().startswith("https://"):
            continue
        if "kqed.org" in f["link"].lower():
            continue
        if norm_url(f["link"]) in seen_urls:
            continue
        if not AI.search(f["title"] + " " + f["summary"][:400]):
            continue
        rel, place = relevance(f, f["feed"].get("home_area"))
        top = max(AREAS, key=lambda a: rel[a])
        if rel[top] < 40:
            continue
        pool.append((f, rel, place, top))
    out = []
    for f, rel, place, top in pool:
        corroborated = any(g is not f and g["feed"]["name"] != f["feed"]["name"] and similar(f["title"], g["title"]) >= 0.5 for g, *_ in pool)
        src, corr, spec, sig = score(f, f["feed"], corroborated)
        strength = src + corr + spec + sig
        if strength < threshold:
            continue
        if any(similar(f["title"], i["title"]) >= 0.8 for i in existing):
            continue
        out.append((strength, f, rel, place, top, (src, corr, spec, sig)))
    out.sort(key=lambda x: (-x[0], -x[1]["date"].timestamp()))
    added, used = [], []
    for strength, f, rel, place, top, (src, corr, spec, sig) in out:
        if len(added) >= MAX_NEW:
            break
        if any(similar(f["title"], u) >= 0.8 for u in used):
            continue
        used.append(f["title"])
        title = f["title"] if len(f["title"]) <= 110 else f["title"][:107].rstrip() + "..."
        pt = ZoneInfo("America/Los_Angeles")
        added.append({
            "title": title, "category": category(f), "source_url": f["link"],
            "source_type": "Primary source" if f["feed"]["kind"] == "primary" else "Independently reported",
            "place": place[top], "published_on": f["date"].astimezone(pt).date().isoformat(),
            "last_verified": now.astimezone(pt).date().isoformat(), "area": top,
            "assessed_by": "automated",
            "scores": {"source": src, "corroboration": corr, "specificity": spec, "significance": sig,
                       "strength": strength, "relevance": rel},
        })
    existing.extend(added)
    existing.sort(key=lambda i: i["published_on"], reverse=True)
    ok = sum(1 for _, s in status if s.startswith("ok"))
    data["last_run"] = now.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
    data["checked_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["note"] = f"Automated run: {len(added)} new item(s) added; {ok} of {len(status)} feeds read."
    (root / "developments.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return added, status

if __name__ == "__main__":
    fx = sys.argv[sys.argv.index("--fixtures") + 1] if "--fixtures" in sys.argv else None
    added, status = run(ROOT, fx)
    for n, s in status:
        print(f"{n}: {s}")
    for a in added:
        print(f"ADDED [{a['scores']['strength']}] {a['area']} | {a['title']}")
    print(f"{len(added)} new item(s)")
