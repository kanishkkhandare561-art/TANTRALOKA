# Rebuilding the site

The scripts read the page images from the epub and write `data/`, `scans/` and `text/`.
Needs Python 3 with numpy, scipy, scikit-image, Pillow, rapidfuzz, wordfreq, and Tesseract 5 with the
`Latin`, `san` and `eng` models. The verse and Viveka data (`dep.json`) is made by `ext_dep.py` from a checkout of
the public sanskrit-depository repository (`data/tantraloka/`).

1. Unzip the epub so the page images are at `/tmp/ep/x/OEBPS/images/` (`p001.jpg`, `p002.png` …).
2. `python3 page.py pages 1 2 3 … 514` — per page: finds the footnote rule, lines, Devanagari lines and
   superscript note numbers, then OCRs the main text and notes (writes `pages/pNNN.json`).
   Then `fix_deva.py` and `fix_deva3.py` re-read lines whose script was misjudged (English read as Devanagari,
   or verses read as English), keeping whichever reading Tesseract is more confident of.
3. `python3 ext_dep.py` — the KSTS verses, Viveka and word analysis.
4. `python3 build.py` — cleans the text, restores IAST accents, numbers the footnotes and places their references.
5. `python3 build3.py` — paragraphs, headings (from the epub’s table of contents), verse alignment, HTML.
6. `python3 export.py <repo folder>` — writes the site’s `data/*.js` and the plain text.

`extra/p514.html` is the hand-transcribed table of Appendix B.
