# Corridor PDF pipeline

Pulls data out of the source PDFs for the Madiwala loop study (Bengaluru). Given the PDFs, it ends with files the study
website and the QGIS templates use as they are, in `exports/`. It is a short sequence of Python scripts run in order by
`main.py`. Turning these files into simulation (SUMO) inputs is not done here: that lives in the simulation repo.

| Step | Script | Reads | Writes (in `out/`) |
|---|---|---|---|
| `roads` | `steps/s1_reference_roads.py` | `osm/corridor.osm.xml` | `corridor.net.xml`, the road network the drawings are fitted to |
| `register` | `steps/s2_register_sheets.py` | tender PDF, pages 24–40 | `georef.json`: where each of the 17 drawing sheets sits on the map |
| `ocr` | `steps/s3_read_linework_labels.py` | tender PDF | `ocr_labels.json`: labels that are drawn as pen strokes, not text |
| `extract` | `steps/s4_extract_drawings.py` | tender PDF | every line, shape and label (`full_*.geojsonl`), sheet images (`sheets/`), traced structures (`contract_structures.geojson`) and labels (`contract_labels.geojson`) |
| `names` | `steps/s5_name_parts.py` | the two files above | the same two files, with the flyover deck cut into named parts and labels moved onto them |
| `od` | `steps/s6_od_tables.py` | OD study PDF | `od/page*.csv` (the six tables) and `od/od_summary.json` |
| `metro` | `steps/s7_metro_survey.py` | hand-picked points on the eight scanned metro survey sheets (`steps/metro_survey_points.json`) | `metro_station.geojson`: St John's Hospital, Koramangala and Jakkasandra station boxes, the land and structures marked for them, and the line from junction A to Jakkasandra |
| `loopplan` | `steps/s8_loop_plan.py` | hand-picked points on the plan of the loop (`steps/loop_plan_points.json`) | `loop_plan.geojson`: the tunnel approach to the Audgodi loop and the pedestrian subway |
| `concept` | `steps/s9_concept_tunnel.py` | corridor concept drawing (vector) | `concept_tunnel.geojson`: the road tunnel's two tubes, the TBM shaft they end in, and the ramps to St John's junction including Exit Ramp 01 |
| `tunnelland` | `steps/s10_tunnel_land.py` | tunnel land acquisition plan, St Johns Junction sheet (vector) | `tunnel_land.geojson`: land needed for the road tunnel, with the sheet's area statement |
| `export` | `steps/s11_export.py` | everything above | **`exports/`**: the finished files below |

## What comes out: `exports/`

| File | For | What it is |
|---|---|---|
| `exports/website/plans.geojson` | the study website's "What's planned" tab | every traced structure and label, in the exact form the site reads; the site's `scripts/build_plans.py` copies it to `data/plans.geojson` |
| `exports/qgis/corridor_drawings.gpkg` | the QGIS contract template | one GeoPackage (WGS84): `structures` (all sources, each with its `source`), `labels`, and the full drawing data `drawing_lines`, `drawing_shapes`, `drawing_text` in the drawing's own colours |
| `exports/qgis/sheets/` | the QGIS contract template | the 17 tender sheets as PNG images with world files (`.pgw`) and projection (`.prj`, UTM zone 43N); any GIS opens them in place |
| `exports/od/` | the website's figures and the simulation | the origin-destination study's six tables (CSV) and `od_summary.json` |
| `exports/manifest.json` | anyone | what was written, when, and the size of each file |

`exports/website/` and `exports/od/` are committed. `exports/qgis/` (about 60 MB) is not: run `python main.py --only export`
after the other steps to make it. The QGIS template is built from it in the simulation repo (`qgis/make_contract_template.py`).

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

| `BMRCL without tunnel-1.pdf` (metro survey, eight scanned sheets) | Metro Phase-3A along Sarjapura Road: placed from the survey benchmarks and track chainages printed on the sheets (each sheet has its own scale), outlined by hand |
| `KENDRIYA SADANA.pdf` (the corridor's plan of the loop, one image sheet) | the tunnel approach and the subway: placed by fitting known points, outlined by hand |
| `OMR to Silk Board Concept 2-9-2025.pdf` (corridor concept drawing, one vector sheet) | the road tunnel west of St John's junction: placed through labels shared with the tender sheets, traced by colour |

The two scanned sources have no vector data, so their shapes are picked by hand and kept as pixel positions in
`steps/*_points.json`. To add or correct a shape, edit that file and re-run the step.

Only the part of the concept drawing around the loop is used so far; it also covers the corridor north to Old Madras Road.

## Who uses the output

- The study website's `scripts/build_plans.py` copies `exports/website/plans.geojson` into its "What's planned" layer.
- The simulation repo's `qgis/make_contract_template.py` styles and packages `exports/qgis/` into the QGIS contract template.
- The simulation repo's `scripts/import_pipeline.py` checks its traffic settings against `exports/od/od_summary.json`.

SUMO is installed here only as a tool: the `roads` step uses its `netconvert` to turn the OpenStreetMap extract into
road-centre geometry that the drawing sheets are fitted to. Nothing here produces simulation input.

See [HOWTO.md](HOWTO.md) for how each step works.

## What to know before trusting it

- **Positions.** All 17 sheets are views of one CAD model. They are linked through shared labels and fitted to
  OpenStreetMap road edges in one go; the median error is 0.8–1.5 m (`out/georef_report.txt`).
- **Structures are traced by fill colour** (orange deck, olive existing flyovers, lavender metro, and so on).
- **Names are a best guess.** The drawings write most labels in clear space with a leader line. Each named shape
  carries `name_confidence` (high / medium / low) and `name_basis`.
- **The OD step checks the totals printed in the PDF** (27,300 vehicles a day; 16,842 diverting; 12,357 tollable)
  and stops if they no longer match.
- `out/` (working files) and `exports/qgis/` are derived from tender documents and are not committed.

Map data © OpenStreetMap contributors (ODbL).
