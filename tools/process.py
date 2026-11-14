"""Per-country elevation profiles (N->S, W->E) from ETOPO2v2 + Natural Earth 1:10m.

Inputs: tools/data (see fetch_data.sh). Output: tools/build/countries_data.json
"""
import json, math, sys, time, unicodedata
from pathlib import Path
import numpy as np
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.affinity import translate
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree
from shapely import contains_xy, prepare
from scipy.ndimage import binary_erosion, map_coordinates

HERE = Path(__file__).resolve().parent
DATA, BUILD = HERE / 'data', HERE / 'build'
G = np.memmap(DATA / 'etopo' / 'ETOPO2v2g_f4_LSB.flt', dtype='<f4', mode='r', shape=(5401, 10801))
NATIVE = 1 / 30  # 2 arc-minutes in degrees
NBINS = 96
R_EARTH = 6371.0

mc = json.load(open(DATA / 'ne' / 'countries.json'))
ne = json.load(open(DATA / 'ne' / 'ne_10m_admin_0_countries.geojson'))
NE = {f['properties']['ADM0_A3']: f for f in ne['features']}

NE_CODES = {'PSE': ['PSX'], 'SSD': ['SDS'], 'UNK': ['KOS'], 'SOM': ['SOM', 'SOL'],
            'CYP': ['CYP', 'CYN', 'CNM'], 'KAZ': ['KAZ', 'KAB']}
# Main-territory linkage distance (km). Islands/exclaves further than this from the
# main landmass cluster are dropped (overseas territories, remote archipelagos).
LINK_KM = {'MYS': 900}
DEFAULT_LINK = 350

DISPLAY = {'COG': 'Republic of the Congo', 'COD': 'DR Congo', 'USA': 'United States'}
EXTRA_ALIASES = {
    'GBR': ['UK', 'Britain', 'Great Britain'], 'USA': ['US', 'USA', 'America', 'United States of America'], 'ZAF': ['RSA'],
    'COD': ['DRC', 'Zaire', 'Congo-Kinshasa', 'Democratic Republic of the Congo'],
    'COG': ['Congo', 'Congo-Brazzaville'], 'CZE': ['Czech Republic'], 'MKD': ['Macedonia'],
    'TUR': ['Turkey'], 'CPV': ['Cabo Verde'], 'VAT': ['Holy See'], 'TLS': ['East Timor'],
    'MMR': ['Burma'], 'SWZ': ['Swaziland'], 'CIV': ["Cote d'Ivoire"], 'BIH': ['Bosnia'],
    'KNA': ['St Kitts and Nevis'], 'LCA': ['St Lucia'], 'VCT': ['St Vincent and the Grenadines'],
    'STP': ['Sao Tome and Principe'], 'KOR': ['Korea, South', 'Republic of Korea'],
    'PRK': ['Korea, North', 'DPRK'], 'ARE': ['UAE'], 'NLD': ['Holland'], 'FSM': ['Federated States of Micronesia'],
}


def latin(s):
    try:
        s.encode('latin-1')
        return True
    except UnicodeEncodeError:
        # allow common latin extended letters, reject other scripts
        return all(unicodedata.name(ch, '').startswith(('LATIN', 'SPACE', 'APOSTROPHE', 'HYPHEN', 'COMMA', 'FULL STOP', 'LEFT', 'RIGHT', 'MODIFIER', 'COMBINING', 'DIGIT'))
                   or ch in " -'’.,()" for ch in s)


def polys_of(geom):
    if geom.geom_type == 'Polygon':
        return [geom]
    return list(geom.geoms)


def geo_area(p):
    c = p.centroid
    return p.area * math.cos(math.radians(c.y))


def hav(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1, math.sqrt(a)))


