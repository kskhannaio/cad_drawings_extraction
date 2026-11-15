"""Build the road network the drawings are fitted to, from OpenStreetMap.

osm/corridor.osm.xml (downloaded with osm/corridor_query.overpassql: roads from the Madiwala loop south to
Bommanahalli) -> out/corridor.net.xml, in UTM 43N. Geometry is kept exactly as mapped: no joined junctions,
no guessed signals or footpaths, because only the road edges matter for the fit.
"""
import os, subprocess
from paths import OSM, OUT, NETCONVERT
import sumo

net = os.path.join(OUT, 'corridor.net.xml')
r = subprocess.run([NETCONVERT, '--osm-files', os.path.join(OSM, 'corridor.osm.xml'),
                    '--type-files', os.path.join(sumo.SUMO_HOME, 'data', 'typemap', 'osmNetconvert.typ.xml'),
                    '--output-file', net, '--output.street-names', 'true', '--proj.utm', 'true',
                    '--geometry.remove', 'false', '--lefthand', 'true', '--tls.guess', 'false',
                    '--junctions.join', 'false', '--sidewalks.guess', 'false', '--osm.layer-elevation', '6',
                    '--no-warnings', 'true'], capture_output=True, text=True)
if r.returncode: raise SystemExit(r.stdout[-2000:] + r.stderr[-2000:])
print(f'wrote {net} ({os.path.getsize(net) // 1_000_000} MB)')
