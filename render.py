#!/usr/bin/env python3
"""无头浏览器渲染 JS 站点，从整页 HTML 里抽澳门六合彩号码 -> macau_rendered.json。
lotobo 等站把号码放在 HTML 标记(隐藏块/data-number)，innerText 为空，所以用整页 content() 解析。"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PAT = re.compile(r"(0?[1-9]|[1-4]\d)([ ,，、/\s]+(0?[1-9]|[1-4]\d)){6}")

def parse_lotobo(html):
    i = html.find('id="last-draw-block"')
    if i < 0:
        return None
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html[i:i + 3000]))
    m = re.search(r"(\d+/\d+)\s*期", txt)
    dm = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
    plus = txt.find("＋")
    if plus < 0:
        return None
    balls = [int(x) for x in re.findall(r"\b(\d{1,2})\b", txt[:plus].split("）")[-1])]
    sp = re.search(r"\b(\d{1,2})\b", txt[plus:])
    r = {"issue": (m.group(1) if m else ""), "time": (dm.group(1) if dm else ""),
         "special": (sp.group(1).zfill(2) if sp else None), "balls": [0] * 6}
    if len(balls) >= 6:
        r["balls"] = balls[-6:]
    return r

def extract(txt):
    tm = re.search(r"(特码|特號|特)[\s:：]*([0-4]\d|0?[1-9])", txt)
    m = PAT.search(txt)
    if not m:
        return None
    parts = [int(x) for x in re.split(r"[ ,，、/\s]+", m.group(0)) if x]
    special = tm.group(2) if tm else (f"{parts[6]:02d}" if len(parts) >= 7 else None)
    return {"issue": "", "time": "", "special": special, "balls": parts[:6]}

def main():
    up = json.load(open(os.path.join(HERE, "upstreams.json"), encoding="utf-8"))
    out = {}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        pg = br.new_page(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        pg.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        for region in ("macau", "hongkong"):
            for src in up.get(region, []):
                if src.get("type") not in ("render", "lotobo"):
                    continue
                try:
                    pg.goto(src["url"], wait_until="domcontentloaded", timeout=30000)
                    try:
                        pg.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    pg.wait_for_timeout(5000)
                    html = pg.content()
                    r = parse_lotobo(html) if 'last-draw-block' in html else extract(
                        pg.eval_on_selector_all("body", "els => els.map(e => e.innerText || '').join('\\n')")[0])
                    if r and r["balls"][0]:
                        r["source"] = src["id"]; out[region] = r
                        print(region, "OK", src["id"], r["balls"], "特=", r["special"], "期=", r["issue"])
                        break
                    print(region, "miss", src["id"])
                except Exception as e:
                    print(region, "err", src["id"], str(e)[:60])
            if region in out:
                break
        br.close()
    json.dump(out, open(os.path.join(HERE, "macau_rendered.json"), "w"), ensure_ascii=False, indent=2)
    print("rendered:", json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
