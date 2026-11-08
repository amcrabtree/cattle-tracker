from supabase import Client

from tools.animal_schema import ANIMAL_SEARCH_FIELDS, ANIMAL_SEARCH_PARTIAL_MATCH


def search_animals(client: Client, args: dict) -> list[dict]:
    query = client.table("animals").select("*")

    for field in ANIMAL_SEARCH_FIELDS:
        if not args.get(field):
            continue
        if field in ANIMAL_SEARCH_PARTIAL_MATCH:
            query = query.ilike(field, f"%{args[field]}%")
        else:
            query = query.eq(field, args[field])

    result = query.order("tag").limit(100).execute()
    return result.data


def get_animal_detail(client: Client, args: dict) -> dict:
    animal_id = args["animal_id"]

    animal = client.table("animals").select("*").eq("id", animal_id).limit(1).execute()
    if not animal.data:
        return {"error": f"No animal found with id '{animal_id}'"}

    weights = (
        client.table("weight_records")
        .select("*")
        .eq("animal_id", animal_id)
        .order("weight_date", desc=True)
        .execute()
    )
    vaccinations = (
        client.table("vaccinations")
        .select("*")
        .eq("animal_id", animal_id)
        .order("administered_date", desc=True)
        .execute()
    )
    health_events = (
        client.table("health_events")
        .select("*")
        .eq("animal_id", animal_id)
        .order("event_date", desc=True)
        .execute()
    )
    as_dam = (
        client.table("breeding_records")
        .select("*")
        .eq("dam_id", animal_id)
        .order("breeding_date", desc=True)
        .execute()
    )
    as_sire = (
        client.table("breeding_records")
        .select("*")
        .eq("sire_id", animal_id)
        .order("breeding_date", desc=True)
        .execute()
    )

    return {
        "animal":           animal.data[0],
        "weights":          weights.data,
        "vaccinations":     vaccinations.data,
        "health_events":    health_events.data,
        "breeding_as_dam":  as_dam.data,
        "breeding_as_sire": as_sire.data,
    }


def get_weight_history(client: Client, args: dict) -> list[dict]:
    query = client.table("weight_records").select("*, animals(tag, registration_num, phn)")

    if args.get("animal_id"):
        query = query.eq("animal_id", args["animal_id"])
    if args.get("category"):
        query = query.eq("category", args["category"])
    if args.get("date_from"):
        query = query.gte("weight_date", args["date_from"])
    if args.get("date_to"):
        query = query.lte("weight_date", args["date_to"])

    result = query.order("weight_date", desc=True).limit(200).execute()
    return result.data


def get_vaccination_records(client: Client, args: dict) -> list[dict]:
    query = client.table("vaccinations").select("*, animals(tag, registration_num, phn)")

    if args.get("animal_id"):
        query = query.eq("animal_id", args["animal_id"])
    if args.get("vaccine_name"):
        query = query.ilike("vaccine_name", f"%{args['vaccine_name']}%")
    if args.get("date_from"):
        query = query.gte("administered_date", args["date_from"])
    if args.get("date_to"):
        query = query.lte("administered_date", args["date_to"])

    result = query.order("administered_date", desc=True).limit(200).execute()
    return result.data


def get_health_events(client: Client, args: dict) -> list[dict]:
    query = client.table("health_events").select("*, animals(tag, registration_num, phn)")

    if args.get("animal_id"):
        query = query.eq("animal_id", args["animal_id"])
    if args.get("event_type"):
        query = query.eq("event_type", args["event_type"])
    if args.get("date_from"):
        query = query.gte("event_date", args["date_from"])
    if args.get("date_to"):
        query = query.lte("event_date", args["date_to"])
    if "resolved" in args:
        if args["resolved"]:
            query = query.not_.is_("resolved_date", "null")
        else:
            query = query.is_("resolved_date", "null")

    result = query.order("event_date", desc=True).limit(200).execute()
    return result.data


def get_breeding_records(client: Client, args: dict) -> list[dict]:
    # breeding_records has 3 FKs to animals; use !fkey_name to disambiguate
    query = client.table("breeding_records").select(
        "*,"
        "dam:animals!breeding_records_dam_id_fkey(tag, registration_num, phn),"
        "sire:animals!breeding_records_sire_id_fkey(tag, name),"
        "calf:animals!breeding_records_calf_id_fkey(tag, registration_num)"
    )

    if args.get("dam_id"):
        query = query.eq("dam_id", args["dam_id"])
    if args.get("sire_id"):
        query = query.eq("sire_id", args["sire_id"])
    if args.get("outcome"):
        query = query.eq("outcome", args["outcome"])
    if args.get("date_from"):
        query = query.gte("breeding_date", args["date_from"])
    if args.get("date_to"):
        query = query.lte("breeding_date", args["date_to"])

    result = query.order("breeding_date", desc=True).limit(100).execute()
    return result.data
