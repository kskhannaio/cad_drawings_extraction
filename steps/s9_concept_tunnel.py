"""Trace the road tunnel and its ramps west of St John's junction from the corridor concept drawing.

"OMR to Silk Board Concept 2-9-2025.pdf" is one large vector sheet of the whole corridor. It is placed on the map
through labels it shares with the tender sheets (the `extract` step's labels, at the positions the drawings write
them): a best-fit scale, rotation and shift, with the misfit of each label printed.

The tunnel parts are cross-hatched bands, picked out by colour and by the length of their hatch strokes:
  red and blue   the two tubes of the North-South road tunnel (rungs about 11 m long)
  cyan           the box the two tubes run into (portal or cut-and-cover section; the drawing does not say)
  orange         the ramps between that box and St John's junction
Writes out/concept_tunnel.geojson (WGS84). Names of the orange ramps are a reading of the drawings, with a
confidence and reason on each.
"""
import collections, json, math, os, re
import numpy as np, pymupdf, pyproj, shapely
from shapely.geometry import LineString, Point, mapping
from shapely.ops import unary_union
from paths import DOCS, OUT

PDF = os.path.join(DOCS, 'OMR to Silk Board Concept 2-9-2025.pdf')
fwd = pyproj.Transformer.from_crs(4326, 32643, always_xy=True).transform
inv = pyproj.Transformer.from_crs(32643, 4326, always_xy=True)
page = pymupdf.open(PDF)[0]

# ---- place the sheet: labels shared with the tender drawings -------------------------------------
SHARED = ['Entry Ramp 08', 'Exit Ramp 01', 'End of Main Tunnel', 'Main Tunnel', 'START  OF APPROACH', 'END  OF APPROACH',
          'Silk Board Metro Staton', 'BOMMANAHALLI METRO STATION']
TENDER = {'Entry Ramp 08': 'Entry Ramp 08 (Sarjapur Road)', 'Exit Ramp 01': 'Exit Ramp 01', 'End of Main Tunnel': 'End of Main Tunnel Tube 1',
          'Main Tunnel': 'Main Tunnel Tube 2 alignment', 'START  OF APPROACH': 'START OF APPROACH', 'END  OF APPROACH': 'END OF APPROACH',
          'Silk Board Metro Staton': 'Silk Board Metro Staton', 'BOMMANAHALLI METRO STATION': 'BOMMANAHALLI METRO STATION'}
lines = {}
for b in page.get_text('dict')['blocks']:
    for l in b.get('lines', []):
        t = ''.join(s['text'] for s in l['spans']).strip()
        if t in SHARED and t not in lines: lines[t] = l['bbox']
# two-line labels: take the middle of the pair as the tender step does
pair = {'End of Main Tunnel': 'Tube 1', 'Main Tunnel': 'Tube 2 alignment', 'Entry Ramp 08': None, 'START  OF APPROACH': None, 'END  OF APPROACH': None}
second = {}
for b in page.get_text('dict')['blocks']:
    for l in b.get('lines', []):
        t = ''.join(s['text'] for s in l['spans']).strip()
        for k_, v in pair.items():
            if v and t == v and k_ in lines and math.dist(l['bbox'][:2], lines[k_][:2]) < 60: second[k_] = l['bbox']
tender = {}
for f in json.load(open(os.path.join(OUT, 'contract_labels.geojson')))['features']:
    p = f['properties']; lon, lat = (p['drawn_lon'], p['drawn_lat']) if 'drawn_lon' in p else f['geometry']['coordinates'][:2]
    tender.setdefault(p['label'], complex(*fwd(lon, lat)))
P, U, N = [], [], []
for name, bb in lines.items():
    if TENDER[name] not in tender: continue
    boxes = [bb] + ([second[name]] if name in second else [])
    x = sum((b[0] + b[2]) / 2 for b in boxes) / len(boxes); y = sum((b[1] + b[3]) / 2 for b in boxes) / len(boxes)
    P.append(complex(x, -y)); U.append(tender[TENDER[name]]); N.append(name)
P, U = np.array(P), np.array(U)
(k, t), *_ = np.linalg.lstsq(np.column_stack([P, np.ones(len(P))]), U, rcond=None)
res = np.abs(k * P + t - U)
assert len(P) >= 6 and res.max() < 12, f'only {len(P)} shared labels, worst misfit {res.max():.1f} m'
to_utm = lambda p: ((k * complex(p.x, -p.y) + t).real, (k * complex(p.x, -p.y) + t).imag)
to_ll = lambda g: shapely.transform(g, lambda a: np.column_stack(inv.transform(a[:, 0], a[:, 1])))

# ---- hatched bands by colour, in the part of the sheet west of St John's junction ---------------------------
SPEC = {'red': ((1.0, 0.0, 0.0), (0, 10380, 620, 10760)), 'blue': ((0.0, 0.0, 1.0), (0, 10380, 620, 10800)),
        'cyan': ((0.0, 1.0, 1.0), (380, 10480, 820, 10900)), 'orange': ((1.0, 0.5, 0.0), (500, 10400, 1750, 11050))}
