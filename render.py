#!/usr/bin/env python3
"""用无头浏览器渲染 JS 站点，把 澳门 六合彩号码读出来 -> macau_rendered.json。
只有上游是 JS 渲染(type=render)才走这里；纯 HTTP 抓不到的才用。"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PAT = re.compile(r"(0?[1-9]|[1-4]\d)([ ,，、/\s]+(0?[1-9]|[1-4]\d)){6}")

def extract(txt):
    # 若正文里出现「特码/特」紧邻一个数字，就把它当特码，其余 6 个当正码
    tm = re.search(r"(特码|特號|特)[\s:：]*([0-4]\d|0?[1-9])", txt)
    m = PAT.search(txt)
    if not m:
        return None
    parts = [int(x) for x in m.group(0).split()]
    special = tm.group(2) if tm else (f"{parts[6]:02d}" if len(parts) >= 7 else None)
    return {"issue": "", "time": "", "special": special, "balls": parts[:6]}

def main():
    up = json.load(open(os.path.join(HERE, "upstreams.json"), encoding="utf-8"))
    out = {}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        pg = br.new_page(user_agent="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile")
        for region in ("macau", "hongkong"):
            if region in out:
                continue
            for src in up.get(region, []):
                if src.get("type") != "render":
                    continue
                try:
                    pg.goto(src["url"], wait_until="domcontentloaded", timeout=25000)
                    try:
                        pg.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:
                        pass
                    pg.wait_for_timeout(2500)
                    txt = pg.eval_on_selector_all(
                        "body", "els => els.map(e => e.innerText || '').join('\\n')")[0]
                    r = extract(txt)
                    if r:
                        r["issue"] = src.get("id", "")
                        r["source"] = src.get("id", src["url"])
                        r["time"] = ""
                        out[region] = r
                        print(region, "OK via", src.get("id"), "sample=", r["balls"], "特=", r["special"])
                        break
                    else:
                        print(region, "no7", src.get("id"), "len=", len(txt))
                except Exception as e:
                    print(region, "err", src.get("id"), str(e)[:60])
        br.close()
    json.dump(out, open(os.path.join(HERE, "macau_rendered.json"), "w"), ensure_ascii=False, indent=2)
    print("rendered:", json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
