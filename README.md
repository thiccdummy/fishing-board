# Guild Fishing Board

A one-page fishing + cooking profit board for **World of Warcraft Forever**, built from the
public numbers on [ForeverEcon](https://foreverecon.com/fishing) (prices originally from
AHledger player scans).

Pearls are priced **per pearl**, not per cast — a pearl is a roll of the dice inside a clam, so it sits high on the board without being a reliable per-catch number.

It answers three questions for a guildmate:

1. **What do I fish?** — ranked by gold per catch, then by how much the market actually absorbs.
2. **Where do I stand?** — the zone list carries the Alliance hub, the skill gate and the catches.
3. **Do I cook it or sell it raw?** — including the cases where cooking *loses* money.

No frameworks, no build step, no accounts, no paid services.

---

## Send it to a guildmate (the thing most people actually want)

```bash
python3 scripts/build_single.py
```

That produces **`dist/guild-fishing-board.html`** — one 48 KB file with the CSS, JS and the
current price snapshot baked in.

- It opens by **double-clicking**, in Chrome, Firefox, Edge, Safari, on phone or desktop.
- No server, no internet, no `assets/` folder, no `localhost` link needed.
- Attach it in Discord/DM, or send `dist/guild-fishing-board-site.zip` if a mail filter
  objects to `.html` attachments.

A `localhost:8000` link will never work for anyone but you — that address means "this
machine". For a clickable link you both can use, host it (Option A or B below); the single
file is also published at `/guild-fishing-board.html` on the hosted site.

---

## Run it right now

```bash
cd fishing-board
python3 -m http.server 8000
# open http://localhost:8000
```

Or just double-click `index.html` — it works from `file://` too, because the data is a
plain script (`assets/data.js`), not a `fetch()` call.

Refresh the numbers by hand at any time:

```bash
python3 scripts/refresh.py
```

---

## Host it for free (pick one)

### Option A — GitHub Pages (recommended: auto-refresh + free hosting)

1. Create a **public** repo and push this folder:
   ```bash
   cd fishing-board
   git init && git add . && git commit -m "fishing board"
   git branch -M main
   git remote add origin git@github.com:YOU/fishing-board.git
   git push -u origin main
   ```
2. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Repo **Settings → Actions → General → Workflow permissions: Read and write**.
4. Open the **Actions** tab → *Refresh prices* → **Run workflow** once.
5. Your board is at `https://YOU.github.io/fishing-board/`.

From then on, `.github/workflows/refresh.yml` refreshes every 2 hours and redeploys.
Cost: **$0** — scheduled Actions and Pages hosting are free for public repos.

### Option B — Cloudflare Pages / Netlify Drop (no git)

Drag the folder onto [pages.cloudflare.com](https://pages.cloudflare.com) or
[app.netlify.com/drop](https://app.netlify.com/drop). Free. There is no cron, so refresh
by running `python3 scripts/refresh.py` and re-uploading (or connect the repo and let the
host's own scheduled build run it).

### Option C — one file in the guild Discord

`python3 scripts/refresh.py`, then paste the output of:

```bash
python3 - <<'PY'
import json;d=json.load(open("data/latest.json"))
print(d["generated_display"], d["market"])
PY
```

…or just use the **Copy shopping list** button on the board itself.

---

## Customising

| File | What to change |
|---|---|
| `assets/config.js` | Guild name, market label, default auction cut, raid countdown |
| `scripts/refresh.py` → `CATALOG` | Which items are tracked (add a `key`, `slug`, `name`, `kind`) |
| `scripts/refresh.py` → `RECIPES` | Recipe inputs, and which ones are fish you catch yourself |
| `scripts/refresh.py` → `ZONES` | Zone cards, Alliance hubs, catches |
| `assets/style.css` | Colours |

`assets/data.js` and `data/latest.json` are generated — don't hand-edit them.

---

## How "live" this actually is (honest version)

| | |
|---|---|
| **Refresh cadence** | Every 2 hours via GitHub Actions (cron is best-effort; GitHub can delay it) |
| **True real-time?** | No. ForeverEcon sends no `Access-Control-Allow-Origin`, so a browser cannot call it directly from your page. Every "live" dashboard built on it has to refresh server-side like this. |
| **If they add CORS or an API later** | Swap `assets/data.js` for a `fetch()` in `app.js` and you get on-page freshness |
| **GitHub gotcha** | Scheduled workflows pause after ~60 days with no commits. The bot commits whenever prices change, which is usually often enough — if the board goes quiet, hit **Run workflow** once |
| **Politeness** | ~38 requests per run, 0.35 s apart, descriptive User-Agent, retries. `robots.txt` allows `/` and disallows `/api/` — this only reads `/item/*` pages |
| **Failure behaviour** | A failed page keeps its last known price and is flagged; it never blanks the board |
| **History** | Each run appends to `data/history.jsonl`, so you own a price time-series the source doesn't publish |

## What the numbers mean (and don't)

- **Net / unit** = cooked buyout − auction cut − spices/water you must buy. Your fishing time
  is not charged, because nobody can price it without drop rates.
- **Market / day** = buyout × sold/day × (1 − cut). It is pooled across **every realm** in the
  market, so it is a regional ceiling shared by all sellers — not your income.
- **No gold-per-hour anywhere.** ForeverEcon explicitly refuses to publish expected value per
  cast because drop rates don't exist publicly, and this board follows that rule.
- **Zone loot and skill gates are original-game data**, carried over and not re-verified in
  Forever. Treat them as strong defaults, not gospel.
- **Medians are padded.** The board prices to the *lowest buyout*, which is what actually sells.

## Attribution

Prices belong to [ForeverEcon](https://foreverecon.com) and AHledger. This is an unofficial
guild tool, not affiliated with or endorsed by Blizzard Entertainment. If the author of
ForeverEcon asks you to stop reading the pages, stop — and ask them for a feed instead.
