#!/usr/bin/env python3
"""Pull data out of the corridor's source PDFs.

Runs the steps below in order. Each step is a plain script in steps/ that reads and writes files in out/.

  python main.py                 every step
  python main.py --from extract  start at a step and carry on to the end
  python main.py --only od       one step (several: --only extract,names)
  python main.py --list          show the steps

Source PDFs are read from ../../docs (see paths.py to change that).
"""
import argparse, os, runpy, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)                       # so steps can `from paths import ...`

STEPS = [   # (name, script, what it does)
    ('roads',    's1_reference_roads.py',      'build the OpenStreetMap road network the drawings are fitted to'),
    ('register', 's2_register_sheets.py',      'place the 17 tender drawing sheets on the map (about 3 min)'),
    ('ocr',      's3_read_linework_labels.py', 'read labels that are drawn as pen strokes (about 8 min first time, then cached)'),
    ('extract',  's4_extract_drawings.py',     'extract every line, shape and label, and trace the structures (about 1 min)'),
    ('names',    's5_name_parts.py',           'cut the flyover deck into named parts and move labels onto them'),
    ('od',       's6_od_tables.py',            'pull the traffic and toll tables out of the origin-destination study'),
    ('metro',    's7_metro_survey.py',         'place Metro Phase-3A from the scanned survey sheets: three stations and the line to Jakkasandra'),
    ('loopplan', 's8_loop_plan.py',            'trace the tunnel approach and the subway from the plan of the loop'),
    ('concept',  's9_concept_tunnel.py',       'trace the road tunnel tubes and their ramps from the corridor concept drawing (about 2 min)'),
]
NAMES = [s[0] for s in STEPS]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--from', dest='start', choices=NAMES); ap.add_argument('--only'); ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if a.list:
        for name, script, what in STEPS: print(f'{name:9} {what}')
        return
    todo = NAMES[NAMES.index(a.start):] if a.start else NAMES
    if a.only:
        todo = a.only.split(',')
        unknown = [n for n in todo if n not in NAMES]
        if unknown: sys.exit(f'unknown step(s): {", ".join(unknown)}. Steps: {", ".join(NAMES)}')
    for name, script, what in STEPS:
        if name not in todo: continue
        print(f'== {name}: {what}', flush=True); t = time.time()
        runpy.run_path(os.path.join(ROOT, 'steps', script), run_name='__main__')
        print(f'   ({time.time() - t:.0f}s)', flush=True)
    print(f'\ndone - results are in {os.path.join(ROOT, "out")}')

if __name__ == '__main__':
    main()
