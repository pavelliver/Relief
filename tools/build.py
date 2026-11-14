"""Builds index.html from src/template.html, tools/build/*.json and src/fonts.

Usage: python3 tools/build.py            -> index.html (installable web app)
       python3 tools/build.py --single   -> also relief.html (no manifest / service worker)
"""
import base64, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
data = json.load(open(HERE / 'build' / 'countries_data.json'))
geo = json.load(open(HERE / 'build' / 'geo.json'))

# Never drawn: too small for a 2-arc-minute grid, flat atolls, or relief missing from the DEM.
NEVER = {'VAT', 'MCO', 'NRU', 'DMA', 'KNA', 'ATG', 'TUV', 'FSM', 'KIR', 'MDV', 'MHL'}
out = []
for c in data:
    pool = 0 if c['id'] in NEVER else (1 if c['cells'] >= 60 and c['bad'] < 0.2 else 2)  # 1 default, 2 micro toggle
    out.append({'i': c['id'], 'n': c['name'], 'a': '|'.join(c['alias']), 'ns': c['ns'][0], 'we': c['we'][0],
                'sp': c['span'], 'c': c['c'], 'b': c['bbox'], 'p': pool, 's': geo['sil'][c['id']]})
payload = 'const DATA=' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\nconst WORLD=' + json.dumps(geo['world'], separators=(',', ':')) + ';'

faces = ''
for fam, w in [('Barlow', 400), ('Barlow', 500), ('Barlow', 600), ('Barlow Condensed', 600), ('Barlow Condensed', 700)]:
    slug = fam.lower().replace(' ', '-')
    b64 = base64.b64encode((REPO / 'src' / 'fonts' / f'{slug}-latin-{w}-normal.woff2').read_bytes()).decode()
    faces += f"@font-face{{font-family:'{fam}';font-style:normal;font-weight:{w};font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2')}}\n"

HEAD = """<meta name="description" content="Name the country from two cross-sections of its terrain.">
<meta name="theme-color" content="#0D1411">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icons/favicon-64.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">"""
SW = """if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}"""

html = (REPO / 'src' / 'template.html').read_text().replace('/*__DATA__*/', payload).replace('/*__FONTS__*/', faces)
(REPO / 'index.html').write_text(html.replace('<!--__HEAD__-->', HEAD).replace('/*__SW__*/', SW))
if '--single' in sys.argv:
    (REPO / 'relief.html').write_text(html.replace('<!--__HEAD__-->\n', '').replace('/*__SW__*/', ''))
print(f"{sum(o['p'] == 1 for o in out)} drawn by default, {sum(o['p'] == 2 for o in out)} with the micro toggle, {len(NEVER)} never drawn; "
      f"index.html {len(html.encode()) // 1024} KB")
