#!/usr/bin/env python3
"""用无头浏览器渲染 JS 站点，抓它们的接口(JSON 响应)+ 诊断 -> 供挑选澳门源。"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PAT = re.compile(r"(0?[1-9]|[1-4]\d)([ ,，、/\s]+(0?[1-9]|[1-4]\d)){6}")

def extract(txt):
    tm = re.search(r"(特码|特號|特)[\s:：]*([0-4]\d|0?[1-9])", txt)
    m = PAT.search(txt)
    if not m:
        return None
    parts = [int(x) for x in m.group(0).split()]
    special = tm.group(2) if tm else (f"{parts[6]:02d}" if len(parts) >= 7 else None)
    return {"issue": "", "time": "", "special": special, "balls": parts[:6]}

def main():
    up = json.load(open(os.path.join(HERE, "upstreams.json"), encoding="utf-8"))
    diag, out = {}, {}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        pg = br.new_page(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        pg.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={app:{}};Object.defineProperty(navigator,'languages',{get:()=>['zh-CN','zh']});Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});")
        dump_path = os.path.join(HERE, "macau_dump.html")
        dumped = False
        for region in ("macau", "hongkong"):
            for src in up.get(region, []):
                if src.get("type") != "render":
                    continue
                rec = {"url": src["url"], "final": None, "nlen": 0, "has7": False, "apis": []}
                api_hits = []
                def on_resp(resp):
                    try:
                        ct = (resp.headers.get("content-type", "") or "")
                        if resp.status < 300 and ("json" in ct or re.search(r"/api/|draw|result|loto|/mo/|/mo\b", resp.url, re.I)):
                            body = resp.text()
                            if PAT.search(body):
                                api_hits.append({"url": resp.url, "body": body[:2000]})
                    except Exception:
                        pass
                pg.on("response", on_resp)
                try:
                    pg.goto(src["url"], wait_until="domcontentloaded", timeout=30000)
                    try:
                        pg.wait_for_load_state("networkidle", timeout=12000)
                    except Exception:
                        pass
                    pg.wait_for_timeout(8000)
                    rec["final"] = pg.url
                    if region == "macau" and not dumped:
                        open(dump_path, "w").write(pg.content())
                        dumped = True
                    ntxt = pg.eval_on_selector_all("body", "els => els.map(e => e.innerText || '').join('\\n')")[0]
                    rec["nlen"] = len(ntxt)
                    r = extract(ntxt)
                    rec["has7"] = bool(r)
                    if r:
                        r["source"] = src["id"]; out[region] = r
                except Exception as e:
                    rec["err"] = str(e)[:80]
                pg.remove_listener("response", on_resp)
                # 接口里命中的，优先取接口(比DOM稳)
                for h in api_hits:
                    rr = extract(h["body"])
                    if rr:
                        rr["source"] = src["id"] + "@api"; rr["time"] = ""; out.setdefault(region, rr)
                        rec["api"] = h["url"][:120]
                        break
                rec["apis"] = [a["url"][:80] for a in api_hits]
                diag[src["id"]] = rec
                print(region, src["id"], "has7=", rec["has7"], "nlen=", rec["nlen"], "api=", rec.get("api", rec.get("apis")), rec.get("err", ""))
                if out.get(region):
                    break
            if region in out:
                break
        br.close()
    json.dump(out, open(os.path.join(HERE, "macau_rendered.json"), "w"), ensure_ascii=False, indent=2)
    json.dump(diag, open(os.path.join(HERE, "macau_diag.json"), "w"), ensure_ascii=False, indent=2)
    print("rendered:", json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
