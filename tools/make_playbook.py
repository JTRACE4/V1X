"""Build assets/BRAIN-Playbook.pdf from assets/playbook-source.html.

    python tools/make_playbook.py

Needs Playwright with Chromium (pip install playwright && playwright install chromium). Icons and images come from static/;
the SVG icons are embedded as data URIs because Chromium won't apply local SVG files as CSS masks.
"""
import base64
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "playbook-source.html")
OUT = os.path.join(ROOT, "assets", "BRAIN-Playbook.pdf")
STATIC = os.path.join(ROOT, "static")


def build(out=OUT):
    html = open(SRC, encoding="utf-8").read()

    def _svg(m):
        data = open(os.path.join(STATIC, m.group(1)), "rb").read()
        return "url(data:image/svg+xml;base64," + base64.b64encode(data).decode() + ")"

    html = re.sub(r"url\((ico-[a-z-]+\.svg)\)", _svg, html)
    tmp = tempfile.mkdtemp(prefix="playbook-")
    try:
        for f in ("logo.png", "hero.jpg"):
            shutil.copy(os.path.join(STATIC, f), tmp)
        page = os.path.join(tmp, "index.html")
        open(page, "w", encoding="utf-8").write(html)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto("file://" + page)
            pg.wait_for_load_state("networkidle")
            pg.pdf(path=out, format="Letter", print_background=True, prefer_css_page_size=True,
                   margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            b.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else OUT))
