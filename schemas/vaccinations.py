"""Single source of truth for the `vaccinations` table's fields, shared by entry/server."""

VACCINATION_FIELDS: dict[str, dict] = {
    "vaccine_name":      {"type": "string"},
    "administered_date": {"type": "string", "description": "ISO date"},
    "administered_by":   {"type": "string"},
    "next_due_date":     {"type": "string", "description": "ISO date"},
    "lot_number":        {"type": "string"},
    "notes":             {"type": "string"},
}


def vaccination_properties(overrides: dict[str, dict] | None = None) -> dict[str, dict]:
    """Return a fresh copy of VACCINATION_FIELDS properties, with per-field overrides."""
    props = {k: dict(v) for k, v in VACCINATION_FIELDS.items()}
    for field, extra in (overrides or {}).items():
        props[field].update(extra)
    return props