def main_territory(cca3, polys):
    main = max(polys, key=geo_area)
    xs = [p.bounds for p in polys]
    straddles = min(b[0] for b in xs) < -170 and max(b[2] for b in xs) > 170
    if straddles:
        if main.centroid.x > 0:
            polys = [translate(p, 360) if p.centroid.x < 0 else p for p in polys]
        else:
            polys = [translate(p, -360) if p.centroid.x > 0 else p for p in polys]
        main = max(polys, key=geo_area)
    link = LINK_KM.get(cca3, DEFAULT_LINK)
    tree = STRtree(polys)
    idx_main = next(i for i, p in enumerate(polys) if p.equals(main))
    included = {idx_main}
    frontier = [idx_main]
    while frontier:
        nxt = []
        for i in frontier:
            p = polys[i]
            maxlat = max(abs(p.bounds[1]), abs(p.bounds[3]), 1)
            deg = link / (111.0 * max(math.cos(math.radians(min(maxlat, 85))), 0.05))
            for j in tree.query(p, predicate='dwithin', distance=deg):
                j = int(j)
                if j in included:
                    continue
                a, b = nearest_points(p, polys[j])
                if hav(a.y, a.x, b.y, b.x) <= link:
                    included.add(j)
                    nxt.append(j)
        frontier = nxt
    kept = [polys[i] for i in sorted(included)]
    dropped_area = sum(geo_area(polys[i]) for i in range(len(polys)) if i not in included)
    total_area = sum(geo_area(p) for p in polys)
    return kept, dropped_area / total_area


def window(miny, maxy, minx, maxx):
    i0 = max(int(math.floor((90 - maxy) * 30)) - 2, 0)
    i1 = min(int(math.ceil((90 - miny) * 30)) + 2, 5400)
    j0 = int(math.floor((minx + 180) * 30)) - 2
    j1 = int(math.ceil((maxx + 180) * 30)) + 2
    cols = np.arange(j0, j1 + 1) % 10800
    win = np.asarray(G[i0:i1 + 1][:, cols], dtype=np.float32)
    return win, i0, j0


def bin_profile(coord, vals, w, lo, hi, nb):
    span = hi - lo
    idx = np.clip(((coord - lo) / span * nb).astype(int), 0, nb - 1)
    sw = np.bincount(idx, weights=w, minlength=nb)
    swz = np.bincount(idx, weights=w * vals, minlength=nb)
    mx = np.full(nb, -np.inf)
    np.maximum.at(mx, idx, vals)
    mean = [None if sw[k] == 0 else int(round(swz[k] / sw[k])) for k in range(nb)]
    peak = [None if sw[k] == 0 else int(round(mx[k])) for k in range(nb)]
    return mean, peak


