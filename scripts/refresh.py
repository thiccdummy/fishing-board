#!/usr/bin/env python3
"""
Refresh ForeverEcon prices into assets/data.js

Reads the public item pages on foreverecon.com (robots.txt allows /), pulls the
same five numbers the site shows -- current price, lowest buyout, listed depth,
estimated sold/day and the 7-day trend -- and rewrites assets/data.js.

Design notes
------------
* No third-party packages. GitHub Actions has Python preinstalled.
* Only ~40 requests per run, with a delay, a descriptive UA and retries.
* A failed page never blanks the board: the previous value is kept from
  data/latest.json, and the item is flagged as stale.
* Every run appends one line to data/history.jsonl so you build your own trend.

Usage
-----
    python3 scripts/refresh.py            # normal refresh
    python3 scripts/refresh.py --dry-run  # fetch + print, write nothing
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HISTORY = DATA_DIR / "history.jsonl"
CACHE = DATA_DIR / "latest.json"
OUT_JS = ROOT / "assets" / "data.js"
CONFIG = ROOT / "assets" / "config.js"

BASE = "https://foreverecon.com"
UA = (
    "GuildFishingBoard/1.0 (personal guild dashboard; "
    "reads ~40 public pages every 2h; contact: set-your-email-here)"
)
DELAY = 0.35
TIMEOUT = 25

# --------------------------------------------------------------------------
# Catalog.  slug = the /item/<slug> path on foreverecon.com.
# kind: fish | clam | pearl | meat | cooked | reagent
# zones/skill are the site's Classic-era data (not re-verified in Forever).
# --------------------------------------------------------------------------
CATALOG = [
    # ---- fish -------------------------------------------------------------
    dict(key="darkclaw-lobster", slug="i-darkclaw-lobster", name="Darkclaw Lobster",
         kind="fish", skill=205, water="Open water",
         zones=["Tanaris", "Feralas", "Azshara", "Dustwallow Marsh", "Swamp of Sorrows"]),
    dict(key="whitescale-salmon", slug="i-raw-whitescale-salmon", name="Raw Whitescale Salmon",
         kind="fish", skill=330, water="Open water",
         zones=["Azshara", "Winterspring"]),
    dict(key="sunscale-salmon", slug="i-raw-sunscale-salmon", name="Raw Sunscale Salmon",
         kind="fish", skill=330, water="Pools & open water", note="Daytime only",
         zones=["Azshara", "Feralas", "Winterspring"]),
    dict(key="nightfin-snapper", slug="raw-nightfin-snapper", name="Raw Nightfin Snapper",
         kind="fish", skill=330, water="Pools & open water", note="Night only",
         zones=["Feralas", "Moonglade", "Western Plaguelands", "Azshara"]),
    dict(key="winter-squid", slug="winter-squid", name="Winter Squid",
         kind="fish", skill=330, water="Open water", note="Winterspring only",
         zones=["Winterspring"]),
    dict(key="stonescale-eel", slug="i-stonescale-eel", name="Stonescale Eel",
         kind="fish", skill=230, water="Pools & open water",
         zones=["Azshara", "Feralas", "Tanaris", "Blasted Lands"]),
    dict(key="glossy-mightfish", slug="i-raw-glossy-mightfish", name="Raw Glossy Mightfish",
         kind="fish", skill=230, water="Open water",
         zones=["Azshara", "Feralas", "Tanaris"]),
    dict(key="spotted-yellowtail", slug="i-raw-spotted-yellowtail", name="Raw Spotted Yellowtail",
         kind="fish", skill=205, water="Open water",
         zones=["Stranglethorn Vale", "Tanaris", "Feralas", "Azshara"]),
    dict(key="mithril-head-trout", slug="i-mithril-head-trout", name="Raw Mithril Head Trout",
         kind="fish", skill=205, water="Open water",
         zones=["Stranglethorn Vale", "Badlands", "Swamp of Sorrows", "Desolace", "Dustwallow Marsh"]),
    dict(key="deviate-fish", slug="i-deviate-fish", name="Deviate Fish",
         kind="fish", skill=55, water="Pools & open water",
         zones=["The Barrens"]),
    dict(key="greater-sagefish", slug="i-raw-greater-sagefish", name="Raw Greater Sagefish",
         kind="fish", skill=230, water="Pools only",
         zones=["The Hinterlands", "Felwood", "Un'Goro Crater", "Azshara"]),
    dict(key="spinefin-halibut", slug="i-raw-spinefin-halibut", name="Raw Spinefin Halibut",
         kind="fish", skill=330, water="Open water",
         zones=["Eastern Plaguelands", "Western Plaguelands"]),
    dict(key="firefin-snapper", slug="i-firefin-snapper", name="Firefin Snapper",
         kind="fish", skill=130, water="Pools & open water",
         zones=["Stranglethorn Vale", "Desolace", "Arathi Highlands", "Hillsbrad Foothills", "Tanaris"]),
    dict(key="oily-blackmouth", slug="i-oily-blackmouth", name="Oily Blackmouth",
         kind="fish", skill=55, water="Pools & open water",
         zones=["Westfall", "Darkshore", "Wetlands", "Stranglethorn Vale", "Desolace"]),
    dict(key="redgill", slug="i-raw-redgill", name="Raw Redgill",
         kind="fish", skill=230, water="Open water",
         zones=["Tanaris", "Feralas", "Azshara"]),
    dict(key="sagefish", slug="i-raw-sagefish", name="Raw Sagefish",
         kind="fish", skill=130, water="Pools only",
         zones=["Thousand Needles", "Dustwallow Marsh", "Wetlands", "Ashenvale", "Hillsbrad Foothills"]),
    dict(key="plated-armorfish", slug="i-raw-plated-armorfish", name="Raw Plated Armorfish",
         kind="fish", skill=230, water="Open water",
         zones=["Azshara", "Feralas", "Tanaris", "Blasted Lands"]),
    dict(key="summer-bass", slug="i-raw-summer-bass", name="Raw Summer Bass",
         kind="fish", skill=130, water="Open water", note="Seasonal (Classic: summer)",
         zones=["Hillsbrad Foothills", "Arathi Highlands", "The Hinterlands"]),

    # ---- clams + pearls ---------------------------------------------------
    dict(key="golden-pearl", slug="golden-pearl", name="Golden Pearl",
         kind="pearl", skill=230, water="From clams",
         zones=["Tanaris", "Azshara", "Feralas", "Winterspring"]),
    dict(key="black-pearl", slug="i-black-pearl", name="Black Pearl",
         kind="pearl", skill=230, water="From clams",
         zones=["Tanaris", "Azshara", "Feralas", "Winterspring"]),
    dict(key="iridescent-pearl", slug="i-iridescent-pearl", name="Iridescent Pearl",
         kind="pearl", skill=130, water="From clams",
         zones=["Stranglethorn Vale", "Hillsbrad Foothills", "Desolace", "Dustwallow Marsh"]),
    dict(key="small-lustrous-pearl", slug="i-small-lustrous-pearl", name="Small Lustrous Pearl",
         kind="pearl", skill=55, water="From clams",
         zones=["Westfall", "Loch Modan", "Darkshore", "Wetlands"]),
    dict(key="zesty-clam-meat", slug="i-zesty-clam-meat", name="Zesty Clam Meat",
         kind="meat", skill=230, water="From clams", zones=["Tanaris"]),
    dict(key="tangy-clam-meat", slug="i-tangy-clam-meat", name="Tangy Clam Meat",
         kind="meat", skill=130, water="From clams", zones=["Stranglethorn Vale"]),
    dict(key="clam-meat", slug="i-clam-meat", name="Clam Meat",
         kind="meat", skill=55, water="From clams", zones=["Westfall"]),
    dict(key="giant-clam-meat", slug="i-giant-clam-meat", name="Giant Clam Meat",
         kind="meat", skill=None, water="From clams", zones=[]),

    # ---- cooked -----------------------------------------------------------
    dict(key="lobster-stew", slug="i-lobster-stew", name="Lobster Stew", kind="cooked"),
    dict(key="baked-salmon", slug="i-baked-salmon", name="Baked Salmon", kind="cooked"),
    dict(key="cooked-yellowtail", slug="i-spotted-yellowtail", name="Spotted Yellowtail", kind="cooked"),
    dict(key="poached-sunscale", slug="i-poached-sunscale-salmon", name="Poached Sunscale Salmon", kind="cooked"),
    dict(key="cooked-mightfish", slug="i-cooked-glossy-mightfish", name="Cooked Glossy Mightfish", kind="cooked"),
    dict(key="cooked-halibut", slug="i-spinefin-halibut", name="Spinefin Halibut", kind="cooked"),
    dict(key="grilled-squid", slug="grilled-squid", name="Grilled Squid", kind="cooked"),
    dict(key="nightfin-soup", slug="nightfin-soup", name="Nightfin Soup", kind="cooked"),
    dict(key="sagefish-delight", slug="i-sagefish-delight", name="Sagefish Delight", kind="cooked"),

    # ---- reagents ---------------------------------------------------------
    dict(key="soothing-spices", slug="soothing-spices", name="Soothing Spices", kind="reagent"),
    dict(key="spring-water", slug="refreshing-spring-water", name="Refreshing Spring Water", kind="reagent"),
    dict(key="stonescale-oil", slug="stonescale-oil", name="Stonescale Oil", kind="reagent"),
]

# recipe: output key -> list of (input key, qty, is_fish)
RECIPES = {
    "lobster-stew":        dict(inputs=[("darkclaw-lobster", 1, True), ("spring-water", 1, False)]),
    "baked-salmon":        dict(inputs=[("whitescale-salmon", 1, True), ("soothing-spices", 1, False)]),
    "cooked-yellowtail":   dict(inputs=[("spotted-yellowtail", 1, True)]),
    "poached-sunscale":    dict(inputs=[("sunscale-salmon", 1, True)]),
    "cooked-mightfish":    dict(inputs=[("glossy-mightfish", 1, True), ("soothing-spices", 1, False)]),
    "cooked-halibut":      dict(inputs=[("spinefin-halibut", 1, True)]),
    "grilled-squid":       dict(inputs=[("winter-squid", 1, True), ("soothing-spices", 1, False)]),
    "nightfin-soup":       dict(inputs=[("nightfin-snapper", 1, True), ("spring-water", 1, False)]),
    "sagefish-delight":    dict(inputs=[("greater-sagefish", 1, True), ("soothing-spices", 1, False)]),
}

ZONES = [
    dict(name="Tanaris", skill=230, hub="Gadgetzan", access="Neutral hub", tier=1,
         catches=["darkclaw-lobster", "golden-pearl", "black-pearl", "zesty-clam-meat",
                  "stonescale-eel", "spotted-yellowtail", "glossy-mightfish", "mithril-head-trout"],
         note="The one zone where the whole loot table sells. Clams at skill 230, not 330."),
    dict(name="Feralas", skill=330, hub="Feathermoon Stronghold", access="Alliance town", tier=1,
         catches=["nightfin-snapper", "sunscale-salmon", "darkclaw-lobster", "golden-pearl",
                  "stonescale-eel", "glossy-mightfish", "redgill"],
         note="Nightfin at night, Sunscale by day. Best single-zone variety for cooking."),
    dict(name="Azshara", skill=330, hub="Talrendis Point", access="Alliance FP", tier=2,
         catches=["whitescale-salmon", "sunscale-salmon", "nightfin-snapper", "darkclaw-lobster",
                  "golden-pearl", "greater-sagefish", "stonescale-eel"],
         note="The Alliance route to Whitescale Salmon and Baked Salmon."),
    dict(name="Winterspring", skill=330, hub="Everlook", access="Neutral hub", tier=2,
         catches=["winter-squid", "whitescale-salmon", "sunscale-salmon", "golden-pearl"],
         note="Only source of Winter Squid. Stockpile before the Dec 9 raid unlock."),
    dict(name="Dustwallow Marsh", skill=205, hub="Theramore", access="Alliance town", tier=3,
         catches=["darkclaw-lobster", "mithril-head-trout", "greater-sagefish", "tangy-clam-meat"],
         note="Lowest-skill lobster on the Alliance side."),
    dict(name="Stranglethorn Vale", skill=205, hub="Booty Bay", access="Neutral hub", tier=3,
         catches=["mithril-head-trout", "spotted-yellowtail", "firefin-snapper",
                  "oily-blackmouth", "tangy-clam-meat"],
         note="Deep pool-fishing market, low unit value."),
    dict(name="Blasted Lands", skill=330, hub="Nethergarde Keep", access="Alliance town", tier=3,
         catches=["stonescale-eel", "plated-armorfish"],
         note="Stonescale Eel swarms; deepest market on the board."),
    dict(name="The Hinterlands", skill=230, hub="Aerie Peak", access="Alliance town", tier=4,
         catches=["greater-sagefish"],
         note="Sagefish pools, but cooking sagefish loses money. Sell raw."),
    dict(name="Felwood", skill=330, hub="Emerald Sanctuary", access="Alliance town", tier=4,
         catches=["greater-sagefish", "nightfin-snapper"],
         note="Sagefish pools plus night-only Nightfin."),
    dict(name="The Barrens", skill=55, hub="Ratchet", access="Neutral hub", tier=4,
         catches=["deviate-fish"],
         note="Horde territory, but Ratchet is neutral by boat from Booty Bay."),
    dict(name="Westfall", skill=55, hub="Sentinel Hill", access="Alliance town", tier=4,
         catches=["oily-blackmouth", "small-lustrous-pearl", "clam-meat"],
         note="Home-zone clam and pool farming; low value per catch."),
    dict(name="Wetlands", skill=130, hub="Menethil Harbor", access="Alliance town", tier=4,
         catches=["greater-sagefish", "oily-blackmouth", "small-lustrous-pearl"],
         note="Close to Ironforge if you want a short session."),
]


# --------------------------------------------------------------------------
# Fetch + parse
# --------------------------------------------------------------------------
def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                if r.status != 200:
                    raise urllib.error.HTTPError(url, r.status, "bad status", r.headers, None)
                return r.read().decode("utf-8", "replace")
        except Exception as exc:                      # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise last


def to_lines(page: str) -> list[str]:
    page = re.sub(r"<script[\s\S]*?</script>", " ", page, flags=re.I)
    page = re.sub(r"<style[\s\S]*?</style>", " ", page, flags=re.I)
    page = re.sub(r"<[^>]+>", "\n", page)
    page = html_mod.unescape(page).replace("\u2212", "-").replace("\xa0", " ")
    return [ln.strip() for ln in page.split("\n") if ln.strip()]


CURRENCY = re.compile(
    r"^(?:(\d+(?:\.\d+)?)\s*g)?\s*(?:(\d+(?:\.\d+)?)\s*s)?\s*(?:(\d+(?:\.\d+)?)\s*c)?$",
    re.I,
)


def parse_money(text: str):
    """'1g44s73c' / '1.4g' / '9.0s' / '76c' -> float copper. None if not money."""
    t = text.strip().lower().replace(",", "")
    if not t or t in {"-", "--", "n/a", "none"}:
        return None
    m = CURRENCY.match(t)
    if not m or not any(m.groups()):
        return None
    g, s, c = (float(x) if x else 0.0 for x in m.groups())
    return int(round(g * 10000 + s * 100 + c))


def find_value(lines: list[str], label: str, kind: str = "text"):
    """Return the value rendered just after `label`."""
    for i, ln in enumerate(lines):
        if not ln.lower().startswith(label.lower()):
            continue
        for j in range(i + 1, min(i + 5, len(lines))):
            cand = lines[j]
            if kind == "money":
                # Value may be one element ("1.4g") or split ("1" "g" "44" "s").
                # Try windows of increasing length and keep the most complete parse.
                best = None
                for width in range(1, 7):
                    chunk = "".join(lines[j:j + width])
                    got = parse_money(chunk)
                    if got is not None and (best is None or len(chunk) > best[0]):
                        best = (len(chunk), got)
                if best is not None:
                    return best[1]
            elif kind == "int":
                m = re.match(r"^([\d,]+)$", cand)
                if m:
                    return int(m.group(1).replace(",", ""))
            elif kind == "pct":
                m = re.match(r"^(-?\d+(?:\.\d+)?)\s*%$", cand)
                if m:
                    return float(m.group(1))
            else:
                if cand and not cand.startswith(("Median", "Depth", "Listed", "Every", "Prices")):
                    return cand
        return None
    return None


def scrape(slug: str) -> dict:
    lines = to_lines(fetch(f"{BASE}/item/{slug}"))
    return {
        "price": find_value(lines, "Current price", "money"),
        "buyout": find_value(lines, "Lowest buyout", "money"),
        "listed": find_value(lines, "Listed", "int"),
        "sold": find_value(lines, "Est. sold / day", "int"),
        "trend": find_value(lines, "vs 7D avg", "pct"),
        # Client item table: what a vendor pays for one. Static, and no auction cut.
        "vendor": find_value(lines, "Vendor sells for", "money"),
    }


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except json.JSONDecodeError:
            pass
    return {"items": {}, "runs": []}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cache = load_cache()
    prev = cache.get("items", {})
    items: dict[str, dict] = {}
    failures = 0

    for idx, item in enumerate(CATALOG, 1):
        key, slug = item["key"], item["slug"]
        row = {k: v for k, v in item.items() if k not in {"slug"}}
        row["slug"] = slug
        row["url"] = f"{BASE}/item/{slug}"
        try:
            got = scrape(slug)
            price_ok = isinstance(got["price"], (int, float))
            row.update(got)
            if not price_ok and key in prev and isinstance(prev[key].get("price"), (int, float)):
                row["price"] = prev[key].get("price")
                row["price_carried"] = True
            row["fetched"] = True
            if not isinstance(row.get("vendor"), (int, float)) and \
                    isinstance(prev.get(key, {}).get("vendor"), (int, float)):
                row["vendor"] = prev[key]["vendor"]
            flag = "" if price_ok else "  (no price listed)"
            print(f"[{idx:2}/{len(CATALOG)}] {row['name']:<28} "
                  f"price={row['price']} buyout={row['buyout']} sold={row['sold']} "
                  f"vendor={row.get('vendor')}{flag}")
        except Exception as exc:                       # noqa: BLE001
            failures += 1
            print(f"[{idx:2}/{len(CATALOG)}] {item['name']:<28} FAILED: {exc}", file=sys.stderr)
            row["fetched"] = False
            if key in prev:
                row.update({k: prev[key].get(k) for k in
                            ("price", "buyout", "listed", "sold", "trend", "vendor")})
                row["price_carried"] = True
        items[key] = row
        time.sleep(DELAY)

    now = datetime.now(timezone.utc)
    payload = {
        "generated": now.isoformat(timespec="seconds"),
        "generated_display": now.strftime("%b %d, %Y %H:%M UTC"),
        "market": "Normal Alliance US",
        "source": BASE,
        "source_note": "Prices from AHledger player scans via ForeverEcon. Unofficial.",
        "failures": failures,
        "items": items,
        "recipes": RECIPES,
        "zones": ZONES,
    }

    if args.dry_run:
        print(json.dumps(payload["items"], indent=2)[:2000])
        return 0

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(payload, indent=2) + "\n")

    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(
        "/* Generated by scripts/refresh.py -- do not edit by hand. */\n"
        "window.FOREVER_DATA = "
        + json.dumps(payload, separators=(",", ":"))
        + ";\n"
    )

    snap = {k: v.get("buyout") for k, v in items.items() if isinstance(v.get("buyout"), (int, float))}
    with HISTORY.open("a") as fh:
        fh.write(json.dumps({"ts": payload["generated"], "buyout": snap}) + "\n")

    priced = sum(1 for v in items.values() if isinstance(v.get("price"), (int, float)))
    print(f"\nWrote {OUT_JS.relative_to(ROOT)}  ({priced}/{len(items)} items priced, {failures} fetch failures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
