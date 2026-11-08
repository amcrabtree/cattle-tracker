"""Single source of truth for the `health_events` table's fields, shared by entry/server."""

HEALTH_EVENT_FIELDS: dict[str, dict] = {
    "event_date":    {"type": "string", "description": "ISO date — defaults to today"},
    "event_type":    {"type": "string", "enum": ["illness", "treatment", "vet_visit", "injury", "other"]},
    "description":   {"type": "string"},
    "treatment":     {"type": "string"},
    "medication":    {"type": "string"},
    "veterinarian":  {"type": "string"},
    "resolved_date": {"type": "string", "description": "ISO date — leave blank if still active"},
    "notes":         {"type": "string"},
}


def health_event_properties(overrides: dict[str, dict] | None = None) -> dict[str, dict]:
    """Return a fresh copy of HEALTH_EVENT_FIELDS properties, with per-field overrides."""
    props = {k: dict(v) for k, v in HEALTH_EVENT_FIELDS.items()}
    for field, extra in (overrides or {}).items():
        props[field].update(extra)
    return props
