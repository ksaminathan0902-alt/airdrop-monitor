"""
Airdrop Monitor — GitHub Actions version
Runs once per trigger, reads/writes seen_airdrops.json for state
"""

import os
import json
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
MIN_RATING         = 3
STATE_FILE         = "seen_airdrops.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─── STATE ────────────────────────────────────────────────────────────────────

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"[Telegram error] {e}")

def format_alert(airdrop):
    stars = "⭐" * airdrop.get("rating", 0)
    return (
        f"🚀 <b>NEW AIRDROP FOUND</b>\n\n"
        f"<b>{airdrop['name']}</b>\n"
        f"Rating : {stars}\n"
        f"Value  : {airdrop.get('value', '?')}\n"
        f"Req    : {airdrop.get('requirements', 'See link')}\n"
        f"Source : {airdrop['source']}\n"
        f"Link   : {airdrop['url']}\n\n"
        f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</i>"
    )

# ─── SCRAPERS ─────────────────────────────────────────────────────────────────

def scrape_airdrops_io():
    results = []
    try:
        resp = requests.get("https://airdrops.io/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article.airdrop-item, div.airdrop-item, div.coin-airdrop")
        if not cards:
            cards = soup.select("div.row div[class*='airdrop']")
        for card in cards:
            try:
                name_tag  = card.select_one("h3, h2, .airdrop-name, .title")
                link_tag  = card.select_one("a[href]")
                value_tag = card.select_one(".airdrop-value, .value, [class*='worth']")
                req_tag   = card.select_one(".airdrop-requirements, .requirements, [class*='req']")
                stars     = len(card.select(".fa-star, .star.active, [class*='star-filled']"))
                if not name_tag or not link_tag:
                    continue
                name = name_tag.get_text(strip=True)
                url  = link_tag["href"]
                if not url.startswith("http"):
                    url = "https://airdrops.io" + url
                results.append({
                    "id": f"airdroprio_{url}", "name": name, "url": url,
                    "value": value_tag.get_text(strip=True) if value_tag else "?",
                    "requirements": req_tag.get_text(strip=True)[:100] if req_tag else "See link",
                    "rating": min(stars, 5), "source": "airdrops.io",
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[airdrops.io error] {e}")
    return results


def scrape_airdropalert():
    results = []
    try:
        resp = requests.get("https://airdropalert.com/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.airdrop-card, article, div.card")
        for card in cards:
            try:
                name_tag  = card.select_one("h2, h3, .card-title, .airdrop-title")
                link_tag  = card.select_one("a[href]")
                value_tag = card.select_one("[class*='value'], [class*='worth'], .amount")
                stars     = len(card.select("[class*='star-on'], [class*='active-star'], .fa-star"))
                if not name_tag or not link_tag:
                    continue
                name = name_tag.get_text(strip=True)
                url  = link_tag["href"]
                if not url.startswith("http"):
                    url = "https://airdropalert.com" + url
                results.append({
                    "id": f"airdropalert_{url}", "name": name, "url": url,
                    "value": value_tag.get_text(strip=True) if value_tag else "?",
                    "requirements": "See link",
                    "rating": min(stars, 5), "source": "airdropalert.com",
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[airdropalert error] {e}")
    return results


def scrape_coinmarketcap():
    results = []
    try:
        url  = "https://coinmarketcap.com/airdrop/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr, div[class*='airdrop'] div[class*='row']")
        for row in rows:
            try:
                name_tag = row.select_one("a, p, span")
                link_tag = row.select_one("a[href]")
                if not name_tag:
                    continue
                name = name_tag.get_text(strip=True)
                href = link_tag["href"] if link_tag else url
                if not href.startswith("http"):
                    href = "https://coinmarketcap.com" + href
                if len(name) < 2:
                    continue
                results.append({
                    "id": f"cmc_{href}", "name": name, "url": href,
                    "value": "See CMC", "requirements": "See link",
                    "rating": 3, "source": "coinmarketcap.com",
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[coinmarketcap error] {e}")
    return results

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    seen = load_seen()
    print(f"Loaded {len(seen)} previously seen airdrops")

    all_airdrops = scrape_airdrops_io() + scrape_airdropalert() + scrape_coinmarketcap()
    print(f"Found {len(all_airdrops)} total listings")

    new_count = 0
    for airdrop in all_airdrops:
        if airdrop["rating"] < MIN_RATING:
            continue
        if airdrop["id"] not in seen:
            seen.add(airdrop["id"])
            send_telegram(format_alert(airdrop))
            print(f"[NEW] {airdrop['name']} ({airdrop['source']})")
            new_count += 1
            time.sleep(1)

    save_seen(seen)
    print(f"Done. {new_count} new alerts sent.")

if __name__ == "__main__":
    main()
