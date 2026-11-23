# Irvington Schools Public Records Archive

An unofficial, volunteer-run, full-text-searchable archive of public records from the Irvington Union Free School District (Irvington, NY). Not affiliated with the district.

**Website:** see the GitHub Pages link in this repository's About box.

## What's in `data/`
- `catalog.jsonl`: one JSON object per document: `id`, `coll` (boarddocs, website, wayback, pac, video), `kind`, `date`, `title`, `url` (the official original), `archive_url` (Internet Archive snapshot, where relevant), `text` (path under `data/text/`).
- `text/`: extracted plain text. Each file's first line names its source URL. Meeting transcripts (`text/video/*.txt`) are machine-generated (Whisper) with `[hh:mm:ss]` timestamps. Slide text (`*.slides.txt`) is OCR.
- `slides/`: presentation slides extracted from board meeting videos (WebP).

Originals are not stored here. Every record links to BoardDocs, the district website, a dated Wayback Machine snapshot, Google Drive (PTSA) or YouTube.

## Withheld material
Student-level special-education (CSE/CPSE) recommendation reports that were attached to some BoardDocs agendas are deliberately left out, as is a redacted special-education settlement. To report anything else that shouldn't be here, please open an issue.

## Building the site
```
python3 build/build.py && npx -y pagefind@1.3.0 --site site
python3 -m http.server -d site
```
GitHub Actions does this on every push to `main` and deploys to GitHub Pages.
