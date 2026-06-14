#!/usr/bin/env python3
"""야선지지 클론 - 실제 시세/뉴스 수집기.
GitHub Actions가 주기적으로 실행해 data.json을 생성한다.
모든 데이터는 Yahoo Finance(시세) + Google News RSS(뉴스)에서 가져온다."""
import json, re, sys, time, urllib.request, urllib.parse, html
from datetime import datetime, timezone, timedelta

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
KST = timezone(timedelta(hours=9))

# ASSETS key -> Yahoo Finance 심볼
SYMBOLS = {
    "k200":   "^KS200",
    "kq150":  "229200.KS",   # KODEX 코스닥150 ETF
    "kospi":  "^KS11",
    "kosdaq": "^KQ11",
    "nq":     "NQ=F",
    "es":     "ES=F",
    "ndx":    "^IXIC",
    "sox":    "^SOX",
    "nikkei": "^N225",
    "wti":    "CL=F",
    "gold":   "GC=F",
    "silver": "SI=F",
    "gas":    "NG=F",
    "vix":    "^VIX",
    "usdkrw": "KRW=X",
    "btc":    "BTC-USD",
    "eth":    "ETH-USD",
}

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def fetch_quote(symbol):
    """가격/전일종가/인트라데이 스파크라인을 한 번에 가져온다."""
    enc = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}?interval=5m&range=1d"
    for attempt in range(3):
        try:
            d = json.loads(http_get(url))
            res = d["chart"]["result"][0]
            meta = res["meta"]
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            spark = []
            try:
                closes = res["indicators"]["quote"][0]["close"]
                spark = [round(c, 4) for c in closes if c is not None][-40:]
            except Exception:
                spark = []
            if price is None:
                raise ValueError("no price")
            return {"price": price, "prev": prev, "spark": spark}
        except Exception as e:
            if attempt == 2:
                print(f"  ! {symbol} 실패: {e}", file=sys.stderr)
                return None
            time.sleep(1.5)

def fetch_news(limit=14):
    """구글뉴스 한국 증시 RSS에서 실제 뉴스 헤드라인을 가져온다."""
    q = urllib.parse.quote("증시 OR 코스피 OR 나스닥 OR 환율 OR 비트코인")
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        xml = http_get(url)
    except Exception as e:
        print(f"  ! 뉴스 실패: {e}", file=sys.stderr)
        return []
    items = re.findall(r"<item>(.*?)</item>", xml, re.S)
    out = []
    for it in items[:limit]:
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        p = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        src = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
        lk = re.search(r"<link>(.*?)</link>", it, re.S)
        if not t:
            continue
        link = html.unescape(lk.group(1)).strip() if lk else ""
        title = html.unescape(t.group(1)).strip()
        # 구글뉴스는 " - 출처" 접미사를 붙임 → 분리
        source = html.unescape(src.group(1)).strip() if src else ""
        if source and title.endswith("- " + source):
            title = title[: -(len(source) + 2)].strip()
        pub = ""
        if p:
            try:
                dt = datetime.strptime(p.group(1).strip(), "%a, %d %b %Y %H:%M:%S %Z")
                pub = dt.replace(tzinfo=timezone.utc).astimezone(KST).isoformat()
            except Exception:
                pub = ""
        out.append({"title": title, "source": source, "time": pub, "url": link})
    return out

def main():
    quotes = {}
    for key, sym in SYMBOLS.items():
        q = fetch_quote(sym)
        if q:
            quotes[key] = q
            print(f"  {key:8s} {sym:12s} = {q['price']}")
        time.sleep(0.4)
    news = fetch_news()
    print(f"  뉴스 {len(news)}건")
    data = {
        "updated": datetime.now(KST).isoformat(),
        "quotes": quotes,
        "news": news,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"data.json 작성 완료: 시세 {len(quotes)}종, 뉴스 {len(news)}건")

if __name__ == "__main__":
    main()
