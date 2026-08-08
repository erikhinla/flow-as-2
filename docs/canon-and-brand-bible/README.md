# Canon and Brand Bible

This folder holds the project's Canon and Brand Bible: reference materials, canon documents, and brand guidance used by the project.

Source (original files):
- Google Drive: https://drive.google.com/drive/folders/19akQvWiWnxgeZ0v2YtX44aAWSssF1vnC?usp=drive_link

Purpose
- Collect authoritative canon docs and brand guidelines near the codebase so contributors can reference them in PRs, docs, and design work.

Recommended structure
- docs/canon-and-brand-bible/
  - README.md (this file)
  - assets/        — binary files (images, PDFs). Prefer small, optimized files.
  - references/    — text-based transcriptions, summaries, and canonical excerpts.

How to add materials
1. If a document is small (text, short markdown), add it directly under `references/` as Markdown with a short summary and a `source:` line pointing back to the Drive file.
2. For large binaries (PDFs, high-res images), add the file under `assets/` and include a small Markdown reference in `references/` that records provenance (who uploaded, when, original Drive link).
3. If you prefer *not* to store a copy, create a link-only entry in `references/` that contains the title, short summary, and the original Drive URL.

Filename and metadata conventions
- Filenames: lower-case, hyphen-separated, e.g. `brand-colors.md`, `canon-episode-list.md`.
- Add a YAML frontmatter or a short header with:
  - title: "..."
  - date: YYYY-MM-DD
  - author: Name or GitHub handle
  - source: original Drive link
  - summary: 1–2 sentences

Licensing & privacy
- Only add files you have the rights to include in this repo. If in doubt, add a link back to the Drive instead of copying.
- Document any license or usage restrictions in the file header.

Contributing
- Open a pull request adding the new file(s) and explain the provenance in the PR description.
- If adding many or large binaries, consider using a release or external hosting and link to it instead.

If you'd like, I can:
- Copy selected Drive files into this folder (you must confirm which files to copy and ensure sharing permissions allow it), or
- Add a script to sync specified Drive files automatically (will require credentials and a decision about where to store secrets).

