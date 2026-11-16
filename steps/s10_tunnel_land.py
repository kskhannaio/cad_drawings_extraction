"""Land required for the road tunnel at St John's, from the tunnel's land acquisition plan.

"Land Acquisition Map - Sept 2025.pdf", page 8 ("Land Acquisition Plan (St. Johns Junction)", 30 Aug 2025, 1:2000,
vector). It is drawn on the same CAD base as the corridor concept drawing, so it is placed through the labels the
two sheets share (ramp names, tunnel labels, chainage marks), using the concept step's fit to the map.

Writes out/tunnel_land.geojson (WGS84): the yellow "Required Area for Tunnel Project" as merged shapes, with the
sheet's own area statement in the properties. Owners named on the sheet are institutions; only the totals are kept.
"""
import json, math, os, re
import numpy as np, pymupdf, pyproj, shapely
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union
from paths import DOCS, OUT

LA = os.path.join(DOCS, 'Detailed Project Report for Vehicular Tunnel System from Hebbal to Silk Board', 'Land Acquisition Map - Sept 2025.pdf')
CONCEPT = os.path.join(DOCS, 'OMR to Silk Board Concept 2-9-2025.pdf')
inv = pyproj.Transformer.from_crs(32643, 4326, always_xy=True)
fit = json.load(open(os.path.join(OUT, 'concept_fit.json'))); kc, tc = complex(*fit['k']), complex(*fit['t'])

def labels(page):
    out = {}
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = re.sub(r'\s+', ' ', ''.join(s['text'] for s in l['spans']).strip())
            if re.fullmatch(r'\d\d?\+\d\d\d|Entry Ramp 08|Exit Ramp 01|End of Main Tunnel|Tube 1|Main Tunnel|Tube 2 alignment|VEHICULAR CROSS PASSAGE', t):
                out.setdefault(t, []).append(complex((l['bbox'][0] + l['bbox'][2]) / 2, -(l['bbox'][1] + l['bbox'][3]) / 2))
    return out
page = pymupdf.open(LA)[7]
a, b = labels(page), labels(pymupdf.open(CONCEPT)[0])
# pair labels by text; a text that appears several times is paired by trying every combination later (RANSAC-style)
pairs = [(t, pa, kc * pb + tc) for t in a if t in b for pa in a[t] for pb in b[t]]
best = None
for i in range(len(pairs)):
    for j in range(i + 1, len(pairs)):
        (_, p1, u1), (_, p2, u2) = pairs[i], pairs[j]
        if abs(p2 - p1) < 150: continue
        k = (u2 - u1) / (p2 - p1); t0 = u1 - k * p1
        if not 0.6 < abs(k) < 0.8: continue                       # 1:2000 on paper is about 0.706 m per point
        inl = {}
        for t, p, u in pairs:
            d = abs(k * p + t0 - u)
            if d < 4 and (t, p) not in inl: inl[(t, p)] = u
        if best is None or len(inl) > len(best): best = inl
P = np.array([p for (_, p) in best]); U = np.array(list(best.values()))
(k, t0), *_ = np.linalg.lstsq(np.column_stack([P, np.ones(len(P))]), U, rcond=None)
res = np.abs(k * P + t0 - U)
assert len(P) >= 8 and res.max() < 6, f'{len(P)} shared labels, worst misfit {res.max():.1f} m'
utm = lambda pt: ((k * complex(pt.x, -pt.y) + t0).real, (k * complex(pt.x, -pt.y) + t0).imag)
to_ll = lambda g: shapely.transform(g, lambda c: np.column_stack(inv.transform(c[:, 0], c[:, 1])))

def rings(drawing):
    """Each closed sub-path of a filled drawing, as a list of points. The fill is drawn as hundreds of slivers."""
    out, cur = [], []
    for it in drawing['items']:
        if it[0] == 're': r = it[1]; out.append([r.tl, r.tr, r.br, r.bl]); continue
        if it[0] == 'qu': q = it[1]; out.append([q.ul, q.ur, q.lr, q.ll]); continue
        pts = list(it[1:3]) if it[0] == 'l' else list(it[1:5]) if it[0] == 'c' else []
        if not pts: continue
        if cur and abs(cur[-1].x - pts[0].x) + abs(cur[-1].y - pts[0].y) > 0.01: out.append(cur); cur = []
        cur += pts if not cur else pts[1:]
    if cur: out.append(cur)
    return [r for r in out if len(r) >= 3]
polys = []
for g in page.get_drawings():
    f = g.get('fill')
    if not f or tuple(round(v, 2) for v in f) != (1.0, 1.0, 0.0): continue
    for r in rings(g):
        pg = Polygon([utm(q) for q in r])
        if not pg.is_valid: pg = pg.buffer(0)
        if not pg.is_empty: polys.append(pg)
# keep the map part of the sheet: the legend swatch and the inset "local area map" sit apart from the main drawing
u = unary_union(polys).buffer(1.5).buffer(-1.5)                 # fuse the slivers
parts = sorted([p for p in getattr(u, 'geoms', [u]) if p.area > 150], key=lambda p: -p.area)
main = parts[0]; parts = [p for p in parts if p.distance(main) < 120]      # the inset "local area map" repeats the shapes about 250 m away
feats = []
STATEMENT = {'total_m2': 41949.21, 'total_acres': 10.36, 'parcels': 3,
             'note': 'area statement printed on the sheet: two parcels of St John\'s Medical College and Hospital (27,992 and 13,823 m2) and 134 m2 of St Anthony\'s Friary Church'}
for p in parts:
    feats.append({'type': 'Feature', 'geometry': mapping(to_ll(shapely.Polygon(p.exterior).simplify(0.4))), 'properties': {
        'layer': 'tunnel_land', 'what': 'Land required for the road tunnel at St John\'s (ramps, TBM shaft and tunnel end)', 'area_m2': round(p.area),
        'statement': STATEMENT['note'], 'statement_total_m2': STATEMENT['total_m2'],
        'source': 'tunnel land acquisition plan, St Johns Junction sheet (30 Aug 2025), vector; placed through labels shared with the corridor concept drawing'}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, 'tunnel_land.geojson'), 'w'))
print(f'sheet: {abs(k):.4f} m per point, rotated {math.degrees(np.angle(k)):.1f} deg; {len(P)} shared labels fit to {res.mean():.1f} m on average, {res.max():.1f} m at worst')
print(f'required area traced: {sum(p.area for p in parts):,.0f} m2 in {len(parts)} shape(s); the sheet\'s area statement says {STATEMENT["total_m2"]:,.0f} m2')
