#!/usr/bin/env python3
"""全量测用户给的每个站：能取到7球(1-49)+特码的，标记 method(http/js)。写 allprobe-report.json。"""
import json, os, re, ssl, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PAT = re.compile(r"(0?[1-9]|[1-4]\d)([ ,，、/\s]+(0?[1-9]|[1-4]\d)){6}")

# 用户给的站（分地区）
SITES = [
    ("macau", "mac_lotobo",  "https://lotobao.com/loto/mo/new_mark6"),
    ("macau", "mac_jc",      "https://macaujc.com/"),
    ("macau", "mac_jcmacau", "https://jc-macau.com/"),
    ("macau", "mac_app1",    "https://111826h2.66111eee3.com/area/aomen"),
    ("macau", "mac_app2",    "https://111826h2.66111fff3.com/area/aomen"),
    ("macau", "mac_app3",    "https://111826h2.66111hhh3.com/area/aomen"),
    ("macau", "mac_app4",    "https://111826h2.66111iii3.com/area/aomen"),
    ("macau", "mac_tonti",   "https://tonti4gbn.yzjkzzbfn.xyz/?redirect=/#_t=25869daj"),
    ("macau", "mac_tonto",   "https://tonto62pz.aajnaaraahmc.xyz/?redirect=/#_t=25869d66"),
    ("hongkong", "hk_on99",   "https://on99.life/api/lottery/history"),
    ("hongkong", "hk_1314",   "https://hk1314.com/?cai_type=HK"),
    ("hongkong", "hk_hkmark6","https://www.hkmark6.net/"),
    ("hongkong", "hk_marksixinfo","https://marksixinfo.com/"),
    ("hongkong", "hk_newhkjc","https://www.newhkjc.com/"),
    ("hongkong", "hk_672",    "https://hk672.com/"),
    ("hongkong", "hk_673",    "https://hk673.com/"),
    ("hongkong", "hk_674",    "https://hk674.com/"),
    ("hongkong", "hk_675",    "https://hk675.com/"),
    ("hongkong", "hk_mingpao","https://news.mingpao.com/pns/%E5%85%AD%E5%90%88%E5%BD%A9/marksix"),
    ("hongkong", "hk_lottery_hk","https://lottery.hk/liuhecai/"),
    ("hongkong", "hk_on99_page","https://on99.life/lottery/results"),
]

def parse_lotobo(html):
    i = html.find('id="last-draw-block"')
    if i < 0: return None
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html[i:i + 3000]))
    plus = txt.find("＋")
    if plus < 0: return None
    balls = [int(x) for x in re.findall(r"\b(\d{1,2})\b", txt[:plus].split("）")[-1])]
    sp = re.search(r"\b(\d{1,2})\b", txt[plus:])
    m = re.search(r"(\d+/\d+)\s*期", txt)
    if len(balls) < 6: return None
    return {"issue": m.group(1) if m else "", "balls": balls[-6:], "special": (sp.group(1).zfill(2) if sp else None)}

def gen_parse(text):
    m = PAT.search(text)
    if not m: return None
    parts = [int(x) for x in re.split(r"[ ,，、/\s]+", m.group(0)) if x]
    if len(parts) < 6: return None
    return {"issue": "", "balls": parts[:6], "special": (f"{parts[6]:02d}" if len(parts) >= 7 else None)}

def valid(balls, special):
    for b in balls:
        if not (1 <= b <= 49): return False
    if special:
        try:
            if not (1 <= int(special) <= 49): return False
        except ValueError:
            return False
    return True

def http(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
        return r.read(2_000_000).decode("utf-8", "replace")

def js(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        pg = br.new_page(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15 Mobile/15E148")
        pg.goto(url, wait_until="domcontentloaded", timeout=25000)
        try: pg.wait_for_load_state("networkidle", timeout=8000)
        except Exception: pass
        pg.wait_for_timeout(5000)
        html = pg.content()
        br.close()
        return html

def main():
    report = {}
    js_candidates = []
    # 阶段1：HTTP
    for region, sid, url in SITES:
        rec = {"region": region, "url": url, "method": None, "balls": None, "special": None, "issue": None, "err": ""}
        try:
            body = http(url)
            # on99 式 JSON
            if '"winningNumbers"' in body or ("\"results\":" in body and "drawId" in body):
                o = json.loads(body)
                d = o["results"][0] if isinstance(o.get("results"), list) and o["results"] else o.get("data", o)
                rec["balls"] = d.get("winningNumbers", []); rec["special"] = str(d.get("extraNumber", "")); rec["issue"] = d.get("drawId", "")
                if valid(rec["balls"], rec["special"]): rec["method"] = "http-json"
            else:
                lp = parse_lotobo(body) or gen_parse(body)
                if lp and valid(lp["balls"], lp.get("special")):
                    rec.update(lp); rec["method"] = "http-html"
        except Exception as e:
            rec["err"] = str(e)[:60]
        if rec["method"]:
            report[sid] = rec
            print("HTTP", region, sid, rec["balls"], "特=", rec["special"])
        else:
            js_candidates.append((region, sid, url))

    # 阶段2：剩下用无头浏览器渲染
    if js_candidates:
        for region, sid, url in js_candidates:
            rec = {"region": region, "url": url, "method": None, "balls": None, "special": None, "issue": None, "err": ""}
            try:
                html = js(url)
                lp = parse_lotobo(html) or gen_parse(html)
                if lp and valid(lp["balls"], lp.get("special")):
                    rec.update(lp); rec["method"] = "js-render"
                else:
                    rec["err"] = "no-nums(len=%d)" % len(html)
            except Exception as e:
                rec["err"] = str(e)[:60]
            report[sid] = rec
            print("JS", region, sid, rec["balls"] or rec["err"])
    json.dump(report, open(os.path.join(HERE, "allprobe-report.json"), "w"), ensure_ascii=False, indent=2)
    ok = {k: v["method"] for k, v in report.items() if v.get("method")}
    print("WORKING:", json.dumps(ok, ensure_ascii=False))

if __name__ == "__main__":
    main()
