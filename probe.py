#!/usr/bin/env python3
"""让境外runner逐个探所有上游源，写回 probe-report.json，供我挑可用源。"""
import json, os, re, urllib.request, ssl, sys

HERE = os.path.dirname(os.path.abspath(__file__))
up = json.load(open(os.path.join(HERE, "upstreams.json"), encoding="utf-8"))
PAT = re.compile(r"(0?[1-9]|[1-4]\d)([ ,，、/\s]+(0?[1-9]|[1-4]\d)){6}")

def probe(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; eni-probe/1.0)", "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
        b = r.read(2_000_000).decode("utf-8", "replace")
        return r.getcode(), b

rep = {}
for region in ("macau", "hongkong"):
    rep[region] = []
    for src in up.get(region, []):
        u = src.get("url"); rec = {"id": src.get("id"), "url": u, "type": src.get("type")}
        try:
            code, b = probe(u)
            m = PAT.search(b)
            rec.update(code=code, len=len(b), has7=bool(m),
                       sample=(m.group(0)[:45] if m else ""),
                       isjson=("winningNumbers" in b or '"balls"' in b or '"results"' in b))
        except Exception as e:
            rec["err"] = str(e)[:70]
        rep[region].append(rec)
        print(rec.get("id"), rec.get("code") or rec.get("err"), "has7=", rec.get("has7"), "json=", rec.get("isjson"), "sample=", rec.get("sample"))

json.dump(rep, open(os.path.join(HERE, "probe-report.json"), "w"), ensure_ascii=False, indent=2)
print("WROTE probe-report.json")
