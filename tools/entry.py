from datetime import date

from supabase import Client

_ANIMAL_FIELDS = [
    "registration_num", "phn", "tag", "name", "animal_type",
    "sex", "color", "dob", "status", "dam_id", "sire_id", "bangs_tag", "notes",
]


def add_animal(client: Client, args: dict) -> dict:
    # Batch mode: args contains an "animals" list
    if "animals" in args:
        defaults = {k: args[k] for k in _ANIMAL_FIELDS if k in args}
        rows = []
        for item in args["animals"]:
            row = {**defaults, **{k: item[k] for k in _ANIMAL_FIELDS if k in item}}
            row.setdefault("status", "active")
            rows.append(row)
        if not rows:
            return {"error": "No animals provided."}
        result = client.table("animals").insert(rows).execute()
        return {"success": True, "inserted": len(result.data), "animal_ids": [a["id"] for a in result.data]}

    row = {k: args[k] for k in _ANIMAL_FIELDS if k in args}
    row.setdefault("status", "active")

    result = client.table("animals").insert(row).execute()
    return {"success": True, "animal_id": result.data[0]["id"]}


def update_animal(client: Client, args: dict) -> dict:
    # Batch mode: args contains an "updates" list, each with animal_id/tag/registration_num + fields
    if "updates" in args:
        defaults = {k: args[k] for k in _ANIMAL_FIELDS if k in args}
        updated = []
        skipped = []
        for item in args["updates"]:
            animal_id = _resolve_animal_id(client, item)
            fields = {**defaults, **{k: item[k] for k in _ANIMAL_FIELDS if k in item}}
            if not animal_id or not fields:
                skipped.append(item)
                continue
            result = client.table("animals").update(fields).eq("id", animal_id).execute()
            if not result.data:
                skipped.append(item)
                continue
            updated.append(result.data[0])
        if not updated:
            return {"error": "No animals could be updated.", "skipped": skipped}
        return {"success": True, "updated": len(updated), "animals": updated, "skipped": skipped}

    animal_id = args["animal_id"]
    updates = {k: args[k] for k in _ANIMAL_FIELDS if k in args}
    if not updates:
        return {"error": "No fields to update provided."}

    result = client.table("animals").update(updates).eq("id", animal_id).execute()
    if not result.data:
        return {"error": f"No animal found with id '{animal_id}'"}
    return {"success": True, "animal": result.data[0]}


def _resolve_animal_id(client: Client, record: dict) -> str | None:
    """Return animal UUID from animal_id, tag, or registration_num."""
    if record.get("animal_id"):
        return record["animal_id"]
    lookup_field = "tag" if record.get("tag") else "registration_num" if record.get("registration_num") else None
    if not lookup_field:
        return None
    result = client.table("animals").select("id").eq(lookup_field, record[lookup_field]).limit(1).execute()
    return result.data[0]["id"] if result.data else None


def record_weight(client: Client, args: dict) -> dict:
    today = str(date.today())

    # Batch mode: args contains a "records" list
    if "records" in args:
        defaults = {
            "weight_date": args.get("weight_date", today),
            "category":    args.get("category"),
            "notes":       args.get("notes"),
        }
        rows = []
        skipped = []
        for item in args["records"]:
            merged = {**defaults, **item}
            animal_id = _resolve_animal_id(client, merged)
            if not animal_id:
                skipped.append(item)
                continue
            rows.append({
                "animal_id":   animal_id,
                "weight_date": merged.get("weight_date", today),
                "weight_lbs":  merged["weight_lbs"],
                "category":    merged["category"],
                "notes":       merged.get("notes"),
            })
        if not rows:
            return {"error": "No records could be matched to animals.", "skipped": skipped}
        result = client.table("weight_records").insert(rows).execute()
        return {"success": True, "inserted": len(result.data), "skipped": skipped}

    # Single mode
    animal_id = _resolve_animal_id(client, args)
    if not animal_id:
        return {"error": "Could not resolve animal. Provide animal_id, tag, or registration_num."}
    row = {
        "animal_id":   animal_id,
        "weight_date": args.get("weight_date", today),
        "weight_lbs":  args["weight_lbs"],
        "category":    args["category"],
        "notes":       args.get("notes"),
    }
    result = client.table("weight_records").insert(row).execute()
    return {"success": True, "weight_record_id": result.data[0]["id"]}


def record_vaccination(client: Client, args: dict) -> dict:
    # Batch mode
    if "records" in args:
        defaults = {
            "vaccine_name":      args.get("vaccine_name"),
            "administered_date": args.get("administered_date", str(date.today())),
            "administered_by":   args.get("administered_by"),
            "next_due_date":     args.get("next_due_date"),
            "lot_number":        args.get("lot_number"),
            "notes":             args.get("notes"),
        }
        rows = []
        skipped = []
        for item in args["records"]:
            merged = {**defaults, **item}
            animal_id = _resolve_animal_id(client, merged)
            if not animal_id:
                skipped.append(item)
                continue
            rows.append({
                "animal_id":         animal_id,
                "vaccine_name":      merged["vaccine_name"],
                "administered_date": merged["administered_date"],
                "administered_by":   merged.get("administered_by"),
                "next_due_date":     merged.get("next_due_date"),
                "lot_number":        merged.get("lot_number"),
                "notes":             merged.get("notes"),
            })
        if not rows:
            return {"error": "No records could be matched to animals.", "skipped": skipped}
        result = client.table("vaccinations").insert(rows).execute()
        return {"success": True, "inserted": len(result.data), "skipped": skipped}

    # Single mode
    animal_id = _resolve_animal_id(client, args)
    if not animal_id:
        return {"error": "Could not resolve animal. Provide animal_id, tag, or registration_num."}
    row = {
        "animal_id":         animal_id,
        "vaccine_name":      args["vaccine_name"],
        "administered_date": args["administered_date"],
        "administered_by":   args.get("administered_by"),
        "next_due_date":     args.get("next_due_date"),
        "lot_number":        args.get("lot_number"),
        "notes":             args.get("notes"),
    }
    result = client.table("vaccinations").insert(row).execute()
    return {"success": True, "vaccination_id": result.data[0]["id"]}


