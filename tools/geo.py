"""Silhouettes (main territory, local projection) + Equal Earth world map paths."""
import json, math
from shapely.geometry import shape, Polygon, MultiPolygon, box
from shapely.ops import unary_union
from shapely.affinity import translate
import process as P

DATA, BUILD = P.DATA, P.BUILD
data = json.load(open(BUILD / 'countries_data.json'))
ne50 = json.load(open(DATA / 'ne' / 'ne_50m_admin_0_countries.geojson'))
N50 = {f['properties']['ADM0_A3']: f for f in ne50['features']}

A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2
SCALE = 1000 / (2 * 2.7066297319215575)  # x range of Equal Earth at lon ±180 -> 1000 units wide


def ee(lon, lat):
    l, p = math.radians(lon), math.radians(lat)
    t = math.asin(M * math.sin(p))
    t2 = t * t; t6 = t2 * t2 * t2
    x = l * math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x * SCALE + 500, -y * SCALE


def ring_path(coords, proj, nd=1):
    pts = []
    last = None
    for lon, lat in coords:
        x, y = proj(lon, lat)
        q = (round(x, nd), round(y, nd))
        if q != last:
            pts.append(q)
            last = q
    if len(pts) < 3:
        return ''
    fmt = (lambda v: f'{v:.{nd}f}'.rstrip('0').rstrip('.')) if nd else (lambda v: str(int(v)))
    return 'M' + 'L'.join(f'{fmt(x)},{fmt(y)}' for x, y in pts) + 'Z'


def geom_path(g, proj, nd=1):
    out = []
    for p in P.polys_of(g):
        out.append(ring_path(p.exterior.coords, proj, nd))
        for h in p.interiors:
            out.append(ring_path(h.coords, proj, nd))
    return ''.join(out)


world = {}
codes_in_game = {c['id'] for c in data}
ne_to_game = {}
for cid in codes_in_game:
    for code in P.NE_CODES.get(cid, [cid]):
        ne_to_game[code] = cid

clip = box(-180, -58, 180, 84)
groups = {}
for f in ne50['features']:
    a3 = f['properties']['ADM0_A3']
    if a3 == 'ATA':
        continue
    g = shape(f['geometry']).buffer(0).intersection(clip)
    if g.is_empty:
        continue
    groups.setdefault(ne_to_game.get(a3, '_bg'), []).append(g)
for cid in codes_in_game:  # microstates missing at 50m -> 10m
    if cid not in groups:
        feats = [P.NE[c] for c in P.NE_CODES.get(cid, [cid]) if c in P.NE]
        groups[cid] = [unary_union([shape(f['geometry']).buffer(0) for f in feats])]

for k, gs in groups.items():
    g = unary_union(gs).simplify(0.11, preserve_topology=True)
    world[k] = geom_path(g, ee, 1)

sil = {}
for c in data:
    cid = c['id']
    feats = [P.NE[x] for x in P.NE_CODES.get(cid, [cid]) if x in P.NE]
    geom = unary_union([shape(f['geometry']).buffer(0) for f in feats])
    kept, _ = P.main_territory(cid, P.polys_of(geom))
    g = MultiPolygon(kept) if len(kept) > 1 else kept[0]
    minx, miny, maxx, maxy = g.bounds
    lat0 = (miny + maxy) / 2
    k = math.cos(math.radians(lat0))
    w, h = (maxx - minx) * k, (maxy - miny)
    s = 100 / max(w, h, 1e-6)
    g = g.simplify(max(w, h) / 170, preserve_topology=True)
    # drop slivers invisible at this size
    g = unary_union([p for p in P.polys_of(g) if p.area * k * s * s > 1.2] or [max(P.polys_of(g), key=lambda p: p.area)])
    proj = lambda lon, lat: ((lon - minx) * k * s + (100 - w * s) / 2, (maxy - lat) * s + (100 - h * s) / 2)
    sil[cid] = geom_path(g, proj, 1)

json.dump({'world': world, 'sil': sil}, open(BUILD / 'geo.json', 'w'), separators=(',', ':'))
print('world bytes', sum(len(v) for v in world.values()), 'sil bytes', sum(len(v) for v in sil.values()))
print('missing world', [c for c in codes_in_game if not world.get(c)])
