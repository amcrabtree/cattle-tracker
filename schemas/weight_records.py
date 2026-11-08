"""Single source of truth for the `weight_records` table's fields, shared by entry/server."""

WEIGHT_RECORD_FIELDS: dict[str, dict] = {
    "weight_date": {"type": "string", "description": "ISO date"},
    "weight_lbs":  {"type": "number", "exclusiveMinimum": 0},
    "category":    {"type": "string", "enum": ["weaning", "yearly", "routine"]},
    "notes":       {"type": "string"},
}


def weight_record_properties(overrides: dict[str, dict] | None = None) -> dict[str, dict]:
    """Return a fresh copy of WEIGHT_RECORD_FIELDS properties, with per-field overrides."""
    props = {k: dict(v) for k, v in WEIGHT_RECORD_FIELDS.items()}
    for field, extra in (overrides or {}).items():
        props[field].update(extra)
    return props
