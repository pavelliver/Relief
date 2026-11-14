# Relief

Name the country from two cross-sections of its terrain.

**Play it here: https://pavelliver.github.io/Relief/**

You get two elevation profiles of a hidden country: north → south and west → east, where every point is the mean elevation of that slice of the country. Type a guess (Enter or **Submit**). Every miss tells you how far away the answer is and in which direction.

## Modes

- **Classic:** 5 countries, up to 5 000 points each (25 000 per game). Misses and time cut into the points.
- **Survival:** one country after another until one beats you. Each country's value drains to zero in 2 minutes. The run ends when it reaches zero, after 6 misses, or when you give up. Your score is the number of countries found.

## Scoring

`points = 5000 × misses factor × time factor`

| Misses before the right answer | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Factor | 1.00 | 0.80 | 0.62 | 0.46 | 0.32 | 0.20 |

A sixth miss, or giving up, scores 0.

- **Classic time factor:** full for the first 10 s, then `exp(−(t − 10) / 100)`, never below 0.25 (30 s ≈ 0.82, 1 min ≈ 0.61, 2 min ≈ 0.33).
- **Survival time factor:** full for the first 10 s, then falls in a straight line to 0 at 2:00.

## Install it on your phone

- **Android (Chrome):** open the link, then ⋮ menu → **Install app**.
- **iPhone (Safari):** open the link, then **Share** → **Add to Home Screen**.

Once loaded it works without internet.

## What's inside

- **197 countries:** the 193 UN members plus Vatican City, Palestine, Kosovo and Taiwan. All of them can be guessed.
- **Which countries are drawn:** 173 by default. A start-screen toggle adds 13 micro-states and small islands. 11 are never drawn: Vatican City, Monaco and Nauru are too small for the elevation grid, the Maldives, Tuvalu, Kiribati and the Marshall Islands are flat atolls, and Dominica, Saint Kitts and Nevis, Antigua and Barbuda and Micronesia have no usable relief in the data.
- **Main territory only:** each profile covers a country's main territory. Islands and exclaves more than 350 km from it are dropped, such as French Guiana, Alaska, Hawaii, Svalbard and the Canaries. Malaysia keeps both halves.
- **Distance** is measured along the globe between territory centres. **Direction** is read as on a map, taking the shorter way round.

## Files

| File | Purpose |
|---|---|
| `index.html` | The game, with all data and fonts embedded (built, do not edit) |
| `src/template.html` | Game source: layout, styles, logic |
| `src/fonts/` | Barlow and Barlow Condensed, embedded at build time |
| `tools/build/` | Computed profiles, outlines and world map (JSON) |
| `tools/` | Data pipeline |
| `manifest.webmanifest`, `sw.js`, `icons/` | Home-screen install and offline start |

## Making changes

Interface or rules: edit `src/template.html`, then run:

```
python3 tools/build.py
```

Recomputing the profiles (needs `pip install numpy scipy shapely`, downloads about 330 MB into the git-ignored `tools/data/`):

```
tools/fetch_data.sh
python3 tools/process.py   # elevation profiles  -> tools/build/countries_data.json
python3 tools/geo.py       # outlines, world map -> tools/build/geo.json
python3 tools/build.py
```

`python3 tools/build.py --single` also writes `relief.html` (git-ignored): one file without the install features, to open straight from disk.

## Credits

- **Elevation:** NOAA ETOPO2v2 (2006), 2-arc-minute grid, public domain, via the [hperantunes/ETOPO2v2gParser](https://github.com/hperantunes/ETOPO2v2gParser) mirror.
- **Borders:** [Natural Earth](https://www.naturalearthdata.com/) admin-0 countries, 1:10m and 1:50m, public domain.
- **Country names and alternative spellings:** [mledoze/countries](https://github.com/mledoze/countries) (ODbL).
- **Fonts:** Barlow and Barlow Condensed by Jeremy Tribby (SIL Open Font License), via [Fontsource](https://fontsource.org/).
