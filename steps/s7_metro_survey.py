"""Place the St John's Hospital metro station from the scanned metro survey sheets.

"BMRCL without tunnel-1.pdf" is eight scanned A3 sheets along Sarjapura Road (Metro Phase-3A): no vector
data, so shapes are picked by hand as pixel positions (steps/metro_survey_points.json). Each sheet prints a
survey benchmark with its easting and northing. Sheet 4 has two, which give the scale and rotation of the
scans (all sheets are one plot series); each other sheet is then placed by its own benchmark.

Writes out/metro_station.geojson (WGS84): the station box, the land marked for it, the parking area and the
structure across the road. Accuracy: the benchmarks are exact, the hand-picked outlines are good to a few
metres. Checked by eye: the study's road centrelines and the mapped foot over bridge land on the sheet's.
"""
import cmath, json, math, os
import pyproj
from paths import ROOT, OUT

P = json.load(open(os.path.join(ROOT, 'steps', 'metro_survey_points.json')))
z = lambda b: (complex(b['px'][0], -b['px'][1]), complex(b['easting'], b['northing']))       # image y runs down
(pa, ua), (pb, ub) = [z(b) for b in P['scale_from']['benchmarks']]
k = (ub - ua) / (pb - pa)                     # metres per pixel, with the scans' small rotation
assert 0.10 < abs(k) < 0.20 and abs(math.degrees(cmath.phase(k))) < 3, 'benchmarks misread: scale or rotation is off'
to_ll = pyproj.Transformer.from_crs(32643, 4326, always_xy=True).transform
feats = []
for page, sheet in P['sheets'].items():
    p0, u0 = z(sheet['benchmark'])
    for s in sheet['shapes']:
        utm = [u0 + (complex(x, -y) - p0) * k for x, y in s['px']]
        area = abs(sum(a.real * b.imag - b.real * a.imag for a, b in zip(utm, utm[1:] + utm[:1]))) / 2
        ring = [[round(v, 7) for v in to_ll(u.real, u.imag)] for u in utm]
        feats.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [ring + ring[:1]]},
                      'properties': {'layer': s['layer'], 'what': s['what'], 'area_m2': round(area),
                                     'source': f'BMRCL metro survey sheets (scanned), sheet {page}; placed from survey benchmark '
                                               f"{sheet['benchmark']['name']}, outline picked by hand, good to a few metres"}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, 'metro_station.geojson'), 'w'))
print(f'scans: {abs(k):.4f} m per pixel, rotated {math.degrees(cmath.phase(k)):.2f} deg')
for f in feats: print(f"  {f['properties']['area_m2']:>6} m2  {f['properties']['what']}")
