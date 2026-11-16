"""Name the parts of the traced flyover deck (best guess) and move each label onto the part it names.

The drawings write most labels in clear space and point to the structure with a leader line, so a label's
position is not the structure's position; and the extract step traces the proposed deck as merged shapes. This step
  1. cuts the loop's deck into its parts: the rotary above Madiwala junction, the three arms that leave it,
     and the ramp that curves onto Sarjapura Road near junction A;
  2. gives every deck, Level-2 and tunnel shape a `name`, with `name_confidence` (high / medium / low) and
     `name_basis` saying why;
  3. moves each matching label to a point on its part (original position kept in `drawn_lon`/`drawn_lat`).
The names are a reading of the drawings, not something they state shape by shape. Run through main.py (step `names`).
"""
import json, math, os
import numpy as np
import shapely
from shapely.geometry import shape, mapping, Point, LineString
from shapely.ops import split
from pyproj import Transformer

from paths import OUT
FWD = Transformer.from_crs(4326, 32643, always_xy=True); INV = Transformer.from_crs(32643, 4326, always_xy=True)
utm = lambda g: shapely.transform(g, lambda a: np.column_stack(FWD.transform(a[:, 0], a[:, 1])))
ll = lambda g: shapely.transform(g, lambda a: np.column_stack(INV.transform(a[:, 0], a[:, 1])))
J = {k: Point(FWD.transform(*v)) for k, v in {'A': (77.620965, 12.927461), 'B': (77.618093, 12.924584), 'C': (77.614971, 12.929885)}.items()}

# the extract step's shapes are kept as contract_structures_raw.geojson so this step can be re-run
SRC, RAW = os.path.join(OUT, 'contract_structures.geojson'), os.path.join(OUT, 'contract_structures_raw.geojson')
S = json.load(open(SRC))
if any('name' in f['properties'] for f in S['features']): S = json.load(open(RAW))      # already named: start again from raw
else: json.dump(S, open(RAW, 'w'))                                                    # fresh from the extract step
L = json.load(open(os.path.join(OUT, 'contract_labels.geojson')))
feats = S['features']
geoms = [utm(shape(f['geometry'])) for f in feats]

def named(f, g, name, conf, basis, part_of=None):
    p = dict(f['properties']); p.update(name=name, what=name, name_confidence=conf, name_basis=basis, area_m2=round(g.area))
    if part_of: p['part_of'] = part_of
    return {'type': 'Feature', 'properties': p, 'geometry': mapping(ll(g))}

out, parts = [], {}                                # parts: name -> utm geometry (for the labels)
decks = [(f, g) for f, g in zip(feats, geoms) if f['properties']['layer'] == 'proposed_deck']
loop_f, loop_g = min(decks, key=lambda fg: fg[1].distance(J['B']))                  # the deck that covers the loop

# ---- 1. the loop's deck -> rotary + arms -----------------------------------------------------
shell = shapely.Polygon(loop_g.exterior)
mic = shapely.maximum_inscribed_circle(shell)                                       # widest spot of the deck = the rotary
centre, radius = Point(mic.coords[0]), mic.length
assert centre.distance(J['B']) < 80, 'widest part of the deck is not at Madiwala junction - check the extraction'
disc = centre.buffer(radius + 4)
rotary = loop_g.intersection(disc)
arms = [g for g in getattr(loop_g.difference(disc), 'geoms', [loop_g.difference(disc)]) if g.area > 30]
bearing = lambda a, b: math.degrees(math.atan2(b.x - a.x, b.y - a.y)) % 360
def toward(g):                                     # which way an arm leaves the rotary
    far = max(g.exterior.coords, key=lambda c: centre.distance(Point(c)))
    b = bearing(centre, Point(far)); diff = lambda t: abs((b - t + 180) % 360 - 180)
    return min((diff(bearing(centre, J['C'])), 'C'), (diff(bearing(centre, J['A'])), 'A'), (diff(bearing(J['C'], J['B'])), 'S'))[1]
groups = {'A': [], 'C': [], 'S': []}
for g in arms: groups[toward(g)].append(g)

def add(name, conf, basis, g, src=loop_f, part_of='Proposed elevated deck around the Madiwala loop'):
    if g.is_empty: return
    out.append(named(src, g, name, conf, basis, part_of)); parts[name] = g

add('Proposed Rotary at Level-1 (above Madiwala junction and the underpass)', 'high',
    'the round, widest part of the deck, above the Madiwala underpass; label "Proposed Rotary at Level-1". Schedule B: elevated rotary, 157 m, four lanes on a 15 m carriageway', rotary)
