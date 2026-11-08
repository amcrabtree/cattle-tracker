"""Single source of truth for the `breeding_records` table's fields, shared by entry/retrieval/server."""

BREEDING_FIELDS: dict[str, dict] = {
    "dam_id":                {"type": "string", "description": "UUID of the dam (cow)"},
    "sire_id":               {"type": "string", "description": "UUID of the sire (bull)"},
    "breeding_date":         {"type": "string", "description": "ISO date"},
    "expected_calving_date": {"type": "string", "description": "ISO date"},
    "actual_calving_date":   {"type": "string", "description": "ISO date"},
    "calf_id":               {"type": "string", "description": "UUID of resulting calf"},
    "outcome":               {"type": "string", "enum": ["live_birth", "stillbirth", "abort", "pending"]},
    "notes":                 {"type": "string"},
}

BREEDING_UPDATABLE_FIELDS = [
    "breeding_date", "expected_calving_date", "actual_calving_date",
    "calf_id", "outcome", "notes",
]


def breeding_properties(overrides: dict[str, dict] | None = None) -> dict[str, dict]:
    """Return a fresh copy of BREEDING_FIELDS properties, with per-field overrides."""
    props = {k: dict(v) for k, v in BREEDING_FIELDS.items()}
    for field, extra in (overrides or {}).items():
        props[field].update(extra)
    return props
