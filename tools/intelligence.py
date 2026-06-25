from datetime import date, timedelta

from supabase import Client


def get_herd_summary(client: Client, args: dict) -> dict:
    upcoming_days = args.get("upcoming_days", 30)
    today = str(date.today())
    cutoff = str(date.today() + timedelta(days=upcoming_days))
    recent_from = str(date.today() - timedelta(days=30))

    all_animals = client.table("animals").select("status, animal_type, sex").execute()

    counts_by_status: dict[str, int] = {}
    counts_by_type: dict[str, int] = {}
    counts_by_sex: dict[str, int] = {}

    for a in all_animals.data:
        counts_by_status[a["status"]] = counts_by_status.get(a["status"], 0) + 1
        counts_by_type[a["animal_type"]] = counts_by_type.get(a["animal_type"], 0) + 1
        if a["sex"]:
            counts_by_sex[a["sex"]] = counts_by_sex.get(a["sex"], 0) + 1

    recent_weights = (
        client.table("weight_records")
        .select("weight_date, weight_lbs, category, animals(tag)")
        .gte("weight_date", recent_from)
        .order("weight_date", desc=True)
        .limit(10)
        .execute()
    )

    upcoming_vax = (
        client.table("vaccinations")
        .select("next_due_date, vaccine_name, animals(tag, registration_num)")
        .gte("next_due_date", today)
        .lte("next_due_date", cutoff)
        .order("next_due_date")
        .limit(20)
        .execute()
    )

    active_health = (
        client.table("health_events")
        .select("id", count="exact")
        .is_("resolved_date", "null")
        .execute()
    )

    return {
        "total_animals":          len(all_animals.data),
        "by_status":              counts_by_status,
        "by_type":                counts_by_type,
        "by_sex":                 counts_by_sex,
        "recent_weight_activity": recent_weights.data,
        "upcoming_vaccinations":  upcoming_vax.data,
        "active_health_issues":   active_health.count,
    }


def get_upcoming_vaccinations(client: Client, args: dict) -> list[dict]:
    days = args.get("days", 30)
    today = str(date.today())
    cutoff = str(date.today() + timedelta(days=days))

    result = (
        client.table("vaccinations")
        .select("*, animals(tag, registration_num, phn, status)")
        .gte("next_due_date", today)
        .lte("next_due_date", cutoff)
        .order("next_due_date")
        .execute()
    )
    return result.data


def get_active_health_issues(client: Client, args: dict) -> list[dict]:
    query = (
        client.table("health_events")
        .select("*, animals(tag, registration_num, phn, status)")
        .is_("resolved_date", "null")
        .order("event_date", desc=True)
    )
    if args.get("event_type"):
        query = query.eq("event_type", args["event_type"])

    result = query.execute()
    return result.data