add('Proposed Flyover at Level-1 (Madiwala rotary to Silk Board, along Hosur Road)', 'high',
    'the arm leaving the rotary to the south-east; label "Proposed Flyover at Level-1" sits beside it',
    shapely.unary_union(groups['S']))
add('Audgodi loop (Proposed Loop at Level-1): Hosur Road, rotary to St John\'s junction', 'high',
    'the arm leaving the rotary to the north-west, towards Adugodi. Schedule B of the tender lists it as the "Proposed Audgodi loop": two 7 m two-lane decks for 360 m, then one 17.2 m four-lane deck to 540 m. "Exit Ramp 01" is a separate ramp at junction C',
    shapely.unary_union(groups['C']))
# the 100 Feet Road arm carries a ramp that curves east onto Sarjapura Road just before junction A: cut it at its neck
armA = shapely.unary_union(groups['A'])
ramp = None
biggest = max(getattr(armA, 'geoms', [armA]), key=lambda g: g.area)
ring = np.array(biggest.exterior.coords)[:-1]
east = [i for i, c in enumerate(ring) if J['A'].distance(Point(c)) < 110]
def turn(i):                                       # interior angle test: concave (notch) vertices have negative cross product on a CCW ring
    a, b, c = ring[i - 1], ring[i], ring[(i + 1) % len(ring)]
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
ccw = shapely.Polygon(ring).exterior.is_ccw
notches = [i for i in east if (turn(i) < 0) == ccw and abs(turn(i)) > 1]
best = None
tip = Point(max((ring[i] for i in east), key=lambda c: c[0]))      # the ramp's far end, east of the arm
for i in notches:                                  # the neck: a notch with the deck's outer edge close by on the other side
    n = Point(ring[i])
    for j in east:
        d = n.distance(Point(ring[j])); steps = min(abs(i - j), len(ring) - abs(i - j))
        if 4 < d < 14 and steps > 8:
            cut = LineString([ring[i], ring[j]])
            mid = cut.interpolate(0.5, normalized=True)
            if biggest.contains(mid):
                v = np.array(ring[j]) - np.array(ring[i]); u = v / np.linalg.norm(v)
                cut = LineString([ring[i] - u * 0.5, ring[j] + u * 0.5])
                pieces = [p for p in split(biggest, cut).geoms]
                if len(pieces) == 2:
                    small = min(pieces, key=lambda p: p.area)
                    # the ramp is the piece that ends east of the arm, towards Sarjapura Road east of A
                    score = small.area                 # the whole ramp: the largest such piece that still ends at the east tip
                    if 80 < small.area < 1500 and small.distance(tip) < 1 and (best is None or score > best[0]): best = (score, small, max(pieces, key=lambda p: p.area))
if best:
    ramp = best[1]; armA = shapely.unary_union([best[2]] + [g for g in getattr(armA, 'geoms', [armA]) if g is not biggest])
add('Split flyover at Level-1: 100 Feet Road, Ejipura flyover to the Madivala rotary', 'high',
    'the arm leaving the rotary to the north-east, either side of the Ejipura flyover ramp. Schedule B of the tender lists it as "Ejipura to Madivala rotary": two 8.5 m two-lane decks, 360 m each. It is not the "loop": that is the Hosur Road arm', armA)
if ramp is not None:
    add('Down ramp at junction A, from the 100 Feet Road arm towards Agara (Sarjapura Road east)', 'medium',
        'the ramp that curves off the 100 Feet Road arm at junction A; the loop plan (KENDRIYA SADANA.pdf) labels it "Down Ramp towards Agara". It is not Entry Ramp 08', ramp)