segs = collections.defaultdict(list)
for g in page.get_drawings():
    c = g.get('color')
    if not c: continue
    c = tuple(round(v, 2) for v in c); r = g['rect']
    for name, (col, B) in SPEC.items():
        if c != col or r.x0 < B[0] or r.x1 > B[2] or r.y0 < B[1] or r.y1 > B[3]: continue
        for it in g['items']:
            if it[0] == 'l':
                l = LineString([to_utm(it[1]), to_utm(it[2])])
                if name != 'orange' or 6 <= l.length <= 20: segs[name].append(l)       # orange: hatch strokes only, not the deck outlines
            elif it[0] == 'c' and name in ('orange', 'cyan'): segs[name].append(LineString([to_utm(q) for q in it[1:5]]))
def band(ls, close):
    u = unary_union([l.buffer(0.4) for l in ls]).buffer(close).buffer(-close).buffer(-1.5).buffer(1.5).simplify(0.4)
    return sorted([shapely.Polygon(p.exterior) for p in getattr(u, 'geoms', [u]) if p.area > 350], key=lambda p: -p.area)
def tube(ls):
    """A tube from its hatch rungs only (9-13.5 m strokes), joined up by closing the gaps between neighbouring rungs.
    Other strokes of the same colour (text, arrows, outlines) would add lumps."""
    rungs = [l for l in ls if 9 <= l.length <= 13.5]
    u = unary_union([l.buffer(0.3) for l in rungs]).buffer(9).buffer(-9).simplify(0.4)
    g = max(getattr(u, 'geoms', [u]), key=lambda p: p.area)
    return shapely.Polygon(g.exterior), float(np.median([l.length for l in rungs])), len(rungs)
feats = []
def add(g, layer, what, conf, basis):
    feats.append({'type': 'Feature', 'geometry': mapping(to_ll(g)), 'properties': {
        'layer': layer, 'what': what, 'area_m2': round(g.area), 'name_confidence': conf, 'name_basis': basis,
        'source': 'corridor concept drawing (OMR to Silk Board Concept, 2 September 2025), vector; placed through labels shared with the tender sheets'}})
for colour in ('red', 'blue'):
    g, w, n = tube(segs[colour])
    add(g, 'tunnel_tube', f'North-South road tunnel, tube drawn in {colour} (about {w:.0f} m wide)', 'medium',
        f'cross-hatched {colour} band, {n} hatch strokes; the sheet labels the pair "TUNNEL NORTH - SOUTH CORRIDOR" with a vehicular cross passage between them. '
        'The drawings do not say which tube this is, or how deep')
box_ = band(segs['cyan'], 8)[0]
add(box_, 'tunnel_portal', 'Box the two tunnel tubes run into, west of St John\'s junction (portal or cut-and-cover section)', 'low',
    'cyan rectangle at the end of both tubes; the drawing does not label it')
C = Point(fwd(77.614971, 12.929885))                    # St John's junction
ramps = band(segs['orange'], 5)
for g in ramps:
    if g.distance(box_) < 15:
        add(g, 'tunnel_ramp', 'Ramp from the tunnel box towards St John\'s junction (joins the Entry Ramp 08 / Tube 2 alignment)', 'medium',
            'orange cross-hatched band leaving the cyan box and curving east to meet the magenta band traced from the tender drawings')
    elif g.distance(C) < 120:
        # two ramps reach the junction: the northern one lands on Sarjapura Road (Exit Ramp 01), the other meets the Hosur Road deck
        north = max((r for r in ramps if r.distance(C) < 120), key=lambda r: r.bounds[3])
        if g is north:
            add(g, 'tunnel_ramp', 'Exit Ramp 01: ramp from the road tunnel up onto Sarjapura Road at St John\'s junction', 'medium',
                'orange cross-hatched band that ends on Sarjapura Road at the junction; the loop plan (KENDRIYA SADANA.pdf) points the label "Exit Ramp 01" at it')
        else:
            add(g, 'tunnel_ramp', 'Ramp between the tunnel side and the Audgodi loop deck at St John\'s junction (not named on the drawings)', 'low',
                'orange cross-hatched band that meets the end of the Hosur Road deck at the junction; it may be part of the tender\'s "tunnel approach connecting to Audgodi loop"')
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, 'concept_tunnel.geojson'), 'w'))
print(f'sheet: {abs(k):.4f} m per point, rotated {math.degrees(np.angle(k)):.1f} deg; {len(P)} shared labels fit to {res.mean():.1f} m on average, {res.max():.1f} m at worst')
for f in feats: print(f"  {f['properties']['name_confidence']:6} {f['properties']['area_m2']:>5} m2  {f['properties']['what'][:100]}")
