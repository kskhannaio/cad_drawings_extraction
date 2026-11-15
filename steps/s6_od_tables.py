"""Pull the traffic and toll tables out of the origin-destination study.

"OD and Toll Analysis OMR to Silk Board.pdf" is six pages, one table each:
  1 daily vehicles by type on the corridor, year by year to 2050-51
  2 the same in passenger-car units at Ejipura junction
  3 diversion to the elevated corridor and tollable traffic, by vehicle type and year
  4 road length between entry and exit points          5 structure length between them
  6 trips diverted to the elevated corridor, between each pair of entry and exit points

Writes out/od/page<n>_<name>.csv (cells as printed, line breaks removed) and out/od/od_summary.json with the
figures the simulation uses. The PDF drops the spaces between words in headings, and prints lengths such as 2.93
as "293 ."; those lengths are put back together. Known totals are checked so a changed PDF fails loudly.
"""
import csv, json, os, re
import pymupdf
from paths import OD_PDF, OUT

NAMES = {1: 'vehicles_by_year', 2: 'pcu_at_ejipura_by_year', 3: 'diversion_and_toll', 4: 'road_length_km',
         5: 'structure_length_km', 6: 'diverted_trips_by_entry_exit'}
out = os.path.join(OUT, 'od'); os.makedirs(out, exist_ok=True)

def clean(cell):
    t = re.sub(r'\s+', ' ', cell or '').strip()
    m = re.fullmatch(r'(\d)(\d\d?) ?\.', t)                 # "293 ." is 2.93, "12 ." is 1.2
    return f'{m.group(1)}.{m.group(2)}' if m else t
num = lambda t: float(t.replace(',', '').rstrip('%')) if re.fullmatch(r'-?[\d,]*\.?\d+%?', t or '') else None

tables = {}
doc = pymupdf.open(OD_PDF)
for i, page in enumerate(doc, 1):
    found = page.find_tables().tables
    assert len(found) == 1, f'page {i}: expected one table, found {len(found)}'
    rows = [[clean(c) for c in r] for r in found[0].extract()]
    tables[i] = rows
    with open(os.path.join(out, f'page{i}_{NAMES[i]}.csv'), 'w', newline='') as f: csv.writer(f).writerows(rows)

# ---- the figures the simulation uses, with checks against the totals printed in the PDF ----
head = tables[1][1]; today = tables[1][2]                  # ADT 2025-26
types = [re.sub(r'(?<=[a-z/&])(?=[A-Z])', ' ', h.replace(' ', '')) for h in head[2:14]]
adt = dict(zip(types, [int(num(v)) for v in today[2:14]])); total = int(num(today[14]))
assert sum(adt.values()) == total == 27300, f'daily total changed: {sum(adt.values())} / {total}'
t3 = {r[1]: r for r in tables[3]}
row = lambda start: next(r for k, r in t3.items() if k.replace(' ', '').lower().startswith(start))
share = dict(zip(types, [num(v) for v in row('%ofanticipateddiversion')[2:14]]))
diverted = int(num(row('anticipateddiversionoftraffic')[14])); tollable = int(num(row('tolabletraffic')[14]))
aadt = int(num(row('aadtfortheyear')[14]))
assert (diverted, tollable) == (16842, 12357), f'diversion totals changed: {diverted}, {tollable}'
pairs = []
t6 = tables[6]; h6 = [h.replace(' ', '').lower() for h in t6[1]]
c_from, c_to = h6.index('from'), h6.index('to')
c_n = max(i for i, h in enumerate(h6) if h == 'odsurveyvehicleinnos')    # the second such column is per pair; the first is per origin
place = lambda t: re.sub(r'\s+', ' ', re.sub(r'^\d+a?\s*\.?\s*', '', t).replace(' .', '').replace('.', ' ')).strip()
origin = None
for r in t6[2:]:
    if r[c_from]: origin = r[c_from]
    if origin and r[c_to] and num(r[c_n]) is not None and r[1] != 'Total':
        pairs.append({'from': place(origin), 'to': place(r[c_to]), 'vehicles_per_day': int(num(r[c_n]))})
assert sum(p['vehicles_per_day'] for p in pairs) == diverted, f"entry-exit trips sum to {sum(p['vehicles_per_day'] for p in pairs)}, not {diverted}"
growth = round((num(tables[1][3][14]) / total - 1) * 100, 2)
summary = {'source': os.path.basename(OD_PDF), 'year': '2025-26', 'corridor': 'Indiranagar to Silk Board, both directions',
           'vehicles_per_day': adt, 'vehicles_per_day_total': total, 'aadt_total': aadt, 'growth_percent_per_year': growth,
           'share_diverting_to_elevated_corridor_percent': share, 'diverted_vehicles_per_day': diverted,
           'diverted_share_of_aadt_percent': round(diverted / aadt * 100, 1), 'tollable_vehicles_per_day': tollable,
           'diverted_trips_by_entry_exit': pairs}
json.dump(summary, open(os.path.join(out, 'od_summary.json'), 'w'), indent=1)
print(f"wrote {len(tables)} tables to {out}; {total} vehicles/day, {diverted} diverting ({summary['diverted_share_of_aadt_percent']}% of AADT), "
      f"{len(pairs)} entry-exit pairs, growth {growth}%/year")
