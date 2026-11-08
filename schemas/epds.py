"""Single source of truth for the `epds` table's fields, shared by entry/retrieval/server."""

EPD_FIELDS: dict[str, dict] = {
    "bw":         {"type": "number", "description": "Birth weight EPD"},
    "bw_pct":     {"type": "integer", "minimum": 0, "maximum": 100, "description": "Birth weight EPD breed percentile"},
    "ww":         {"type": "number", "description": "Weaning weight EPD"},
    "ww_pct":     {"type": "integer", "minimum": 0, "maximum": 100, "description": "Weaning weight EPD breed percentile"},
    "yw":         {"type": "number", "description": "Yearling weight EPD"},
    "yw_pct":     {"type": "integer", "minimum": 0, "maximum": 100, "description": "Yearling weight EPD breed percentile"},
    "as_of_date": {"type": "string", "description": "ISO date EPDs were calculated/published"},
    "source":     {"type": "string", "description": "Breed association or registry, e.g. 'AAA', 'ASA'"},
    "notes":      {"type": "string"},
}


def epd_properties(overrides: dict[str, dict] | None = None) -> dict[str, dict]:
    """Return a fresh copy of EPD_FIELDS properties, with per-field overrides."""
    props = {k: dict(v) for k, v in EPD_FIELDS.items()}
    for field, extra in (overrides or {}).items():
        props[field].update(extra)
    return props
