"""Step: export - turn the pipeline's working files (out/) into files the other repos use as they are.

Writes exports/ (tracked in git, except the QGIS files, which are large):

  exports/website/plans.geojson   the "What's planned" layer of the study website, ready to copy to its data/ folder:
                                  kind=structure (layer, what, area_m2; conf/basis for named parts; scan = which non-tender
                                  sheet a shape comes from; statement for the tunnel land) and kind=label (group = roads,
                                  metro or tunnel: the layer it goes with; labels known to be wrong are left out)
  exports/od/                     the origin-destination study's six tables (CSV) and od_summary.json
  exports/qgis/corridor_drawings.gpkg
                                  one GeoPackage (WGS84) for the QGIS templates:
                                    structures      every traced structure from every source, with its "source"
                                    labels          the drawings' labels, placed on what they name
                                    drawing_lines, drawing_shapes, drawing_text   every line, filled shape and text item,
                                                    in the drawing's own colours (stroke / fill / colour fields)
  exports/qgis/sheets/            the 17 tender sheets as images with world files (.pgw, .prj; UTM zone 43N)
  exports/manifest.json           what was written, when, and from which PDFs

Nothing here is specific to the simulation; turning these files into SUMO inputs is the simulation repo's job.
"""
import glob, json, os, shutil, time
import fiona
from fiona.crs import CRS
from pyproj import CRS as PCRS
from paths import OUT, ROOT

EXP = os.path.join(ROOT, 'exports')
for sub in ('website', 'od', 'qgis', os.path.join('qgis', 'sheets')):
    os.makedirs(os.path.join(EXP, sub), exist_ok=True)
rd = lambda name: json.load(open(os.path.join(OUT, name)))
rnd = lambda c: [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 6), round(c[1], 6)]   # about 10 cm

# sources of traced structures: the tender sheets, then shapes from other documents (scan = which one)
SOURCES = [('contract_structures.geojson', None), ('metro_station.geojson', 'metro'), ('loop_plan.geojson', 'loop'),
           ('concept_tunnel.geojson', 'concept'), ('tunnel_land.geojson', 'land')]
structures = []
for fname, scan in SOURCES:
    if not os.path.exists(os.path.join(OUT, fname)): print(f'  (no {fname} - its step has not run)'); continue
    for f in rd(fname)['features']:
        structures.append((f, scan))

# labels: which group of structures each names, so a map can show a label only with its layer; and labels the drawings
# get wrong, which the website leaves out (QGIS keeps them, with the reason)
import re
def label_group(text):
    t = text.lower()
    if re.search(r'tunnel|entry ramp|exit ramp', t): return 'tunnel'
    if re.search(r'metro|station', t): return 'metro'
    return 'roads'                                               # flyovers, loops, rotary, levels, approaches, underpass
WRONG = {'Metro Line (Phase-3A)': 'The general alignment drawing writes this on the band that is Entry Ramp 08 into the road tunnel '
                                  '(named on the plan of the loop and in the tunnel project report); the metro runs along Sarjapura Road.'}

# ---- website: the "What's planned" layer -------------------------------------------------------------------------
web = []
for f, scan in structures:
    p = f['properties']
    props = {'kind': 'structure', 'layer': p['layer'], 'what': p['what'], 'area_m2': p['area_m2']}
    if scan: props['scan'] = scan
    if p.get('name_confidence'): props.update(conf=p['name_confidence'], basis=p['name_basis'])
    if p.get('statement'): props.update(statement=p['statement'], statement_total_m2=p['statement_total_m2'])
    web.append({'type': 'Feature', 'properties': props, 'geometry': {'type': f['geometry']['type'], 'coordinates': rnd(f['geometry']['coordinates'])}})
for f in rd('contract_labels.geojson')['features']:
    p = f['properties']
    if p['label'] in WRONG: continue
    web.append({'type': 'Feature', 'properties': {'kind': 'label', 'label': p['label'], 'group': label_group(p['label']), 'source': p['source'].split(' (')[0],
                'ocr': 'OCR' in p['source'], 'moved': 'drawn_lon' in p}, 'geometry': {'type': 'Point', 'coordinates': rnd(f['geometry']['coordinates'])}})
web_path = os.path.join(EXP, 'website', 'plans.geojson')
json.dump({'type': 'FeatureCollection', 'features': web}, open(web_path, 'w'), separators=(',', ':'))
n = sum(f['properties']['kind'] == 'structure' for f in web)
print(f'  website/plans.geojson: {n} structures, {len(web) - n} labels, {os.path.getsize(web_path) // 1024} KB')

