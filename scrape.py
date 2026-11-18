#!/usr/bin/env python3
"""港澳六合彩 -> results.json 抓取器。
在 GitHub Actions(境外) 里跑。上游源列表在 upstreams.json（可随时改，不用动手机App）。
逻辑：每个地区按 主->备 顺序试，取到第一个合法结果；全失败则沿用上一次缓存(last-good)。
输出 results.json：
{
  "macau":    {"issue":"2026xxxx","balls":[...6...],"special":"07","time":"2026-...","source":"id","fetched":ts},
  "hongkong": {...},
  "macau_is_cached": false, "hongkong_is_cached": false, "ts": ts
}
"""
import json, re, os, time, urllib.request, urllib.error, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
REGIONS = ["macau", "hongkong"]
UA = "Mozilla/5.0 (compatible; eni-lotto-scrape/1.0)"
LASTGOOD = os.path.join(HERE, "lastgood.json")
RESULTS  = os.path.join(HERE, "results.json")


def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read().decode("utf-8", "replace")


def parse_json(body, region):
    o = json.loads(body)
    # 有些源把数据包在 results[]（最新在[0]）或 data{} 里
    d = o
    if isinstance(o, dict):
        if isinstance(o.get("results"), list) and o["results"]:
            d = o["results"][0]
        elif isinstance(o.get("data"), dict):
            d = o["data"]
    def pick(*ks):
        for k in ks:
            v = d.get(k) if isinstance(d, dict) else None
            if v not in (None, ""):
                return v
        return None
    issue   = pick("drawId", "issue", "no", "期号", "期数", "drawNumber")
    time_   = pick("drawDate", "time", "date", "drawDateTime", "开奖时间", "updateTime")
    special = pick("extraNumber", "special", "特码", "te")
    balls = None
    for k in ("winningNumbers", "balls", "nums", "numbers", "号码"):
        v = d.get(k) if isinstance(d, dict) else None
        if v:
            balls = v; break
    out = {"issue": str(issue or ""), "time": str(time_ or ""), "special": None, "balls": [0]*6}
    if balls:
        flat = [int(x) for x in balls[:7]]
        if len(balls) == 7 and (special in (None, "")):
            out["balls"] = flat[:6]; out["special"] = f"{flat[6]:02d}"
        else:
            out["balls"] = [int(x) for x in balls[:6]]
            if special not in (None, ""):
                out["special"] = str(int(special)).zfill(2) if str(special).isdigit() else str(special)
    return out


def parse_html(body, region):
    # 六合彩启发式：连续 7 个 1-49 数字（6正+特）
    m = re.search(r"(0?[1-9]|[1-4]\d)([ ,，、\s]+(0?[1-9]|[1-4]\d)){6}", body)
    if not m:
        return None
    parts = [p for p in re.split(r"[ ,，、/\s]+", m.group(0)) if p]
    out = {"issue": "", "time": "", "special": None, "balls": [int(parts[i]) for i in range(min(6, len(parts)))]}
    if len(parts) >= 7:
        out["special"] = f"{int(parts[6]):02d}"
    # 找期号
    im = re.search(r"(第|期号)[\s:]?([0-9]{4,8})", body)
    if im: out["issue"] = im.group(2)
    tm = re.search(r"20[0-9]{2}[-/.][0-1]?[0-9][-/.][0-9]{1,2}", body)
    if tm: out["time"] = tm.group(0)
    return out


def parse_lotobo(body):
    """lotobao 澳门页：#last-draw-block -> 今期開彩結果 - 期 日期 6正码 ＋ 特码"""
    i = body.find('id="last-draw-block"')
    if i < 0:
        return None
    seg = body[i:i + 3000]
    txt = re.sub(r"<[^>]+>", " ", seg)
    txt = re.sub(r"\s+", " ", txt)
    m = re.search(r"(\d+/\d+)\s*期", txt)
    dm = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
    plus = txt.find("＋")
    if plus < 0:
        return None
    head = txt[:plus].split("）")[-1]
    balls = [int(x) for x in re.findall(r"\b(\d{1,2})\b", head)]
    sp = re.search(r"\b(\d{1,2})\b", txt[plus:])
    r = {"issue": (m.group(1) if m else ""), "time": (dm.group(1) if dm else ""),
         "special": (sp.group(1).zfill(2) if sp else None), "balls": [0] * 6}
    if len(balls) >= 6:
        r["balls"] = balls[-6:]
    return r


def valid(r):
    if not r: return False
    for b in r["balls"]:
        if not (1 <= b <= 49): return False
    if r.get("special"):
        try:
            s = int(r["special"])
            if not (1 <= s <= 49): return False
        except ValueError:
            return False
    return True


def load_upstreams():
    with open(os.path.join(HERE, "upstreams.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    up = load_upstreams()
    # 载入上次 last-good
    last = {}
    if os.path.exists(LASTGOOD):
        try: last = json.load(open(LASTGOOD, encoding="utf-8"))
        except Exception: last = {}

    results = {"ts": int(time.time())}
    for region in REGIONS:
        chosen = None
        for src in up.get(region, []):
            ptype = src.get("type", "json")
            if ptype == "render":
                continue  # JS 渲染交给 render.py
            url = src.get("url")
            try:
                body = http_get(url)
                if ptype == "json":
                    r = parse_json(body, region)
                elif ptype == "lotobo":
                    r = parse_lotobo(body)
                else:
                    r = parse_html(body, region)
                if valid(r):
                    r["source"] = src.get("id", url); r["fetched"] = int(time.time())
                    chosen = r; break
            except Exception:
                continue

        # JS 渲染兜底：render.py 生成的 macau_rendered.json
        if not chosen:
            rend = os.path.join(HERE, "macau_rendered.json")
            if os.path.exists(rend):
                try:
                    rr = json.load(open(rend, encoding="utf-8")).get(region)
                    if valid(rr):
                        rr.setdefault("fetched", int(time.time()))
                        rr["source"] = rr.get("source", "render"); chosen = rr
                except Exception:
                    pass

        if chosen:
            results[region] = chosen; results[region + "_is_cached"] = False
        elif region in last and valid(last.get(region)):
            results[region] = last[region]; results[region + "_is_cached"] = True
        else:
            results[region] = None; results[region + "_is_cached"] = True

    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    # 只要抓到新的就更新 last-good
    keep = {}
    for region in REGIONS:
        if results.get(region): keep[region] = results[region]
        elif region in last: keep[region] = last[region]
    if keep:
        json.dump(keep, open(LASTGOOD, "w", encoding="utf-8"), ensure_ascii=False)

    print(json.dumps({k: (v["issue"] if isinstance(v, dict) and "issue" in v else v) for k, v in results.items()
                      if k in ("macau", "hongkong")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
