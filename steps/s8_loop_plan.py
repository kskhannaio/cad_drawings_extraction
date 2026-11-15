"""Trace what only the corridor's plan of the loop shows: Exit Ramp 01, the tunnel-end strip and the subway.

"KENDRIYA SADANA.pdf" is one large sheet covering the loop, stored as an image (no vector data or text). It is
placed on the map by a best-fit scale, rotation and shift through five known points (steps/loop_plan_points.json):
the two foot over bridges from OpenStreetMap and the centre of the Level-1 rotary. Shapes are then picked by hand.

Writes out/loop_plan.geojson (WGS84). Accuracy: the fit's residuals are printed (a few metres); hand-picked
outlines add a few more. Checked by eye: the tender-traced deck, the study's road centrelines and the metro
station from the survey scans all land on the plan's own drawing of them.
"""
import cmath, json, math, os
import numpy as np, pyproj
from shapely.geometry import LineString, Polygon, mapping
import shapely
from paths import ROOT, OUT

P = json.load(open(os.path.join(ROOT, 'steps', 'loop_plan_points.json')))
fwd = pyproj.Transformer.from_crs(4326, 32643, always_xy=True).transform
inv = pyproj.Transformer.from_crs(32643, 4326, always_xy=True)
px = np.array([complex(c['px'][0], -c['px'][1]) for c in P['control']])
utm = np.array([complex(*(c['utm'] if 'utm' in c else fwd(*c['lonlat']))) for c in P['control']])
(k, t), *_ = np.linalg.lstsq(np.column_stack([px, np.ones(len(px))]), utm, rcond=None)      # utm = k * pixel + t
res = np.abs(k * px + t - utm)
assert res.max() < 8, f'control points disagree by up to {res.max():.1f} m - check them'
to_utm = lambda pts: [((k * complex(x, -y) + t).real, (k * complex(x, -y) + t).imag) for x, y in pts]
to_ll = lambda g: shapely.transform(g, lambda a: np.column_stack(inv.transform(a[:, 0], a[:, 1])))
feats = []
for s in P['shapes']:
    g = Polygon(to_utm(s['polygon_px'])) if 'polygon_px' in s else LineString(to_utm(s['line_px'])).buffer(s['width_m'] / 2, cap_style='flat')
    feats.append({'type': 'Feature', 'geometry': mapping(to_ll(g)), 'properties': {
        'layer': s['layer'], 'what': s['what'], 'area_m2': round(g.area), 'name_confidence': s['confidence'], 'name_basis': s['basis'],
        'source': "corridor's plan of the loop (KENDRIYA SADANA.pdf, an image); placed by fitting five known points, outline picked by hand, good to several metres"}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, 'loop_plan.geojson'), 'w'))
print(f'plan: {abs(k):.4f} m per pixel at {P["render_dpi"]} dpi, rotated {math.degrees(cmath.phase(k)):.1f} deg; control points fit to {res.mean():.1f} m on average, {res.max():.1f} m at worst')
for f in feats: print(f"  {f['properties']['name_confidence']:6} {f['properties']['area_m2']:>5} m2  {f['properties']['what']}")
