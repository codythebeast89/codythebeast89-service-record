#!/usr/bin/env python3
"""Google Sheets read-only client using awards-tui OAuth token."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_TOKEN_PATH = Path.home() / "Projects" / "awards-tui" / "token.json"


def resolve_token_path() -> Path:
    env_path = os.environ.get("AWARDS_TOKEN_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_TOKEN_PATH


def load_token(path: Path | None = None) -> dict:
    token_path = path or resolve_token_path()
    if not token_path.is_file():
        raise FileNotFoundError(
            f"OAuth token not found at {token_path}. "
            "Run awards-tui login locally or set AWARDS_TOKEN_PATH."
        )
    with token_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def refresh_token(tok: dict, *, persist_path: Path | None = None) -> dict:
    expiry = tok.get("expiry")
    if expiry:
        exp = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < exp - timedelta(seconds=120):
            return tok

    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": tok["refresh_token"],
            "client_id": tok["client_id"],
            "client_secret": tok["client_secret"],
        }
    ).encode()
    req = urllib.request.Request(tok["token_uri"], data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        new = json.load(resp)

    now = datetime.now(timezone.utc)
    tok["token"] = new["access_token"]
    tok["expiry"] = (now + timedelta(seconds=new.get("expires_in", 3600))).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    write_path = persist_path or resolve_token_path()
    if write_path.is_file():
        with write_path.open("w", encoding="utf-8") as handle:
            json.dump(tok, handle, indent=2)

    return tok


def api(
    tok: dict,
    spreadsheet_id: str,
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    persist_path: Path | None = None,
    retries: int = 4,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(retries):
        tok = refresh_token(tok, persist_path=persist_path)
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}{path}"
        payload = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {tok['token']}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
            last_error = exc
            if attempt + 1 >= retries:
                break
            time.sleep(min(2 ** attempt, 8))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Sheets API {exc.code}: {detail}") from exc

    if last_error is not None:
        raise RuntimeError(f"Sheets API request failed after {retries} attempts: {last_error}") from last_error
    raise RuntimeError("Sheets API request failed")


def get_values(
    tok: dict,
    spreadsheet_id: str,
    sheet: str,
    a1_range: str,
    *,
    value_render: str = "FORMATTED_VALUE",
    persist_path: Path | None = None,
) -> list[list[str]]:
    encoded = urllib.parse.quote(f"'{sheet}'!{a1_range}", safe="")
    path = f"/values/{encoded}?valueRenderOption={value_render}"
    result = api(tok, spreadsheet_id, path, persist_path=persist_path)
    return result.get("values") or []


def get_grid_cells(
    tok: dict,
    spreadsheet_id: str,
    sheet: str,
    a1_range: str,
    *,
    persist_path: Path | None = None,
) -> list[list[dict | None]]:
    """Return raw cell metadata for a range (includes chipRuns hyperlinks)."""
    encoded_range = urllib.parse.quote(f"'{sheet}'!{a1_range}", safe="")
    fields = urllib.parse.quote(
        "sheets(data(rowData(values(formattedValue,hyperlink,userEnteredValue,chipRuns))))",
        safe="",
    )
    path = f"?includeGridData=true&ranges={encoded_range}&fields={fields}"
    result = api(tok, spreadsheet_id, path, persist_path=persist_path)
    sheets = result.get("sheets") or []
    if not sheets:
        return []
    data = sheets[0].get("data") or []
    if not data:
        return []
    row_data = data[0].get("rowData") or []
    rows: list[list[dict | None]] = []
    max_cols = 0
    for row in row_data:
        values = row.get("values") or []
        max_cols = max(max_cols, len(values))
        rows.append(values)
    normalized: list[list[dict | None]] = []
    for values in rows:
        row: list[dict | None] = []
        for idx in range(max_cols):
            row.append(values[idx] if idx < len(values) else None)
        normalized.append(row)
    return normalized


def list_sheet_titles(
    tok: dict,
    spreadsheet_id: str,
    *,
    persist_path: Path | None = None,
) -> list[str]:
    meta = api(
        tok,
        spreadsheet_id,
        "?fields=sheets(properties(title))",
        persist_path=persist_path,
    )
    return [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]
