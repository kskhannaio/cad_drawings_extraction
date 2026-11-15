# Corridor PDF pipeline

Pulls data out of the source PDFs for the Madiwala loop study (Bengaluru), so the map site and the traffic
simulation can use it. It is a short sequence of Python scripts run in order by `main.py`.

| Step | Script | Reads | Writes (in `out/`) |
|---|---|---|---|
| `roads` | `steps/s1_reference_roads.py` | `osm/corridor.osm.xml` | `corridor.net.xml`, the road network the drawings are fitted to |
| `register` | `steps/s2_register_sheets.py` | tender PDF, pages 24–40 | `georef.json`: where each of the 17 drawing sheets sits on the map |
| `ocr` | `steps/s3_read_linework_labels.py` | tender PDF | `ocr_labels.json`: labels that are drawn as pen strokes, not text |
| `extract` | `steps/s4_extract_drawings.py` | tender PDF | every line, shape and label (`full_*.geojsonl`), sheet images (`sheets/`), traced structures (`contract_structures.geojson`) and labels (`contract_labels.geojson`) |
| `names` | `steps/s5_name_parts.py` | the two files above | the same two files, with the flyover deck cut into named parts and labels moved onto them |
| `od` | `steps/s6_od_tables.py` | OD study PDF | `od/page*.csv` (the six tables) and `od/od_summary.json` |
| `metro` | `steps/s7_metro_survey.py` | hand-picked points on the scanned metro survey sheets (`steps/metro_survey_points.json`) | `metro_station.geojson`: the St John's Hospital station box, its land, parking area and the structure across the road |
| `loopplan` | `steps/s8_loop_plan.py` | hand-picked points on the plan of the loop (`steps/loop_plan_points.json`) | `loop_plan.geojson`: Exit Ramp 01, the tunnel-end strip and the pedestrian subway |

## Run

```sh
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt   # once
./.venv/bin/python main.py                 # everything (about 15 min the first time)
./.venv/bin/python main.py --from extract  # from one step onwards
./.venv/bin/python main.py --only od       # one step
./.venv/bin/python main.py --list
```

The `ocr` step also needs Tesseract with English data (Arch: `pacman -S tesseract tesseract-data-eng`).

## Source PDFs

Read from `../../docs` (set `PIPELINE_DOCS` to change it). They are not in this repo.

| PDF | Used for |
|---|---|
| `Ejipura to Silk Board Schedule A B C D F H I.pdf` (B-SMILE elevated-corridor tender) | drawing sheets: topographical survey 1–6, general alignment drawing 1–6, land acquisition plan 1–5 |
| `OD and Toll Analysis OMR to Silk Board.pdf` | daily traffic by vehicle type, share diverting to the elevated corridor, trips between entry and exit points |

| `BMRCL without tunnel-1.pdf` (metro survey, eight scanned sheets) | the metro station: placed from the survey benchmarks printed on the sheets, outlined by hand |
| `KENDRIYA SADANA.pdf` (the corridor's plan of the loop, one image sheet) | tunnel ramps and the subway: placed by fitting known points, outlined by hand |

The two scanned sources have no vector data, so their shapes are picked by hand and kept as pixel positions in
`steps/*_points.json`. To add or correct a shape, edit that file and re-run the step.

Not used yet: the corridor concept drawing (`OMR to Silk Board Concept 2-9-2025.pdf`, one vector sheet), read by eye so far.

## Who uses the output

- The study website's `scripts/build_plans.py` copies the traced structures and labels into its "What's planned" layer.
- The simulation repo's `qgis/make_contract_template.py` builds the QGIS contract template from everything in `out/`.

See [HOWTO.md](HOWTO.md) for how each step works.

## What to know before trusting it

- **Positions.** All 17 sheets are views of one CAD model. They are linked through shared labels and fitted to
  OpenStreetMap road edges in one go; the median error is 0.8–1.5 m (`out/georef_report.txt`).
- **Structures are traced by fill colour** (orange deck, olive existing flyovers, lavender metro, and so on).
- **Names are a best guess.** The drawings write most labels in clear space with a leader line. Each named shape
  carries `name_confidence` (high / medium / low) and `name_basis`.
- **The OD step checks the totals printed in the PDF** (27,300 vehicles a day; 16,842 diverting; 12,357 tollable)
  and stops if they no longer match.
- `out/` is derived from tender documents and is not committed.

Map data © OpenStreetMap contributors (ODbL).
