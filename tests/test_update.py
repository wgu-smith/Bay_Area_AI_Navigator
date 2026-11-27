import json, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import update_developments as u

tmp = Path(tempfile.mkdtemp())
for f in ("developments.json", "sources.json"):
    shutil.copy(ROOT / f, tmp / f)
before = json.loads((tmp / "developments.json").read_text())
n0 = len(before["items"])
now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
added, status = u.run(tmp, str(ROOT / "tests" / "fixtures"), now)
after = json.loads((tmp / "developments.json").read_text())
titles = [a["title"] for a in added]
checks = {
  "bad feed does not stop the run": any(s.startswith("FAILED") for n, s in status if n == "Mercury News"),
  "missing feeds are reported, not fatal": any(s == "no fixture" for _, s in status),
  "Stanford AI story added as Primary source": any("radiology" in t and a["source_type"] == "Primary source" and a["area"] == "Stanford" for t, a in zip(titles, added)),
  "San Francisco funding story added with category funding": any("raises $250 million" in t and a["area"] == "San Francisco" and a["category"] == "funding" for t, a in zip(titles, added)),
  "tracking query string dropped from duplicate check only, link kept https": all(a["source_url"].startswith("https://") for a in added),
  "non-AI story skipped": not any("poetry" in t for t in titles),
  "non-Bay-Area story skipped": not any("Austin" in t for t in titles),
  "old story skipped": not any("long ago" in t for t in titles),
  "http link skipped": not any("Insecure" in t for t in titles),
  "markup stripped from title": all("<" not in t for t in titles),
  "at most 3 added": len(added) <= 3,
  "all admitted items meet the threshold": all(a["scores"]["strength"] >= 50 for a in added),
  "items labelled automated": all(a["assessed_by"] == "automated" for a in added),
  "strength is the sum of its parts": all(a["scores"]["strength"] == sum(a["scores"][k] for k in ("source","corroboration","specificity","significance")) for a in added),
  "item count grew by number added": len(after["items"]) == n0 + len(added),
  "rubric unchanged": after["rubric"] == before["rubric"],
  "sorted newest first": [i["published_on"] for i in after["items"]] == sorted((i["published_on"] for i in after["items"]), reverse=True),
  "stamps updated": after["checked_at"] == "2026-11-27T12:00:00Z" and after["last_run"] == "2026-11-27",
}
# second run must not add duplicates
added2, _ = u.run(tmp, str(ROOT / "tests" / "fixtures"), now)
checks["second run adds nothing (no duplicates)"] = len(added2) == 0
for k, v in checks.items():
    print(("PASS  " if v else "FAIL  ") + k)
print("added:", [(a["scores"]["strength"], a["area"], a["title"][:60]) for a in added])
print("status:", status)
sys.exit(0 if all(checks.values()) else 1)
