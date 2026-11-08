"""Single source of truth for the `animals` table's fields, shared by entry/retrieval/server."""

ANIMAL_FIELDS: dict[str, dict] = {
    "registration_num": {"type": "string"},
    "phn":              {"type": "string", "description": "Physical herd number e.g. 'SPAD 28N'"},
    "tag":              {"type": "string", "description": "Short tag e.g. '28N'"},
    "name":             {"type": "string", "description": "Sire display name"},
    "animal_type":      {"type": "string", "enum": ["calf", "cow", "bull", "sire", "steer"]},
    "sex":              {"type": "string", "enum": ["M", "F"]},
    "color":            {"type": "string"},
    "dob":              {"type": "string", "description": "ISO date"},
    "status":           {"type": "string", "enum": ["active", "dead", "sold"]},
    "dam_id":           {"type": "string", "description": "UUID of the dam"},
    "sire_id":          {"type": "string", "description": "UUID of the sire"},
    "bangs_tag":        {"type": "string", "description": "Official brucellosis vaccination tag number issued to heifers"},
    "disposition":      {"type": "integer"},
    "usda_eid":         {"type": "string", "description": "15-digit USDA EID", "minLength": 15, "maxLength": 15},
    "notes":            {"type": "string"},
}

ANIMAL_SEARCH_FIELDS: dict[str, dict] = {
    "tag":              {"type": "string", "description": "Short tag e.g. '28N'"},
    "registration_num": {"type": "string", "description": "Full registration number e.g. 'LFM3451181'"},
    "phn":              {"type": "string", "description": "Physical herd number e.g. 'SPAD 28N'"},
    "name":             {"type": "string", "description": "Sire display name e.g. 'GROWTH FUND'"},
    "status":           {"type": "string", "enum": ["active", "dead", "sold"]},
    "animal_type":      {"type": "string", "enum": ["calf", "cow", "bull", "sire", "steer"]},
    "sex":              {"type": "string", "enum": ["M", "F"]},
    "disposition":      {"type": "integer"},
    "usda_eid":         {"type": "string", "description": "15-digit USDA EID"},
}

# Fields matched with ILIKE partial-match instead of exact eq() in search_animals.
ANIMAL_SEARCH_PARTIAL_MATCH = {"tag", "registration_num", "phn", "name", "usda_eid"}


def animal_properties(overrides: dict[str, dict] | None = None) -> dict[str, dict]:
    """Return a fresh copy of ANIMAL_FIELDS properties, with per-field overrides (e.g. extra descriptions)."""
    props = {k: dict(v) for k, v in ANIMAL_FIELDS.items()}
    for field, extra in (overrides or {}).items():
        props[field].update(extra)
    return props
