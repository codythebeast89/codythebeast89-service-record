#!/usr/bin/env python3
"""Build static service record site from Google Sheets tracker data."""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sheets_client import get_values, load_token, resolve_token_path  # noqa: E402

CONFIG_PATH = ROOT / "config.json"
IMAGE_MAP_PATH = ROOT / "data" / "image-map.json"
STYLE_SRC = ROOT / "docs" / "style.css"
DOCS_DIR = ROOT / "docs"
INDEX_PATH = DOCS_DIR / "index.html"

# Hardcoded badge layout from copy_and_populate_decorations.py
BADGE_SECTIONS: list[dict] = [
    {
        "group": "Group 1",
        "items": [{"name": "Master Combat Action Badge", "device": "3rd Award"}],
    },
    {
        "group": "Group 2",
        "items": [{"name": "Expert Soldier Badge", "device": "-"}],
    },
    {
        "group": "Group 3",
        "items": [{"name": "Aviator Badge", "device": "Basic"}],
    },
    {
        "group": "Group 5",
        "items": [{"name": "Driver and Mechanic Badges", "device": "Driver T, W & Operator"}],
    },
    {
        "group": "Special",
        "items": [
            {"name": "Master Gunner Identification Badge", "device": "Master"},
            {
                "name": "Combat Service Identification Badge",
                "device": "1CAV, NATO, Afghanistan, Kosovo, Sea Duty, MATCOM CSIB",
            },
            {"name": "Sapper Tab", "device": "-"},
            {"name": "Overseas Bar", "device": "x9"},
            {"name": "Service Stripe", "device": "x4"},
            {"name": "Queens Dedication Medal", "device": "-"},
        ],
    },
]

PROOF_TABS = [
    ("Proof - Overseas Bar", "Overseas Bar Proof"),
    ("Proof - JSA", "Joint Service Achievement Proof"),
    ("Proof - ASD", "Army Sea Duty / Campaign Proof"),
    ("Proof - SWA Service", "Southwest Asia Service Proof"),
    ("Proof - Kosovo", "Kosovo Campaign Proof"),
    ("Proof - Afghanistan", "Afghanistan Campaign Proof"),
]

