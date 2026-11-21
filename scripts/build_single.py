#!/usr/bin/env python3
"""
Bundle the multi-file board into ONE self-contained .html file.

Output: dist/guild-fishing-board.html

That file has the CSS, JS and the whole price snapshot inlined, so it works by
double-clicking it on any machine with any browser, with no server, no network
and no companion files. This is the file to send to guildmates.

Run after every refresh (the GitHub workflow does this automatically):
    python3 scripts/build_single.py
"""

from __future__ import annotations

import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
OUT = DIST / "guild-fishing-board.html"
ZIP = DIST / "guild-fishing-board-site.zip"

CSS_TAG = '<link rel="stylesheet" href="assets/style.css">'
JS_FILES = ["config.js", "data.js", "app.js"]


def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "style.css").read_text(encoding="utf-8")

    if CSS_TAG not in html:
        fail("could not find the stylesheet tag in index.html")

    html = html.replace(CSS_TAG, "<style>\n" + css + "\n</style>")

    for name in JS_FILES:
        path = ROOT / "assets" / name
        if not path.exists():
            fail(f"missing {path} — run scripts/refresh.py first")
        js = path.read_text(encoding="utf-8")
        # A literal </script> inside a string would end the block early.
        js = js.replace("</script", "<\\/script")
        tag = f'<script src="assets/{name}"></script>'
        if tag not in html:
            fail(f"could not find the script tag for {name}")
        html = html.replace(tag, "<script>\n" + js + "\n</script>")

    leftovers = re.findall(r'(?:src|href)="assets/[^"]+"', html)
    if leftovers:
        fail("still references external files: " + ", ".join(leftovers))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = html.replace(
        "</head>",
        f'<meta name="generator" content="guild-fishing-board (single file, built {stamp})">\n</head>',
    )

    DIST.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")

    # A zip of the normal multi-file version, for anyone who wants to edit it.
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT / "index.html", "fishing-board/index.html")
        for f in sorted((ROOT / "assets").glob("*")):
            z.write(f, f"fishing-board/assets/{f.name}")
        z.write(ROOT / "README.md", "fishing-board/README.md")

    kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT.relative_to(ROOT)}  ({kb:.0f} KB, self-contained)")
    print(f"Wrote {ZIP.relative_to(ROOT)}  ({ZIP.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
