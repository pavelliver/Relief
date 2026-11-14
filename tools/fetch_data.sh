#!/usr/bin/env bash
# Downloads the raw inputs for process.py / geo.py into tools/data (~330 MB unpacked, git-ignored).
# Only needed to recompute profiles; UI changes need just `python3 tools/build.py`.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)/data"
mkdir -p "$D/etopo" "$D/ne"

# NOAA ETOPO2v2 (2006), 2-arc-minute grid-registered, float32 little-endian, mirrored on GitHub
if [ ! -f "$D/etopo/ETOPO2v2g_f4_LSB.flt" ]; then
  tmp="$(mktemp -d)"
  git -C "$tmp" init -q
  git -C "$tmp" remote add origin https://github.com/hperantunes/ETOPO2v2gParser
  git -C "$tmp" fetch -q --depth 1 --filter=blob:none origin HEAD
  git -C "$tmp" checkout -q FETCH_HEAD -- Data/ETOPO2v2g_f4_LSB.zip
  unzip -o -q "$tmp/Data/ETOPO2v2g_f4_LSB.zip" -d "$D/etopo"
  rm -rf "$tmp"
fi

# Natural Earth admin-0 countries (1:10m for profiles, 1:50m for the world map)
NE=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson
for f in ne_10m_admin_0_countries.geojson ne_50m_admin_0_countries.geojson; do
  [ -f "$D/ne/$f" ] || curl -sSfL -o "$D/ne/$f" "$NE/$f"
done

# Country names, alternative spellings and French names
[ -f "$D/ne/countries.json" ] || curl -sSfL -o "$D/ne/countries.json" https://raw.githubusercontent.com/mledoze/countries/master/countries.json
echo "Data ready in $D"