def process(cca3):
    feats = [NE[c] for c in NE_CODES.get(cca3, [cca3]) if c in NE]
    geom = unary_union([shape(f['geometry']).buffer(0) for f in feats])
    polys = polys_of(geom)
    kept, dropped = main_territory(cca3, polys)
    mp = MultiPolygon(kept) if len(kept) > 1 else kept[0]
    minx, miny, maxx, maxy = mp.bounds
    latc = (miny + maxy) / 2
    coslat = math.cos(math.radians(latc))
    min_ext = min(maxy - miny, (maxx - minx) * coslat)
    step = min(NATIVE, max(min_ext / 180, NATIVE / 40))

    # sample grid aligned to multiples of step
    lats = np.arange(math.floor(maxy / step) * step, miny - step, -step)
    lons = np.arange(math.ceil(minx / step) * step, maxx + step, step)
    LON, LAT = np.meshgrid(lons, lats)
    prepare(mp)
    mask = contains_xy(mp, LON, LAT)
    if mask.sum() < 12:  # very small: densify
        step = step / 4
        lats = np.arange(math.floor(maxy / step) * step, miny - step, -step)
        lons = np.arange(math.ceil(minx / step) * step, maxx + step, step)
        LON, LAT = np.meshgrid(lons, lats)
        mask = contains_xy(mp, LON, LAT)
    if mask.sum() == 0:
        rp = mp.representative_point()
        LON, LAT = np.array([[rp.x]]), np.array([[rp.y]])
        mask = np.array([[True]])

    k = max(1, int(round(NATIVE / step)))
    interior = binary_erosion(mask, iterations=k) if mask.shape[0] > 2 and mask.shape[1] > 2 else np.zeros_like(mask)

    win, i0, j0 = window(miny, maxy, minx, maxx)
    la, lo = LAT[mask], LON[mask]
    r = (90 - la) * 30 - i0
    c = (lo + 180) * 30 - j0
    z = map_coordinates(win, [r, c], order=1, mode='nearest')
    inner = interior[mask]
    keep = z >= -440
    nbad = int(np.sum(~keep) + np.sum((z < 0) & ~inner & keep))
    frac_bad = nbad / max(len(z), 1)
    z = np.where((z < 0) & ~inner, 0.0, z)
    la, lo, z = la[keep], lo[keep], z[keep]
    w = np.cos(np.radians(la))

    # centroid (spherical mean of sample points)
    phi, lam = np.radians(LAT[mask]), np.radians(LON[mask])
    ww = np.cos(phi)
    X = np.sum(ww * np.cos(phi) * np.cos(lam)); Y = np.sum(ww * np.cos(phi) * np.sin(lam)); Z = np.sum(ww * np.sin(phi))
    clat = math.degrees(math.atan2(Z, math.hypot(X, Y)))
    clon = math.degrees(math.atan2(Y, X))

    ns_mean, ns_peak = bin_profile(maxy - la, z, w, 0, maxy - miny, NBINS)
    we_mean, we_peak = bin_profile(lo - minx, z, w, 0, maxx - minx, NBINS)

    native_cells = int(mask.sum() * (step / NATIVE) ** 2)
    area_km2 = float(np.sum(np.cos(np.radians(LAT[mask]))) * (step * 111.195) ** 2)
    return {
        'ns': [ns_mean, ns_peak], 'we': [we_mean, we_peak],
        'span': [round((maxy - miny) * 111.195), round((maxx - minx) * 111.32 * math.cos(math.radians(clat)))],
        'bbox': [round(minx, 3), round(miny, 3), round(maxx, 3), round(maxy, 3)],
        'c': [round(clat, 3), round(((clon + 180) % 360) - 180, 3)],
        'zmax': int(round(float(z.max()))) if len(z) else 0,
        'zmean': int(round(float(np.sum(w * z) / np.sum(w)))) if len(z) else 0,
        'cells': native_cells, 'area': round(area_km2), 'dropped': round(dropped, 3),
        'step': round(step * 60, 3), 'bad': round(frac_bad, 3),
    }


def main():
    keep = [c for c in mc if c.get('unMember') or c['cca3'] in ('PSE', 'UNK', 'TWN')]
    out = []
    t0 = time.time()
    only = set(sys.argv[1:])
    for c in sorted(keep, key=lambda c: c['name']['common']):
        cca3 = c['cca3']
        if only and cca3 not in only:
            continue
        t = time.time()
        d = process(cca3)
        name = DISPLAY.get(cca3, c['name']['common'])
        aliases = [c['name']['common'], c['name']['official']] + c.get('altSpellings', []) + EXTRA_ALIASES.get(cca3, [])
        fr = c.get('translations', {}).get('fra', {}).get('common')
        if fr:
            aliases.append(fr)
        extra = EXTRA_ALIASES.get(cca3, [])
        aliases = sorted({a for a in aliases if (len(a) > 3 or a in extra) and latin(a) and a != name})
        d.update({'id': cca3, 'name': name, 'alias': aliases})
        out.append(d)
        print(f"{cca3} {name:28s} cells={d['cells']:>8} area={d['area']:>9} drop={d['dropped']:.2f} zmax={d['zmax']:>5} zmean={d['zmean']:>5} bad={d['bad']:.2f} span={d['span']} step={d['step']}' {time.time()-t:.1f}s", flush=True)
    json.dump(out, open(BUILD / 'countries_data.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('done', len(out), f'{time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()
