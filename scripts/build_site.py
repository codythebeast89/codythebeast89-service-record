#!/usr/bin/env python3
"""Build static service record site from Google Sheets tracker data."""

from __future__ import annotations

import html
import json
import sys
from dataclasses import dataclass
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
    ("Proof - Overseas Bar", "Overseas Bar Proof", "osb.html", "OSB"),
    ("Proof - JSA", "Joint Service Achievement Proof", "jsa.html", "JSA"),
    ("Proof - ASD", "Army Sea Duty / Campaign Proof", "asd.html", "Campaign"),
    ("Proof - SWA Service", "Southwest Asia Service Proof", "swa.html", "SWA"),
    ("Proof - Kosovo", "Kosovo Campaign Proof", "kosovo.html", "Kosovo"),
    ("Proof - Afghanistan", "Afghanistan Campaign Proof", "afghanistan.html", "Afghanistan"),
    ("Proof - Iraq", "Iraq Campaign Proof", "iraq.html", "Iraq"),
]


@dataclass(frozen=True)
class SitePage:
    slug: str
    file: str
    nav_label: str
    section_title: str
    header_variant: str | None = None  # None | "gold" | "charcoal"


CORE_PAGES: list[SitePage] = [
    SitePage("profile", "index.html", "Profile", "Profile"),
    SitePage("decorations", "decorations.html", "Decorations", "Decorations", "gold"),
    SitePage("events", "events.html", "Events", "Events Log"),
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


IMAGE_ALIASES: dict[str, str] = {
    "antartica service": "antarctica service",
    "afghanistan campagin": "afghanistan campaign",
}


def lookup_image(maps: dict, category: str, name: str) -> str | None:
    key = IMAGE_ALIASES.get(norm_key(name), norm_key(name))
    search_order: list[str] = []
    for cat in (category, "ribbons", "badges", "foreign"):
        if cat not in search_order:
            search_order.append(cat)
    for cat in search_order:
        bucket = maps.get(cat, {})
        if key in bucket:
            return bucket[key]
        for map_key, url in bucket.items():
            if key in map_key or map_key in key:
                return url
    return None


def render_award_media(url: str | None, label: str) -> str:
    if url:
        display_url = thumb_url(url)
        return (
            f'<div class="award-card__media">'
            f'<img src="{esc(display_url)}" alt="{esc(label)}" loading="lazy" width="52" height="52">'
            f"</div>"
        )
    return '<div class="award-card__media award-card__media--empty" aria-hidden="true"></div>'


def thumb_url(url: str, size: int = 120) -> str:
    """Prefer a bounded Wikimedia thumb URL for predictable layout and faster loads."""
    marker = "/thumb/"
    if marker not in url:
        return url
    base, rest = url.split(marker, 1)
    path_part, size_part = rest.rsplit("/", 1)
    if "px-" not in size_part:
        return url
    filename = size_part.split("px-", 1)[1]
    return f"{base}{marker}{path_part}/{size}px-{filename}"


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
            media = render_award_media(img, name)
            device_html = f'<div class="badge-card__device">{esc(device)}</div>' if device and device != "-" else ""
            chunks.append(
                "<li class=\"badge-card\">"
                f"{media}<div class=\"badge-card__body\"><div class=\"badge-card__name\">{esc(name)}</div>{device_html}</div>"
                "</li>"
            )
        chunks.append("</ul></div>")
    chunks.append("</div>")
    return "".join(chunks)


def render_ribbons(maps: dict, ribbons: list[tuple[str, str]]) -> str:
    chunks = [f'<p class="ribbon-count">{len(ribbons)} Ribbons Obtained</p><div class="ribbon-grid">']
    for name, device in ribbons:
        img = lookup_image(maps, "ribbons", name)
        media = render_award_media(img, name)
        device_html = f'<div class="ribbon-card__device">{esc(device)}</div>' if device else ""
        chunks.append(
            '<div class="ribbon-card">'
            f"{media}<div class=\"ribbon-card__body\"><div class=\"ribbon-card__name\">{esc(name)}</div>{device_html}</div>"
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
    fields: list[str] = []
    for field in PROFILE_FIELDS:
        value = profile.get(field, "")
        if not value:
            continue
        fields.append(
            f'<div class="profile-field"><dt>{esc(field)}</dt><dd>{esc(value)}</dd></div>'
        )
    return (
        f'<div class="profile-layout">'
        f'<div class="profile-photo"><img src="{esc(photo_url)}" alt="Service photo"></div>'
        f'<div class="profile-fields">{"".join(fields)}</div>'
        f"</div>"
        f'<p class="meta-note">Generated from tracker data. Title: {esc(title)}</p>'
    )


def site_pages() -> list[SitePage]:
    pages = list(CORE_PAGES)
    for _sheet, heading, file_name, nav_label in PROOF_TABS:
        pages.append(SitePage(heading.lower().replace(" ", "-"), file_name, nav_label, heading, "charcoal"))
    return pages


def header_class(variant: str | None) -> str:
    if variant == "gold":
        return "section-header section-header--gold"
    if variant == "charcoal":
        return "section-header section-header--charcoal"
    return "section-header"


def render_nav(pages: list[SitePage], active_file: str) -> str:
    items: list[str] = []
    for page in pages:
        active = " is-active" if page.file == active_file else ""
        items.append(
            f'<li><a href="{esc(page.file)}" class="site-nav__link{active}">{esc(page.nav_label)}</a></li>'
        )
    return f'<nav class="site-nav" aria-label="Sections"><ul>{"".join(items)}</ul></nav>'


def render_page_shell(
    *,
    config: dict,
    profile: dict[str, str],
    built_at: str,
    pages: list[SitePage],
    active_file: str,
    page_title: str,
    page_slug: str,
    body_html: str,
) -> str:
    username = profile.get("Username") or config.get("username", "Service Member")
    site_title = profile.get("_title") or f"{username} | Service Record File"
    tracker_url = config.get("tracker_url", "")
    awards_repo = config.get("awards_tui_repo", "")
    full_title = f"{page_title} · {site_title}" if page_title != "Profile" else site_title

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="view-transition" content="same-origin">
  <title>{esc(full_title)}</title>
  <meta name="description" content="Public service record for {esc(username)} — {esc(page_title)}">
  <link rel="stylesheet" href="style.css">
  <script src="nav.js" defer></script>
</head>
<body>
  <header class="site-header">
    <div class="site-header__inner">
      <h1><a class="site-header__home" href="index.html">{esc(site_title)}</a></h1>
      <p>Public service record · Last built {esc(built_at)} UTC</p>
    </div>
  </header>
  {render_nav(pages, active_file)}
  <main class="page-content" data-page="{esc(page_slug)}">
    {body_html}
  </main>
  <footer class="site-footer">
    <p>Source tracker: <a href="{esc(tracker_url)}" rel="noopener">Google Sheets</a>
    · Built by <a href="{esc(awards_repo)}" rel="noopener">awards-tui</a></p>
  </footer>
</body>
</html>
"""


def render_section_block(title: str, variant: str | None, inner_html: str, section_id: str = "") -> str:
    id_attr = f' id="{esc(section_id)}"' if section_id else ""
    return (
        f"<section{id_attr}>"
        f'<div class="{header_class(variant)}">{esc(title)}</div>'
        f'<div class="section-body">{inner_html}</div>'
        "</section>"
    )


def write_nav_js(pages: list[SitePage]) -> None:
    files = json.dumps([page.file for page in pages])
    script = f"""(() => {{
  const PAGES = {files};
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function currentFile() {{
    const path = window.location.pathname;
    return path.substring(path.lastIndexOf("/") + 1) || "index.html";
  }}

  function initEnter() {{
    const main = document.querySelector(".page-content");
    if (!main || reduceMotion) return;
    const dir = sessionStorage.getItem("page-transition-dir");
    sessionStorage.removeItem("page-transition-dir");
    if (dir === "forward") main.classList.add("page-enter-forward");
    else if (dir === "back") main.classList.add("page-enter-back");
    else main.classList.add("page-enter");
  }}

  function bindNav() {{
    document.querySelectorAll(".site-nav a.site-nav__link").forEach((link) => {{
      link.addEventListener("click", (event) => {{
        const href = link.getAttribute("href");
        if (!href || href.includes("://") || href.startsWith("#")) return;

        const from = currentFile();
        const fromIdx = PAGES.indexOf(from);
        const toIdx = PAGES.indexOf(href);
        if (fromIdx < 0 || toIdx < 0 || fromIdx === toIdx) {{
          return;
        }}

        sessionStorage.setItem(
          "page-transition-dir",
          toIdx > fromIdx ? "forward" : "back"
        );

        if (reduceMotion) return;

        const main = document.querySelector(".page-content");
        if (!main) return;

        event.preventDefault();
        const exitClass = toIdx > fromIdx ? "page-exit-forward" : "page-exit-back";
        main.classList.add(exitClass);
        window.setTimeout(() => {{
          window.location.href = href;
        }}, 280);
      }});
    }});
  }}

  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", () => {{
      initEnter();
      bindNav();
    }});
  }} else {{
    initEnter();
    bindNav();
  }}
}})();
"""
    (DOCS_DIR / "nav.js").write_text(script, encoding="utf-8")


def build_all_pages(
    config: dict,
    profile: dict[str, str],
    ribbons: list[tuple[str, str]],
    proof_tables: list[tuple[str, str, str, list[str], list[list[str]]]],
    events: list[dict],
    maps: dict,
    built_at: str,
) -> list[Path]:
    pages = site_pages()
    written: list[Path] = []

    profile_body = render_section_block(
        "Profile",
        None,
        render_profile(profile, config.get("service_photo_url", "")),
        "profile",
    )
    written.append(
        _write_page(
            "index.html",
            pages,
            config,
            profile,
            built_at,
            "Profile",
            "profile",
            profile_body,
        )
    )

    decorations_inner = (
        '<h2 class="visually-hidden">Badges</h2>'
        f"{render_badge_sections(maps)}"
        '<h2 class="decorations-ribbons-heading">Ribbons</h2>'
        f"{render_ribbons(maps, ribbons)}"
    )
    written.append(
        _write_page(
            "decorations.html",
            pages,
            config,
            profile,
            built_at,
            "Decorations",
            "decorations",
            render_section_block("Decorations", "gold", decorations_inner, "decorations"),
        )
    )

    written.append(
        _write_page(
            "events.html",
            pages,
            config,
            profile,
            built_at,
            "Events Log",
            "events",
            render_section_block("Events Log", None, render_events(events), "events-log"),
        )
    )

    for _sheet, heading, file_name, _nav, header, body in proof_tables:
        written.append(
            _write_page(
                file_name,
                pages,
                config,
                profile,
                built_at,
                heading,
                heading.lower().replace(" ", "-"),
                render_section_block(heading, "charcoal", render_table(header, body)),
            )
        )

    return written


def _write_page(
    file_name: str,
    pages: list[SitePage],
    config: dict,
    profile: dict[str, str],
    built_at: str,
    page_title: str,
    page_slug: str,
    body_html: str,
) -> Path:
    path = DOCS_DIR / file_name
    path.write_text(
        render_page_shell(
            config=config,
            profile=profile,
            built_at=built_at,
            pages=pages,
            active_file=file_name,
            page_title=page_title,
            page_slug=page_slug,
            body_html=body_html,
        ),
        encoding="utf-8",
    )
    return path


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

    proof_tables: list[tuple[str, str, str, str, list[str], list[list[str]]]] = []
    for sheet_name, heading, file_name, nav_label in PROOF_TABS:
        header, body = fetch_table(tok, sheet_id, sheet_name, token_path)
        proof_tables.append((sheet_name, heading, file_name, nav_label, header, body))

    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_style_css()
    pages = site_pages()
    write_nav_js(pages)
    written = build_all_pages(config, profile, ribbons, proof_tables, events, maps, built_at)
    for path in written:
        print(f"Wrote {path}")
    print(f"Wrote {DOCS_DIR / 'nav.js'}")
    print(f"Wrote {DOCS_DIR / 'style.css'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
