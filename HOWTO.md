# How each step works

The tender's sheets are topographical survey 1–6, general alignment drawing 1–6 and land acquisition plan 1–5
(PDF pages 24–40), all vector CAD exports at 1:2000.

- **Georeferencing (step `register`).** The sheets are vector CAD views of one model at one scale. Every sheet is
  linked to GAD sheet 2 through labels both show (RANSAC on label positions, drawing area only; sheet 6 needs a
  shift-only fallback as it barely overlaps sheet 5). One similarity transform then maps the model to UTM 43N,
  fitted so the grey road areas' edges on all sheets land on road edges of a network built from
  `osm/corridor.osm.xml` (downloaded with `osm/corridor_query.overpassql`, built by step `roads`). Result: same scale on every sheet
  (0.691 m per PDF point), median road-edge error 0.8–1.5 m. Report: `out/georef_report.txt`.
- **Extraction (step `extract`).** Full data: every stroked line, filled shape and text line inside the drawing frame,
  with page/set/sheet, colours, width, text rotation and size; sheet and view frames, white masks and hatch dots
  are dropped. Named structures by fill colour (alignment drawings, plus yellow on the LA plans for land):
  orange = proposed deck, olive = existing flyovers, light blue = Ejipura flyover, lavender = metro and stations,
  bright orange = underpass or metro (by nearby labels), magenta near metro chainages (16+…) or tunnel labels =
  Phase-3A tunnel (hatching is widened and merged; both tubes share one alignment), mint = BMRCL land.
  Bright orange on the survey sheets gives the underpass. The three sets repeat one base map: each drawn entity
  is kept once, with a `sets` field listing every set that shows it.
- **Labels drawn as linework (step `ocr`).** Labels such as "Proposed Loop at Level-1" are magenta pen strokes, not
  text. The short magenta strokes are drawn to an image, grouped into labels, turned horizontal and read with
  Tesseract (both orientations, confidence >= 60). step `extract` corrects each reading to the closest of the
  drawings' known phrases (or keeps it as read if confidence >= 75) and marks it `ocr = yes` with the raw reading.
- **Level-2.** The deck's two levels share a colour. The drawings mark the second level with thick blue dashed
  lines across the corridor at "START OF APPROACH" and "END OF APPROACH" (SECOND LEVEL); a line is fitted through
  each set of dashes, and the deck between them within 30 m of the main deck's axis is `proposed_deck_level2`.
  The loops and ramps beside it stay Level-1.
- **Named parts (step `names`).** The drawings write most labels in clear space with a leader line, and the
  deck is traced as merged shapes. This step cuts the loop's deck into the rotary (the widest spot, above the
  underpass), the three arms leaving it and Entry Ramp 08, and gives every deck, Level-2 and tunnel shape a `name`,
  `name_confidence` (high / medium / low) and `name_basis`. Matching labels move onto their part; the drawn
  position stays in `drawn_lon` / `drawn_lat`. The names are a best-guess reading, weakest at Silk Board.
  step `extract`'s shapes are kept as `contract_structures_raw.geojson`, so the step can be re-run.
- Outputs (`out/`, the zip) are derived from the tender drawings and are not committed.
- **OD tables (step `od`).** `pymupdf` finds one table per page. Cells are written as printed, with line breaks
  removed; the PDF drops spaces inside headings and prints lengths such as 2.93 as "293 .", which are rebuilt.
  `od_summary.json` holds the figures the simulation uses: daily vehicles by type, the share of each type
  diverting to the elevated corridor, and the 26 entry-to-exit trip pairs. Printed totals are asserted.