def log_health_event(client: Client, args: dict) -> dict:
    today = str(date.today())

    # Batch mode
    if "records" in args:
        defaults = {
            "event_date":   args.get("event_date", today),
            "event_type":   args.get("event_type"),
            "description":  args.get("description"),
            "treatment":    args.get("treatment"),
            "medication":   args.get("medication"),
            "veterinarian": args.get("veterinarian"),
            "resolved_date": args.get("resolved_date"),
            "notes":        args.get("notes"),
        }
        rows = []
        skipped = []
        for item in args["records"]:
            merged = {**defaults, **item}
            animal_id = _resolve_animal_id(client, merged)
            if not animal_id:
                skipped.append(item)
                continue
            rows.append({
                "animal_id":    animal_id,
                "event_date":   merged.get("event_date", today),
                "event_type":   merged["event_type"],
                "description":  merged["description"],
                "treatment":    merged.get("treatment"),
                "medication":   merged.get("medication"),
                "veterinarian": merged.get("veterinarian"),
                "resolved_date": merged.get("resolved_date"),
                "notes":        merged.get("notes"),
            })
        if not rows:
            return {"error": "No records could be matched to animals.", "skipped": skipped}
        result = client.table("health_events").insert(rows).execute()
        return {"success": True, "inserted": len(result.data), "skipped": skipped}

    # Single mode
    animal_id = _resolve_animal_id(client, args)
    if not animal_id:
        return {"error": "Could not resolve animal. Provide animal_id, tag, or registration_num."}
    row = {
        "animal_id":    animal_id,
        "event_date":   args.get("event_date", today),
        "event_type":   args["event_type"],
        "description":  args["description"],
        "treatment":    args.get("treatment"),
        "medication":   args.get("medication"),
        "veterinarian": args.get("veterinarian"),
        "resolved_date": args.get("resolved_date"),
        "notes":        args.get("notes"),
    }
    result = client.table("health_events").insert(row).execute()
    return {"success": True, "health_event_id": result.data[0]["id"]}


_DELETABLE_TABLES = {
    "animals", "weight_records", "vaccinations", "health_events", "breeding_records"
}


def delete_record(client: Client, args: dict) -> dict:
    table = args.get("table")
    if table not in _DELETABLE_TABLES:
        return {"error": f"Invalid table '{table}'. Must be one of: {', '.join(sorted(_DELETABLE_TABLES))}"}

    # Batch mode: args contains a "record_ids" list
    if "record_ids" in args:
        record_ids = args["record_ids"]
        if not record_ids:
            return {"error": "record_ids is empty."}
        result = client.table(table).delete().in_("id", record_ids).execute()
        deleted_ids = [r["id"] for r in result.data]
        skipped = [rid for rid in record_ids if rid not in deleted_ids]
        return {"success": True, "deleted_from": table, "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids, "skipped": skipped}

    record_id = args.get("record_id")
    if not record_id:
        return {"error": "record_id is required."}
    result = client.table(table).delete().eq("id", record_id).execute()
    if not result.data:
        return {"error": f"No record found in '{table}' with id '{record_id}'"}
    return {"success": True, "deleted_from": table, "record_id": record_id}


def record_breeding(client: Client, args: dict) -> dict:
    _BREEDING_FIELDS = [
        "breeding_date", "expected_calving_date", "actual_calving_date",
        "calf_id", "outcome", "notes",
    ]

    # Batch mode: args contains a "records" list
    if "records" in args:
        defaults = {k: args[k] for k in _BREEDING_FIELDS if k in args}
        updated = []
        inserted_ids = []
        skipped = []
        for item in args["records"]:
            merged = {**defaults, **{k: item[k] for k in _BREEDING_FIELDS if k in item}}
            if item.get("breeding_record_id"):
                result = (
                    client.table("breeding_records")
                    .update(merged)
                    .eq("id", item["breeding_record_id"])
                    .execute()
                )
                if not result.data:
                    skipped.append(item)
                    continue
                updated.append(result.data[0])
                continue
            if not item.get("dam_id") or not item.get("sire_id"):
                skipped.append(item)
                continue
            row = {"dam_id": item["dam_id"], "sire_id": item["sire_id"], **merged}
            result = client.table("breeding_records").insert(row).execute()
            inserted_ids.append(result.data[0]["id"])
        if not updated and not inserted_ids:
            return {"error": "No breeding records could be processed.", "skipped": skipped}
        return {"success": True, "updated": updated, "inserted_ids": inserted_ids, "skipped": skipped}

    if args.get("breeding_record_id"):
        updates = {k: args[k] for k in _BREEDING_FIELDS if k in args}
        result = (
            client.table("breeding_records")
            .update(updates)
            .eq("id", args["breeding_record_id"])
            .execute()
        )
        if not result.data:
            return {"error": f"No breeding record found with id '{args['breeding_record_id']}'"}
        return {"success": True, "breeding_record": result.data[0]}

    row = {
        "dam_id":  args["dam_id"],
        "sire_id": args["sire_id"],
        **{k: args[k] for k in _BREEDING_FIELDS if k in args},
    }
    result = client.table("breeding_records").insert(row).execute()
    return {"success": True, "breeding_record_id": result.data[0]["id"]}
