#!/usr/bin/env python3
"""
Dicta daily filing check.

Looks on SEC EDGAR for new earnings releases from the companies in
data/watchlist.json: an 8-K with item 2.02 (results of operations), or a 6-K
from a foreign company (like TSMC or ASML) that reads like quarterly results.

For each new release it adds an item to data/pending.json with the link and a
short pointer to who is quoted in it. It never copies the quotes themselves:
a person opens the source, picks the line and checks it word for word.

Uses only the Python standard library. Needs the SEC_USER_AGENT environment
variable, for example "Dicta research yourname@example.com". The SEC asks every
automated visitor to name themselves and give a contact email.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
NOTE_FILE = os.path.join(ROOT, "review-note.md")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "14"))
UA = os.environ.get("SEC_USER_AGENT", "").strip()

ROLE_WORDS = r"(?:Chair(?:man|woman|person)?|Chief Executive Officer|CEO|President|Chief Financial Officer|CFO)"
SAID = r"(?:said|says|commented|stated|added|noted)"
RESULTS_RE = re.compile(r"\b(first|second|third|fourth|1Q|2Q|3Q|4Q|Q[1-4])\b.{0,60}?\b(quarter|results|earnings)\b", re.I | re.S)
QUOTE_RE = re.compile(r"[“\"]([^“”\"]{40,1500})[”\"]")
NAME = r"[A-Z][A-Za-z.\-’']+(?:\s+[A-Z][A-Za-z.\-’']+){0,3}(?:,\s*Jr\.)?"
AFTER_SAID_NAME = re.compile(r"^\W{0,5}" + SAID + r"\s+(" + NAME + r")", re.S)
AFTER_NAME_SAID = re.compile(r"^\W{0,5}(" + NAME + r")[^.]{0,80}?\b" + SAID + r"\b", re.S)
BEFORE_ROLE_NAME = re.compile(ROLE_WORDS + r",?\s+(" + NAME + r"),?\s+" + SAID + r"\s*[:,]?\s*$", re.S)
BEFORE_NAME = re.compile(r"(" + NAME + r"),?\s[^.]{0,120}?" + ROLE_WORDS + r"[^.]{0,80}?\b" + SAID + r"\s*[:,]?\s*$", re.S)


def looks_like_name(s):
    return bool(s) and not re.search(ROLE_WORDS, s) and not re.match(r"(?i)(the|our|we|this|company)\b", s)


def read_json(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch(url, as_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            time.sleep(0.25)  # stay well under the SEC's limit of 10 requests a second
            return json.loads(body) if as_json else body.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError:
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def html_to_text(raw):
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", raw)
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", text)


def quote_pointers(text, limit=4):
    """Where executives are quoted: a speaker hint and the first 6 words only."""
    out, seen_starts = [], set()
    for m in QUOTE_RE.finditer(text):
        after = text[m.end():m.end() + 220]
        before = text[max(0, m.start() - 260):m.start()]
        window = before + " " + after
        if not re.search(ROLE_WORDS, window) or not re.search(r"\b" + SAID + r"\b", window):
            continue
        speaker = ""
        for rx, src in ((AFTER_SAID_NAME, after), (AFTER_NAME_SAID, after), (BEFORE_ROLE_NAME, before), (BEFORE_NAME, before)):
            mm = rx.search(src)
            cand = mm.group(1).strip(" ,") if mm else ""
            if cand.endswith(".") and not cand.endswith("Jr."):
                cand = cand[:-1]
            if looks_like_name(cand):
                speaker = cand
                break
        words = m.group(1).split()
        starts = " ".join(words[:6]) + ("…" if len(words) > 6 else "")
        if starts in seen_starts:
            continue
        seen_starts.add(starts)
        out.append({"speaker": speaker or "Check the source", "startsWith": starts})
        if len(out) >= limit:
            break
    return out


def pick_document(cik, acc_nodash, primary):
    """Prefer exhibit 99.1 (the press release) over the cover form."""
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/"
    try:
        idx = fetch(base + "index.json")
        names = [i.get("name", "") for i in idx.get("directory", {}).get("item", [])]
    except Exception:
        names = []
    ex = sorted(n for n in names if re.search(r"ex[-_]?99", n, re.I) and n.lower().endswith((".htm", ".html")))
    return base + (ex[0] if ex else primary)


def ticker_of(display):
    return str(display or "").split(":")[-1].upper()


def already_in_feed(quotes, ticker, filed):
    """True when the feed already has a quote from this company within 3 days of the filing."""
    for q in quotes:
        if ticker_of(q.get("ticker")) != ticker:
            continue
        try:
            gap = abs((dt.date.fromisoformat(q["date"]) - dt.date.fromisoformat(filed)).days)
        except (KeyError, ValueError):
            continue
        if gap <= 3:
            return True
    return False


def review_note(items, problems, today):
    lines = [f"The daily check found {len(items)} new earnings release{'s' if len(items) != 1 else ''} to review ({today}).", ""]
    lines += ["| Company | Filed | Form | Source | Who is quoted |", "| --- | --- | --- | --- | --- |"]
    for it in items:
        people = "; ".join(f"{p['speaker']}: \"{p['startsWith']}\"" for p in it["quotedPeople"]) or "No quotes found; check the source"
        lines.append(f"| {it['company']} ({it['ticker']}) | {it['filed']} | {it['form']} | [open]({it['url']}) | {people} |")
    lines += ["", "**To review:** open `review.html` on the site, fill in each quote from the source, and paste the two outputs into `data/quotes.json` and `data/pending.json`. Close this issue when you're done."]
    if problems:
        lines += ["", "**Couldn't check:**"] + [f"- {p}" for p in problems]
    return "\n".join(lines) + "\n"


def main():
    if not UA or "@" not in UA:
        sys.exit("Set SEC_USER_AGENT to a name plus a contact email, for example 'Dicta research you@example.com'. "
                 "On GitHub: Settings > Secrets and variables > Actions > Variables.")
    if os.path.exists(NOTE_FILE):
        os.remove(NOTE_FILE)

    watch = read_json("watchlist.json", {"companies": []}).get("companies", [])
    pending = read_json("pending.json", {"items": []})
    pending.setdefault("items", [])
    seen = read_json("seen.json", {"ids": []})
    seen.setdefault("ids", [])
    quotes = read_json("quotes.json", {"quotes": []}).get("quotes", [])

    known = set(seen["ids"]) | {i.get("id") for i in pending["items"]}
    quote_urls = {q.get("sourceUrl") for q in quotes}
    today = dt.date.today()
    since = (today - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()

    tickers = fetch("https://www.sec.gov/files/company_tickers.json")
    cik_by_ticker = {str(v["ticker"]).upper(): int(v["cik_str"]) for v in tickers.values()}

    added, problems = [], []
    for co in watch:
        t = str(co.get("ticker", "")).upper()
        cik = cik_by_ticker.get(t)
        if not cik:
            problems.append(f"{t}: not in the SEC's ticker list. Check the ticker in data/watchlist.json.")
            continue
        try:
            sub = fetch(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        except Exception as e:
            problems.append(f"{t}: couldn't read its filings ({e}).")
            continue
        r = sub.get("filings", {}).get("recent", {})
        n = len(r.get("accessionNumber", []))
        items_col = r.get("items") or [""] * n
        for i in range(n):
            form, filed = r["form"][i], r["filingDate"][i]
            if filed < since:
                continue
            is_8k = form in ("8-K", "8-K/A") and "2.02" in (items_col[i] or "")
            is_6k = form in ("6-K", "6-K/A")
            if not (is_8k or is_6k):
                continue
            acc = r["accessionNumber"][i]
            fid = f"{cik}-{acc}"
            if fid in known:
                continue
            known.add(fid)
            seen["ids"].append(fid)
            display = co.get("display") or t
            if already_in_feed(quotes, t, filed):
                continue
            acc_nd = acc.replace("-", "")
            try:
                url = pick_document(cik, acc_nd, r["primaryDocument"][i])
                text = html_to_text(fetch(url, as_json=False))
            except Exception as e:
                problems.append(f"{t} {acc}: couldn't open the filing ({e}).")
                seen["ids"].pop()
                known.discard(fid)
                continue
            if is_6k and not RESULTS_RE.search(text[:8000]):
                continue  # a 6-K that isn't an earnings release
            if url in quote_urls:
                continue
            item = {
                "id": fid,
                "company": co.get("name") or sub.get("name", ""),
                "ticker": display,
                "form": form,
                "filed": filed,
                "url": url,
                "filingIndex": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nd}/",
                "quotedPeople": quote_pointers(text),
                "found": today.isoformat(),
            }
            pending["items"].append(item)
            added.append(item)

    pending["items"].sort(key=lambda x: x.get("filed", ""), reverse=True)
    seen["ids"] = seen["ids"][-3000:]
    write_json("pending.json", pending)
    write_json("seen.json", seen)

    if added:
        with open(NOTE_FILE, "w", encoding="utf-8") as f:
            f.write(review_note(added, problems, today.isoformat()))
    print(f"Checked {len(watch)} companies since {since}: {len(added)} new release(s) to review.")
    for p in problems:
        print("  Couldn't check:", p)


if __name__ == "__main__":
    main()