# ---- 2. the other shapes ----------------------------------------------------------------------
lab = {f['properties']['label']: utm(shape(f['geometry'])) for f in L['features']}
end = lab.get('END OF PROJECT')
for f, g in zip(feats, geoms):
    layer = f['properties']['layer']
    if f is loop_f: continue
    if layer == 'proposed_deck':
        c = g.centroid; dx, dy = c.x - J['B'].x, c.y - J['B'].y
        if end is not None and g.distance(end) < 400 or dy < -1300:
            nm, cf, why = 'Proposed elevated corridor at Level-1, Silk Board to Bommanahalli (ends at "END OF PROJECT")', 'medium', 'the deck running south from Silk Board to the label "END OF PROJECT"'
        elif g.bounds[2] - g.bounds[0] > 6 * (g.bounds[3] - g.bounds[1]):
            nm, cf, why = 'Elevated Flyover at Level-1 from Marathahalli (ORR)', 'low', 'short east-west deck at the east side of Silk Board junction, under the Level-2 flyover'
        elif dx < 320:
            nm, cf, why = 'Level-1 connection to the Double Decker Flyover (towards Ragigudda / Banashankari)', 'low', 'the branch curving south-west beside the existing double-decker loop'
        else:
            nm, cf, why = 'Approach from 100 Feet Road to Electronic City (Level-1, through Silk Board)', 'low', 'the deck continuing south-east through Silk Board junction'
        out.append(named(f, g, nm, cf, why, 'Proposed elevated deck at Silk Board')); parts.setdefault(nm, g)
    elif layer == 'proposed_deck_level2':
        nm = 'Proposed Flyover at Level-2 (over Silk Board, towards Marathahalli / ORR)'
        out.append(named(f, g, nm, 'medium', 'between the dashed "START / END OF APPROACH, SECOND LEVEL" marks; a reading of the drawing'))
        parts[nm] = shapely.unary_union([parts.get(nm, g), g])
    elif layer == 'metro_tunnel':
        nm = 'Entry Ramp 08 (Sarjapur Road): ramp from Sarjapura Road down into the road tunnel (654 m, 2 lanes, cars only)'
        out.append(named(f, g, nm, 'high', 'named in the tunnel project report (Feb 2025, Table 9: "Entry Ramp 8 into Main Tunnel, from Sarjapur Road / HSR layout", 654 m, 2 lanes: 190 m open cut, 200 m cut-and-cover, 264 m open cut). Also: the loop plan (KENDRIYA SADANA.pdf) points the label "Entry Ramp 08 (Sarjapur Road)" at this band: it leaves Sarjapura Road by St John\'s, runs under the college playground with its own chainage (0+000 to 0+596) and joins "Main Tunnel Tube 2" at junction C. The tender sheets also write "Metro Line (Phase-3A)" here, but the metro runs along Sarjapura Road'))
        parts[nm] = g
    elif layer == 'existing_flyover':
        nm = 'Existing Double Decker Flyover and loop at Silk Board'
        out.append(named(f, g, nm, 'medium', 'olive fill; labels "Double Decker Flyover" and "Existing Flyover (Loop) at Level-1"')); parts[nm] = g
    elif layer == 'ejipura_flyover' and g.distance(LineString([J['A'], J['B']])) < 25:
        nm = 'Ejipura flyover ramp on 100 Feet Road (under construction)'
        out.append(named(f, g, nm, 'high', 'light-blue block between the two sides of 100 Feet Road, where the contract survey shows the ramp wall')); parts[nm] = g
    else:
        out.append(f)
S['features'] = out
json.dump(S, open(os.path.join(OUT, 'contract_structures.geojson'), 'w'))

# ---- 3. labels onto their parts ----------------------------------------------------------------
KEY = [('Proposed Rotary at Level-1', 'Proposed Rotary'), ('Proposed Flyover at Level-1', 'Proposed Flyover at Level-1'),
       ('Proposed Loop at Level-1', 'Audgodi loop (Proposed Loop at Level-1)'), ('Entry Ramp 08', 'Entry Ramp 08 (Sarjapur Road): ramp'),
       ('Proposed Flyover at Level-2', 'Proposed Flyover at Level-2'),
       ('Ejipura Flyover', 'Ejipura flyover ramp'), ('Elevated Flyover at Level-1 from Marathahalli', 'Elevated Flyover at Level-1 from Marathahalli'),
       ('Approach from 100 Feet Road', 'Approach from 100 Feet Road'), ('END OF PROJECT', 'Silk Board to Bommanahalli')]
moved = []
for f in L['features']:
    p = f['properties']; t = p['label']
    if 'drawn_lon' in p: f['geometry'] = {'type': 'Point', 'coordinates': [p['drawn_lon'], p['drawn_lat']]}   # re-run
    for starts, part in KEY:
        target = next((g for n, g in parts.items() if n.startswith(part)), None)
        if t.startswith(starts) and target is not None:
            here = utm(shape(f['geometry']))
            if t == 'END OF PROJECT': spot = shapely.ops.nearest_points(target, here)[0]
            else: spot = max(getattr(target, 'geoms', [target]), key=lambda g: g.area).representative_point()
            p['drawn_lon'], p['drawn_lat'] = f['geometry']['coordinates'][:2]
            p['placed'] = 'on the structure it names (best guess); the drawing writes it %d m away with a leader line' % here.distance(spot)
            f['geometry'] = mapping(ll(spot)); moved.append(t); break
json.dump(L, open(os.path.join(OUT, 'contract_labels.geojson'), 'w'))

print(f'rotary centre {centre.distance(J["B"]):.0f} m from junction B, radius {radius:.0f} m')
for f in out:
    p = f['properties']
    if p.get('name'): print(f"  {p['name_confidence']:6} {p['area_m2']:>6} m2  {p['name']}")
print('labels moved onto their structure:', len(moved), 'of', len(L['features']))
