# Tantrāloka — private study copy

Private repository. Not for redistribution.

*Tantrāloka: The Light On and Of the Tantras*, Volume One, Chapter One, by Abhinavagupta, with Jayaratha’s
commentary (Viveka), translated with explanatory notes by Mark S. G. Dyczkowski (2023). © the translator / publisher.

## Reading the book

The whole book is laid out as a reading site: open **`index.html`** in a browser.

- On your computer: download the repository (**Code → Download ZIP** on GitHub), unzip it, and double-click
  `index.html`. Everything works from the folder; an internet connection only adds the web fonts.
- **Do not turn on GitHub Pages for this repository.** On GitHub’s personal plans a Pages site is public even when
  the repository is private, so it would publish the book to anyone with the link.

What the site has:

- **Every page of the book**, in order, with its printed page number in the margin. Select a page number to see
  the scan of that page next to the text — that is the place to check any word.
- **All the footnotes** (about 1,400). Select a note number in the text to read the note where you are; each
  section ends with its notes, and the *Footnotes* tab lists all of them with a filter.
- **The verses in Devanagari, word by word.** Each line of a verse is matched to the Kashmir Series of Texts and
  Studies edition of the Tantrāloka (KSTS vol. 23, 1918), so every word can be selected for its sandhi split,
  grammar and meaning (Trika glossary and Monier-Williams). Lines that could not be matched (quotations, a few
  differing readings) are shown as read from the page, in grey; their words still open a transliteration.
- **Jayaratha’s Viveka in Sanskrit** under every verse (the *Viveka* button), with the KSTS editor’s notes, and
  the same word-by-word meanings.
- **Search** across the translation, notes, verses and Viveka. Accents are optional (*siva* finds *Śiva*), and a
  Devanagari search also finds romanised words.
- The verse index (*Verses* tab), a contents sidebar, dark mode and text size.

How it was made, and its limits: the e-book contains only page images, so the text was read by OCR (Tesseract,
Latin-script and Sanskrit models), page by page, separating the main text from the footnotes and finding the
superscript note numbers. Romanised Sanskrit was checked against a word list drawn from the Tantrāloka itself.
It has not been proofread by hand: expect some misread letters (especially accents), and a few footnote numbers in
the text that could not be placed — those notes still appear at the end of their section. The table on p. 500
(Appendix B) was transcribed by hand.

## Files

- `index.html`, `assets/`, `data/` — the reading site (`data/*.js` hold the text, notes, Viveka and word data).
- `scans/` — the 514 page images from the e-book (reduced to 4 grey levels).
- `book/Tantraloka-Vol1-Ch1-Dyczkowski.epub` — the e-book itself.
- `text/Tantraloka-Vol1-Ch1-Dyczkowski.txt` — plain text of the book with the footnotes, page by page.
- `build/` — the scripts that made the site from the epub (see `build/README.md`).

The Sanskrit text of the verses and the Viveka, and the word analysis, come from the public Sanskrit Depository
project (KSTS edition, public domain; verse e-text after Jun Takashima’s GRETIL file, CC BY-NC-SA).
