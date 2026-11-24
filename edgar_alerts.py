#!/usr/bin/env python3
"""SEC 8-K alert bot (single pass, built for GitHub Actions) -> ntfy push."""
import json
import os
import re
import time

import feedparser
import requests

NTFY_TOPIC = os.environ["NTFY_TOPIC"]
SEC_USER_AGENT = os.environ["SEC_USER_AGENT"]
STATE_FILE = "seen.json"

TICKERS = [
    "NVDA", "MSFT", "AAPL", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "AMD",
    "ORCL", "CRM", "ADBE", "NFLX", "INTC", "QCOM", "MU", "CSCO", "IBM",
    "NOW", "PLTR", "PANW", "AMAT", "LRCX", "KLAC", "ANET", "TXN",
]

ITEMS = {
    "5.02": ("CEO/exec/board change", 5),
    "2.02": ("Earnings results", 4),
    "1.01": ("Material agreement", 4),
    "1.02": ("Agreement terminated", 4),
    "2.01": ("Acquisition/disposal", 4),
    "1.05": ("Cybersecurity incident", 5),
    "4.02": ("Restatement warning", 5),
    "3.01": ("Delisting notice", 5),
    "7.01": ("Reg FD disclosure", 3),
    "8.01": ("Other events", 3),
}

FEED = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    "&CIK={t}&type=8-K&dateb=&owner=include&count=10&output=atom"
)


def push(title, body, priority, url):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=body.encode("utf-8"),
        headers={
            "Title": title.encode("ascii", "ignore").decode(),
            "Priority": str(priority),
            "Click": url,
        },
        timeout=15,
    )


def main():
    first_run = not os.path.exists(STATE_FILE)
    seen = []
    if not first_run:
        with open(STATE_FILE) as f:
            seen = json.load(f)
    seen_set = set(seen)

    for t in TICKERS:
        try:
            r = requests.get(
                FEED.format(t=t), headers={"User-Agent": SEC_USER_AGENT}, timeout=20
            )
            for e in feedparser.parse(r.content).entries:
                uid = e.get("id") or e.get("link")
                if uid in seen_set:
                    continue
                seen.append(uid)
                seen_set.add(uid)
                if first_run:
                    continue
                text = re.sub(r"<[^>]+>", " ", e.get("summary", ""))
                codes = re.findall(r"Item (\d\.\d{2})", text)
                hits = [ITEMS[c] for c in codes if c in ITEMS]
                if not hits:
                    continue
                prio = max(p for _, p in hits)
                labels = ", ".join(sorted({l for l, _ in hits}))
                push(f"{t} 8-K: {labels}", " ".join(text.split())[:300], prio, e.link)
                print(f"ALERT {t}: {labels}")
        except Exception as ex:
            print(f"{t} error: {ex}")
        time.sleep(0.3)

    with open(STATE_FILE, "w") as f:
        json.dump(seen[-3000:], f)


if __name__ == "__main__":
    main()
