"""Place Metro Phase-3A along Sarjapura Road from the scanned metro survey sheets: three stations and the line.

"BMRCL without tunnel-1.pdf" is eight scanned A3 sheets from St John's Hospital east to Jakkasandra: no vector
data, so shapes are picked by hand as pixel positions (steps/metro_survey_points.json). Each sheet prints one or
two survey benchmarks with eastings and northings. The sheets are not all at one scale:
  - two benchmarks on a sheet give its scale and rotation directly (sheets 4 and 8);
  - a sheet with one benchmark is taken as north-up, with a scale worked out from the track chainages printed on
    the sheets (the distance along the track between two marks), as recorded per sheet in the points file.
Checks printed: the distance between chainage marks as placed, against the chainage difference.

Writes out/metro_station.geojson (WGS84): station boxes, the land and structures marked for them, and the line from
junction A to Jakkasandra as a 10 m band through the picked pillar positions. Accuracy: a few metres near a
benchmark, up to 10-15 m on sheets 6 and 7 where the scale is assumed.
"""
import cmath, json, math, os
import pyproj
from shapely.geometry import LineString, Polygon, mapping
import shapely, numpy as np
from paths import ROOT, OUT

P = json.load(open(os.path.join(ROOT, 'steps', 'metro_survey_points.json')))
inv = pyproj.Transformer.from_crs(32643, 4326, always_xy=True)
to_ll = lambda g: shapely.transform(g, lambda a: np.column_stack(inv.transform(a[:, 0], a[:, 1])))
zp = lambda px: complex(px[0], -px[1])                       # image y runs down
fits, marks, feats, track = {}, {}, [], []
for page, sh in P['sheets'].items():
    b = sh['benchmarks']; p0, u0 = zp(b[0]['px']), complex(b[0]['easting'], b[0]['northing'])
    if len(b) == 2:
        k = (complex(b[1]['easting'], b[1]['northing']) - u0) / (zp(b[1]['px']) - p0); how = 'two benchmarks'
    else:
        k = complex(sh['scale_m_per_px'], 0); how = 'one benchmark, scale from chainages'
    assert 0.09 < abs(k) < 0.18, f'sheet {page}: scale {abs(k):.3f} m/px is out of range'
    fits[page] = (abs(k), math.degrees(cmath.phase(k)), how)
    place = lambda px, k=k, p0=p0, u0=u0: u0 + (zp(px) - p0) * k
    for name, px in sh.get('marks', {}).items(): marks.setdefault(name, []).append((page, place(px)))
    for s in sh.get('shapes', []):
        g = Polygon([(z.real, z.imag) for z in map(place, s['px'])])
        feats.append({'type': 'Feature', 'geometry': mapping(to_ll(g)), 'properties': {
            'layer': s['layer'], 'what': s['what'], 'area_m2': round(g.area),
            'source': f"BMRCL metro survey sheets (scanned), sheet {page}; placed from survey benchmark {b[0]['name']} ({how}), outline picked by hand"}})
    track += [(int(page), i, place(px)) for i, px in enumerate(sh.get('track', []))]
# the line: bridge intersection -> null point -> pillars on sheets 4 to 8, through the two elevated stations
first = lambda n: marks[n][0][1]
pts = [first('Bridge intersection'), first('Null point')] + [z for _, _, z in sorted(track, key=lambda t: (t[0], t[1]))]
pts.insert(next(i for i, z in enumerate(pts) if z.real > first('Koramangala station centre').real), first('Koramangala station centre'))
line = LineString([(z.real, z.imag) for z in pts])
feats.append({'type': 'Feature', 'geometry': mapping(to_ll(line.buffer(5, cap_style='flat'))), 'properties': {
    'layer': 'metro_line', 'what': 'Metro Phase-3A viaduct along Sarjapura Road, junction A to Jakkasandra (approximate line through the pillars)',
    'area_m2': round(line.length * 10), 'length_m': round(line.length),
    'source': 'BMRCL metro survey sheets (scanned), sheets 3 to 8; pillar positions picked by hand. Good to a few metres on sheets 3, 4, 5 and 8, 10 to 15 m on sheets 6 and 7'}})
st = first("St John's Hospital station centre"); bi = first('Bridge intersection')
lead = LineString([(st.real, st.imag), (bi.real, bi.imag)])
feats.append({'type': 'Feature', 'geometry': mapping(to_ll(lead.buffer(5, cap_style='flat'))), 'properties': {
    'layer': 'metro_line', 'what': "Metro Phase-3A track between St John's Hospital station and junction A (straight line between the two marks; the sheets draw it dashed, with gentle curves)",
    'area_m2': round(lead.length * 10), 'length_m': round(lead.length),
    'source': 'BMRCL metro survey sheets (scanned), sheets 1 to 3; the two end marks are placed, the line between them is not traced'}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, 'metro_station.geojson'), 'w'))

for page, (s, rot, how) in fits.items(): print(f'  sheet {page}: {s:.4f} m per pixel, rotated {rot:+.2f} deg ({how})')
ch = P['chainage_marks_m']; order = sorted(ch, key=lambda n: -ch[n])
print('checks: distance between marks as placed, against the chainage difference')
for a, b in zip(order, order[1:]):
    print(f'  {a} -> {b}: {abs(first(a) - first(b)):.1f} m placed, {ch[a] - ch[b]:.1f} m by chainage')
for n, v in marks.items():
    if len(v) > 1: print(f'  {n} placed from sheets {v[0][0]} and {v[1][0]}: {abs(v[0][1] - v[1][1]):.1f} m apart')
for f in feats: print(f"  {f['properties']['area_m2']:>6} m2  {f['properties']['what'][:105]}")