# ---- origin-destination tables -------------------------------------------------------------------------------------
od = []
for src in glob.glob(os.path.join(OUT, 'od', '*')):
    shutil.copy(src, os.path.join(EXP, 'od', os.path.basename(src))); od.append(os.path.basename(src))
print(f'  od/: {len(od)} files')

# ---- QGIS: one GeoPackage -----------------------------------------------------------------------------------------
GPKG = os.path.join(EXP, 'qgis', 'corridor_drawings.gpkg')
if os.path.exists(GPKG): os.remove(GPKG)
WGS84 = CRS.from_epsg(4326)
TYPES = {bool: 'bool', int: 'int', float: 'float', str: 'str'}

def write(layer, feats, geom):
    """feats: [(properties, geometry dict)]; field types from the values (a field mixing int and float is float)."""
    fields = {}
    for p, _ in feats:
        for k, v in p.items():
            if v is None: fields.setdefault(k, None); continue
            t = TYPES.get(type(v), 'str')
            old = fields.get(k)
            fields[k] = t if old in (None, t) else 'float' if {old, t} <= {'int', 'float'} else 'str'
    schema = {'geometry': geom, 'properties': {k: (t or 'str') for k, t in fields.items()}}
    with fiona.open(GPKG, 'w', driver='GPKG', layer=layer, crs=WGS84, schema=schema) as dst:
        dst.writerecords({'geometry': g, 'properties': {k: (str(p[k]) if schema['properties'][k] == 'str' and p.get(k) is not None else p.get(k))
                                                         for k in fields}} for p, g in feats)
    print(f'  qgis/corridor_drawings.gpkg | {layer}: {len(feats)}')

keys = ('layer', 'what', 'name', 'part_of', 'area_m2', 'length_m', 'name_confidence', 'name_basis', 'statement', 'statement_total_m2', 'source')
rows = []
for f, scan in structures:
    p = f['properties']; g = f['geometry']
    if g['type'] == 'Polygon': g = {'type': 'MultiPolygon', 'coordinates': [g['coordinates']]}
    rows.append(({k: p.get(k) for k in keys}, g))
write('structures', rows, 'MultiPolygon')
write('labels', [({**f['properties'], 'group': label_group(f['properties']['label']), 'wrong': WRONG.get(f['properties']['label'])}, f['geometry'])
                 for f in rd('contract_labels.geojson')['features']], 'Point')
for layer, fname, geom in (('drawing_lines', 'full_lines.geojsonl', 'LineString'), ('drawing_shapes', 'full_polygons.geojsonl', 'MultiPolygon'),
                           ('drawing_text', 'full_text.geojsonl', 'Point')):
    feats = []
    for line in open(os.path.join(OUT, fname)):
        f = json.loads(line); g = f['geometry']
        if g['type'] == 'Polygon': g = {'type': 'MultiPolygon', 'coordinates': [g['coordinates']]}
        feats.append((f['properties'], g))
    write(layer, feats, geom)

# sheet images with their world files; .prj so any GIS knows they are UTM 43N
prj = PCRS.from_epsg(32643).to_wkt(version='WKT1_ESRI')
nsheets = 0
for png in sorted(glob.glob(os.path.join(OUT, 'sheets', '*.png'))):
    base = os.path.splitext(os.path.basename(png))[0]
    shutil.copy(png, os.path.join(EXP, 'qgis', 'sheets', base + '.png'))
    shutil.copy(os.path.join(OUT, 'sheets', base + '.pgw'), os.path.join(EXP, 'qgis', 'sheets', base + '.pgw'))
    open(os.path.join(EXP, 'qgis', 'sheets', base + '.prj'), 'w').write(prj)
    nsheets += 1
print(f'  qgis/sheets/: {nsheets} sheets')

# ---- manifest -------------------------------------------------------------------------------------------------------
from paths import DOCS
json.dump({'built': time.strftime('%Y-%m-%d %H:%M'), 'source_pdfs_folder': os.path.relpath(DOCS, ROOT),
           'files': {os.path.relpath(p, EXP): os.path.getsize(p) for p in sorted(glob.glob(os.path.join(EXP, '**', '*'), recursive=True))
                     if os.path.isfile(p) and not p.endswith('manifest.json')}},
          open(os.path.join(EXP, 'manifest.json'), 'w'), indent=1)
print(f'  exports written to {EXP}')
