#!/usr/bin/env python3
"""
Checks the data files before the site goes live.

If anything is wrong, it prints what to fix and stops the deploy, so the
last good version of the site stays up.
"""
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CHANNELS = {"Earnings call", "Press release", "Filing", "Interview", "Official X account", "Personal X account"}
RELATIONS = {"", "supplier", "customer", "competitor", "partner"}
TONES = {"", "confident", "same", "cautious"}
MAX_WORDS = 14  # keep every quote under 15 words and link out for the rest

errors = []


def load(name):
    path = os.path.join(DATA, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        errors.append(f"data/{name} is missing.")
    except json.JSONDecodeError as e:
        errors.append(f"data/{name} isn't valid (line {e.lineno}, column {e.colno}: {e.msg}). "
                      "Look for a missing comma, bracket or quote mark near there.")
    return None


def word_count(text):
    parts = re.split(r"\s+", text.replace("…", " ").strip())
    return len([w for w in parts if re.search(r"\w", w)])


def is_date(value):
    try:
        dt.date.fromisoformat(str(value)[:10])
        return len(str(value)) >= 10
    except ValueError:
        return False


def check_quotes(doc):
    quotes = doc.get("quotes")
    if not isinstance(quotes, list):
        errors.append('quotes.json needs a "quotes" list.')
        return 0
    ids = set()
    for n, q in enumerate(quotes, 1):
        where = f"quotes.json, quote {n} ({q.get('id') or 'no id'})"
        for field in ("id", "company", "ticker", "speaker", "date", "channel", "text", "sourceUrl", "verifiedAt"):
            if not str(q.get(field, "")).strip():
                errors.append(f"{where}: '{field}' is empty.")
        if q.get("id") in ids:
            errors.append(f"{where}: this id is used twice. Give each quote its own id.")
        ids.add(q.get("id"))
        for field in ("date", "verifiedAt"):
            if q.get(field) and not is_date(q[field]):
                errors.append(f"{where}: '{field}' must look like 2026-10-22.")
        if q.get("channel") and q["channel"] not in CHANNELS:
            errors.append(f"{where}: channel must be one of: {', '.join(sorted(CHANNELS))}.")
        if q.get("sourceUrl") and not str(q["sourceUrl"]).startswith("https://"):
            errors.append(f"{where}: sourceUrl must start with https://")
        wc = word_count(str(q.get("text", "")))
        if wc > MAX_WORDS:
            errors.append(f"{where}: the quote is {wc} words. Trim it to {MAX_WORDS} or fewer, mark the cut with …, and let the link carry the rest.")
        if q.get("toneDirection", "") not in TONES:
            errors.append(f"{where}: toneDirection must be empty, confident, same or cautious.")
        for r in q.get("related") or []:
            if (r.get("relation") or "") not in RELATIONS:
                errors.append(f"{where}: related company relation must be supplier, customer, competitor or partner.")
    return len(quotes)


def check_corrections(doc):
    items = doc.get("corrections")
    if not isinstance(items, list):
        errors.append('corrections.json needs a "corrections" list.')
        return
    for n, c in enumerate(items, 1):
        if not is_date(c.get("date", "")):
            errors.append(f"corrections.json, item {n}: 'date' must look like 2026-10-22.")
        if not str(c.get("note", "")).strip():
            errors.append(f"corrections.json, item {n}: 'note' is empty. Say what was wrong and what changed.")


def main():
    quotes = load("quotes.json")
    count = check_quotes(quotes) if isinstance(quotes, dict) else 0
    corrections = load("corrections.json")
    if isinstance(corrections, dict):
        check_corrections(corrections)
    for name in ("config.json", "pending.json", "seen.json", "watchlist.json"):
        load(name)
    if errors:
        print("Data check failed, so the site was not updated. Fix these and commit again:\n")
        for e in errors:
            print(" - " + e)
        sys.exit(1)
    print(f"Data check passed: {count} quotes.")


if __name__ == "__main__":
    main()