PROFILE_FIELDS = [
    "Username",
    "Roblox ID",
    "Discord ID",
    "Rank",
    "Command",
    "Division",
    "Brigade/Battalion/Group",
    "Company",
    "Join Date",
    "Unit Time of Service",
    "Position",
    "Position Date of Hire",
]


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_image_map() -> dict:
    if not IMAGE_MAP_PATH.is_file():
        return {"badges": {}, "ribbons": {}, "foreign": {}}
    with IMAGE_MAP_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def norm_key(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def lookup_image(maps: dict, category: str, name: str) -> str | None:
    bucket = maps.get(category, {})
    key = norm_key(name)
    if key in bucket:
        return bucket[key]
    for map_key, url in bucket.items():
        if key in map_key or map_key in key:
            return url
    return None


def esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def cell(row: list[str], index: int, default: str = "") -> str:
    if index < len(row):
        return str(row[index]).strip()
    return default


def fetch_profile(tok: dict, sheet_id: str, token_path: Path) -> dict[str, str]:
    rows = get_values(tok, sheet_id, "Profile", "G7:J20", persist_path=token_path)
    profile: dict[str, str] = {}
    for row in rows:
        label = cell(row, 0)
        value = cell(row, 2)
        if label:
            profile[label] = value
    title_rows = get_values(tok, sheet_id, "Profile", "C5:C5", persist_path=token_path)
    if title_rows and title_rows[0]:
        profile["_title"] = cell(title_rows[0], 0)
    return profile


def fetch_obtained_ribbons(tok: dict, sheet_id: str, token_path: Path) -> list[tuple[str, str]]:
    rows = get_values(tok, sheet_id, "Ribbons", "A1:E200", persist_path=token_path)
    if not rows:
        return []
    obtained: list[tuple[str, str]] = []
    for row in rows[1:]:
        name = cell(row, 0)
        status = cell(row, 3)
        device = cell(row, 4, "N/A")
        if name and status == "Obtained":
            obtained.append((name, device if device and device != "N/A" else ""))
    return obtained


def fetch_table(tok: dict, sheet_id: str, sheet: str, token_path: Path) -> tuple[list[str], list[list[str]]]:
    rows = get_values(tok, sheet_id, sheet, "A1:Z500", persist_path=token_path)
    if not rows:
        return [], []
    header = [cell(rows[0], i) for i, _ in enumerate(rows[0])]
    while header and not header[-1]:
        header.pop()
    body: list[list[str]] = []
    for row in rows[1:]:
        cells = [cell(row, i) for i in range(len(header))]
        if any(cells):
            body.append(cells)
    return header, body


def fetch_events(tok: dict, sheet_id: str, token_path: Path) -> list[dict]:
    """Parse Events Log tab with side-by-side sections (AFA / Expeditions / Courses)."""
    rows = get_values(tok, sheet_id, "Events Log", "A1:Z200", persist_path=token_path)
    if not rows:
        return []

    title_idx: int | None = None
    for idx in range(len(rows) - 1):
        header_row = rows[idx + 1]
        if not any(cell(header_row, col) == "Date" for col in range(2, len(header_row))):
            continue
        title_row = rows[idx]
        titles = [
            (col, cell(title_row, col))
            for col in range(2, len(title_row))
            if cell(title_row, col) and cell(title_row, col) != "Events"
        ]
        if titles:
            title_idx = idx
            break

    if title_idx is None:
        return []

    title_row = rows[title_idx]
    header_row = rows[title_idx + 1]
    starts = [
        (col, cell(title_row, col))
        for col in range(2, len(title_row))
        if cell(title_row, col) and cell(title_row, col) != "Events"
    ]

    blocks: list[dict] = []
    for block_index, (start_col, title) in enumerate(starts):
        end_col = starts[block_index + 1][0] if block_index + 1 < len(starts) else max(len(header_row), 26)
        header_cols = [
            (cell(header_row, col), col)
            for col in range(start_col, end_col)
            if cell(header_row, col)
        ]
        if not header_cols:
            continue

        data_rows: list[list[str]] = []
        for row in rows[title_idx + 2 :]:
            values = [cell(row, col) for _, col in header_cols]
            if any(values):
                data_rows.append(values)

        blocks.append(
            {
                "title": title,
                "headers": [header for header, _ in header_cols],
                "rows": data_rows,
            }
        )
    return blocks


def render_badge_sections(maps: dict) -> str:
    chunks: list[str] = ['<div class="badge-groups">']
    for section in BADGE_SECTIONS:
        chunks.append(f'<div class="badge-group"><h3>{esc(section["group"])}</h3><ul class="badge-list">')
        for item in section["items"]:
            name = item["name"]
            device = item["device"]
            category = "foreign" if "medal" in name.lower() else "badges"
            img = lookup_image(maps, category, name) or lookup_image(maps, "badges", name)
            img_tag = f'<img src="{esc(img)}" alt="" loading="lazy">' if img else ""
            device_html = f'<div class="badge-card__device">{esc(device)}</div>' if device and device != "-" else ""
            chunks.append(
                "<li class=\"badge-card\">"
                f"{img_tag}<div><div class=\"badge-card__name\">{esc(name)}</div>{device_html}</div>"
                "</li>"
            )
        chunks.append("</ul></div>")
    chunks.append("</div>")
    return "".join(chunks)


def render_ribbons(maps: dict, ribbons: list[tuple[str, str]]) -> str:
    chunks = [f'<p class="ribbon-count">{len(ribbons)} Ribbons Obtained</p><div class="ribbon-grid">']
    for name, device in ribbons:
        img = lookup_image(maps, "ribbons", name)
        img_tag = f'<img src="{esc(img)}" alt="" loading="lazy">' if img else ""
        device_html = f'<div class="ribbon-card__device">{esc(device)}</div>' if device else ""
        chunks.append(
            '<div class="ribbon-card">'
            f"{img_tag}<div><div class=\"ribbon-card__name\">{esc(name)}</div>{device_html}</div>"
            "</div>"
        )
    chunks.append("</div>")
    return "".join(chunks)


def status_class(status: str) -> str:
    lowered = status.lower()
    if "log" in lowered:
        return "status-logged"
    if "pend" in lowered:
        return "status-pending"
    return ""


def render_table(header: list[str], body: list[list[str]]) -> str:
    if not header:
        return '<p class="meta-note">No data available.</p>'
    chunks = ['<div class="table-wrap"><table><thead><tr>']
    for col in header:
        chunks.append(f"<th>{esc(col)}</th>")
    chunks.append("</tr></thead><tbody>")
    for row in body:
        chunks.append("<tr>")
        for idx, col in enumerate(header):
            value = cell(row, idx)
            if header[idx].lower() == "status":
                cls = status_class(value)
                chunks.append(f'<td class="{cls}">{esc(value)}</td>' if cls else f"<td>{esc(value)}</td>")
            else:
                chunks.append(f"<td>{esc(value)}</td>")
        chunks.append("</tr>")
    chunks.append("</tbody></table></div>")
    return "".join(chunks)


def render_events(blocks: list[dict]) -> str:
    if not blocks:
        return '<p class="meta-note">No events logged yet.</p>'
    chunks: list[str] = []
    for block in blocks:
        rows = block.get("rows", [])
        chunks.append(f'<div class="events-block"><h3>{esc(block["title"])}</h3>')
        if not rows:
            chunks.append('<p class="meta-note">No entries yet.</p></div>')
            continue
        headers = block.get("headers") or ["Date", "Event"]
        chunks.append('<div class="table-wrap"><table><thead><tr>')
        for h in headers:
            chunks.append(f"<th>{esc(h)}</th>")
        chunks.append("</tr></thead><tbody>")
        for row in rows:
            chunks.append("<tr>")
            for idx in range(len(headers)):
                chunks.append(f"<td>{esc(cell(row, idx))}</td>")
            chunks.append("</tr>")
        chunks.append("</tbody></table></div></div>")
    return "".join(chunks)


def render_profile(profile: dict[str, str], photo_url: str) -> str:
    title = profile.get("_title") or f"{profile.get('Username', 'Service Record')} | Service Record File"
    chunks = [
        f'<dl class="profile-grid">',
        f'<div class="profile-photo"><img src="{esc(photo_url)}" alt="Service photo"></div>',
    ]
    for field in PROFILE_FIELDS:
        value = profile.get(field, "")
        if not value:
            continue
        chunks.append(f"<dt>{esc(field)}</dt><dd>{esc(value)}</dd>")
    chunks.append("</dl>")
    chunks.append(f'<p class="meta-note">Generated from tracker data. Title: {esc(title)}</p>')
    return "".join(chunks)


def build_html(
    config: dict,
    profile: dict[str, str],
    ribbons: list[tuple[str, str]],
    proof_tables: list[tuple[str, list[str], list[list[str]]]],
    events: list[dict],
    maps: dict,
    built_at: str,
) -> str:
    username = profile.get("Username") or config.get("username", "Service Member")
    title = profile.get("_title") or f"{username} | Service Record File"
    tracker_url = config.get("tracker_url", "")

    proof_sections = ""
    for heading, header, body in proof_tables:
        proof_sections += (
            f'<section id="{esc(heading.lower().replace(" ", "-"))}">'
            f'<div class="section-header section-header--charcoal">{esc(heading)}</div>'
            f'<div class="section-body">{render_table(header, body)}</div></section>'
        )

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{esc(title)}</title>
  <meta name=\"description\" content=\"Public service record for {esc(username)}\">
  <link rel=\"stylesheet\" href=\"style.css\">
</head>
<body>
  <header class=\"site-header\">
    <div class=\"site-header__inner\">
      <h1>{esc(title)}</h1>
      <p>Public service record · Last built {esc(built_at)} UTC</p>
    </div>
  </header>
  <nav class=\"site-nav\" aria-label=\"Sections\">
    <ul>
      <li><a href=\"#profile\">Profile</a></li>
      <li><a href=\"#decorations\">Decorations</a></li>
      <li><a href=\"#events-log\">Events</a></li>
      <li><a href=\"#overseas-bar-proof\">OSB</a></li>
      <li><a href=\"#joint-service-achievement-proof\">JSA</a></li>
      <li><a href=\"#army-sea-duty-/-campaign-proof\">Campaign</a></li>
      <li><a href=\"#southwest-asia-service-proof\">SWA</a></li>
      <li><a href=\"#kosovo-campaign-proof\">Kosovo</a></li>
      <li><a href=\"#afghanistan-campaign-proof\">Afghanistan</a></li>
    </ul>
  </nav>
  <main>
    <section id=\"profile\">
      <div class=\"section-header\">Profile</div>
      <div class=\"section-body\">{render_profile(profile, config.get('service_photo_url', ''))}</div>
    </section>
    <section id=\"decorations\">
      <div class=\"section-header section-header--gold\">Decorations</div>
      <div class=\"section-body\">
        <h2 class=\"visually-hidden\">Badges</h2>
        {render_badge_sections(maps)}
        <h2 style=\"margin-top:1.25rem;color:var(--maroon);\">Ribbons</h2>
        {render_ribbons(maps, ribbons)}
      </div>
    </section>
    <section id=\"events-log\">
      <div class=\"section-header\">Events Log</div>
      <div class=\"section-body\">{render_events(events)}</div>
    </section>
    {proof_sections}
  </main>
  <footer class=\"site-footer\">
    <p>Source tracker: <a href=\"{esc(tracker_url)}\" rel=\"noopener\">Google Sheets</a>
    · Built by <a href=\"{esc(config.get('awards_tui_repo', ''))}\" rel=\"noopener\">awards-tui</a></p>
  </footer>
</body>
</html>
"""


def ensure_style_css() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if not STYLE_SRC.is_file():
        raise FileNotFoundError(f"Missing stylesheet at {STYLE_SRC}")


def main() -> int:
    config = load_config()
    maps = load_image_map()
    token_path = resolve_token_path()
    tok = load_token(token_path)
    sheet_id = config["spreadsheet_id"]

    profile = fetch_profile(tok, sheet_id, token_path)
    ribbons = fetch_obtained_ribbons(tok, sheet_id, token_path)
    events = fetch_events(tok, sheet_id, token_path)

    proof_tables: list[tuple[str, list[str], list[list[str]]]] = []
    for sheet_name, heading in PROOF_TABS:
        header, body = fetch_table(tok, sheet_id, sheet_name, token_path)
        proof_tables.append((heading, header, body))

    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_style_css()
    INDEX_PATH.write_text(
        build_html(config, profile, ribbons, proof_tables, events, maps, built_at),
        encoding="utf-8",
    )
    print(f"Wrote {INDEX_PATH}")
    print(f"Wrote {DOCS_DIR / 'style.css'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
