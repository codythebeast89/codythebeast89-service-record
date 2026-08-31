# codythebeast89-service-record

Public GitHub Pages service record for **codythebeast89**, generated from the
[QMC tracker spreadsheet](https://docs.google.com/spreadsheets/d/1RayD8PRCVwut5gRG3_awt3HcWBKMH3lIker09dAMBYI/edit).

Live site: **https://codythebeast89.github.io/codythebeast89-service-record/**

Each tracker section is its own page with animated transitions when navigating via the top nav.

## Pages

| Page | File |
|------|------|
| Profile (home) | `index.html` |
| Decorations | `decorations.html` |
| Overseas Bar proof | `osb.html` |
| JSA proof | `jsa.html` |
| Army Sea Duty / Campaign | `asd.html` |
| Southwest Asia Service | `swa.html` |
| Kosovo Campaign | `kosovo.html` |
| Afghanistan Campaign | `afghanistan.html` |
| Iraq Campaign | `iraq.html` |

## Contents

- **Profile** — username, Roblox ID, Discord ID, rank, unit, and service details
- **Decorations** — badges (hardcoded layout) and obtained ribbons from the tracker
- **Proof tabs** — one HTML page per proof tab (OSB, JSA, ASD, SWA, Kosovo, Afghanistan, Iraq)

## Local build

Requires Python 3.10+ and a valid Google Sheets OAuth token from
[awards-tui](https://github.com/codythebeast89/awards-tui) at
`~/Projects/awards-tui/token.json` (or set `AWARDS_TOKEN_PATH`).

```bash
python3 scripts/build_site.py
```

Output is written to `docs/` — one HTML file per section plus shared `style.css` and `nav.js`.

## GitHub Actions / Pages setup

1. Enable **GitHub Pages** for this repo: Settings → Pages → Source = **GitHub Actions**.
2. Add repository secret **`AWARDS_TOKEN_JSON`**: base64-encoded contents of `token.json`.

   ```bash
   base64 -w0 ~/Projects/awards-tui/token.json
   ```

   Paste the output as the secret value (single line, no wrapping).

3. Optional fallback: set **`AWARDS_TOKEN_PATH`** if using a self-hosted runner with the token on disk.

The workflow (`.github/workflows/pages.yml`) rebuilds on every push to `main`/`master` and on manual dispatch.

## Configuration

`config.json` holds spreadsheet ID, photo URL, and tracker links. Badge sections are defined in
`scripts/build_site.py` (mirroring `copy_and_populate_decorations.py` in awards-tui). Ribbons are
pulled live from the **Ribbons** sheet where **Obtained?** = `Obtained`.

## Palette

Military reference colors: `#434343`, `#980000`, `#cc0000`, `#e69138`.
