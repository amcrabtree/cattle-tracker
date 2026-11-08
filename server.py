import contextlib
import json
import os
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.auth.routes import create_auth_routes, create_protected_resource_routes
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from auth.context import current_user_id
from auth.oauth_provider import CattleOAuthProvider
from auth.supabase_callback import handle_supabase_callback
from db.client import get_client
from tools.entry import (
    add_animal,
    delete_record,
    log_health_event,
    record_breeding,
    record_vaccination,
    record_weight,
    update_animal,
)
from tools.intelligence import (
    get_active_health_issues,
    get_herd_summary,
    get_upcoming_vaccinations,
)
from tools.retrieval import (
    get_animal_detail,
    get_breeding_records,
    get_health_events,
    get_vaccination_records,
    get_weight_history,
    search_animals,
)
from schemas.animals import ANIMAL_SEARCH_FIELDS, animal_properties

load_dotenv()

BASE_URL     = os.environ["BASE_URL"]       # e.g. https://cattle-tracker-2kq1.onrender.com
SUPABASE_URL = os.environ["SUPABASE_URL"]
ALLOWED_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.environ.get("ALLOWED_EMAILS", "").split(",")
    if e.strip()
}

server = Server("cattle-tracker")
oauth_provider = CattleOAuthProvider(
    db=get_client(),
    base_url=BASE_URL,
    supabase_url=SUPABASE_URL,
    allowed_emails=ALLOWED_EMAILS,
)


# ── Tool definitions ──────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── Retrieval ──────────────────────────────────────────────────────────
        Tool(
            name="search_animals",
            description="Search cattle by tag, registration number, PHN, name, status, type, sex, disposition, or USDA EID.",
            inputSchema={
                "type": "object",
                "properties": ANIMAL_SEARCH_FIELDS,
            },
        ),
        Tool(
            name="get_animal_detail",
            description="Full profile for one animal including weight history, vaccinations, health events, and breeding records.",
            inputSchema={
                "type": "object",
                "required": ["animal_id"],
                "properties": {
                    "animal_id": {"type": "string", "description": "UUID of the animal"},
                },
            },
        ),
        Tool(
            name="get_weight_history",
            description="Weight records for a specific animal or the entire herd, filterable by category and date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "animal_id": {"type": "string"},
                    "category":  {"type": "string", "enum": ["weaning", "yearly", "routine"]},
                    "date_from": {"type": "string", "description": "ISO date e.g. 2025-01-01"},
                    "date_to":   {"type": "string", "description": "ISO date e.g. 2025-12-31"},
                },
            },
        ),
        Tool(
            name="get_vaccination_records",
            description="Vaccination records filterable by animal, vaccine name, and date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "animal_id":    {"type": "string"},
                    "vaccine_name": {"type": "string"},
                    "date_from":    {"type": "string", "description": "ISO date"},
                    "date_to":      {"type": "string", "description": "ISO date"},
                },
            },
        ),
        Tool(
            name="get_health_events",
            description="Health events filterable by animal, event type, date range, and resolved/unresolved status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "animal_id":  {"type": "string"},
                    "event_type": {"type": "string", "enum": ["illness", "treatment", "vet_visit", "injury", "other"]},
                    "date_from":  {"type": "string", "description": "ISO date"},
                    "date_to":    {"type": "string", "description": "ISO date"},
                    "resolved":   {"type": "boolean", "description": "true=resolved only, false=unresolved only, omit=all"},
                },
            },
        ),
        Tool(
            name="get_breeding_records",
            description="Breeding and calving records filterable by dam, sire, outcome, and date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dam_id":    {"type": "string", "description": "UUID of the dam (cow)"},
                    "sire_id":   {"type": "string", "description": "UUID of the sire (bull)"},
                    "outcome":   {"type": "string", "enum": ["live_birth", "stillbirth", "abort", "pending"]},
                    "date_from": {"type": "string", "description": "ISO date — filters on breeding_date"},
                    "date_to":   {"type": "string", "description": "ISO date"},
                },
            },
        ),
        # ── Entry ──────────────────────────────────────────────────────────────
        Tool(
            name="add_animal",
            description=(
                "Add one or more new animals to the herd. For a single animal, provide fields at the top level "
                "(animal_type required). For a batch, set top-level defaults (e.g. animal_type, status, dob) and "
                "pass an 'animals' array — each item's fields override the defaults. One tool call handles the whole batch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    **animal_properties({"animal_type": {"description": "Required in single mode; default for batch"}}),
                    "animals": {
                        "type": "array",
                        "description": "Batch mode: list of animals to add. Top-level fields apply to all unless overridden per item.",
                        "items": {
                            "type": "object",
                            "properties": animal_properties(),
                        },
                    },
                },
            },
        ),
        Tool(
            name="update_animal",
            description=(
                "Update fields on one or more existing animals (status, tag, notes, parentage, etc.). For a single "
                "animal, provide animal_id + fields to change. For a batch (e.g. marking several animals sold), set "
                "top-level defaults (e.g. status) and pass an 'updates' array — each item needs animal_id, tag, or "
                "registration_num. One tool call handles the whole batch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "animal_id": {"type": "string", "description": "Single-record mode: UUID"},
                    **animal_properties({"status": {"description": "Default for all batch updates"}}),
                    "updates": {
                        "type": "array",
                        "description": "Batch mode: list of animals to update, each identified by animal_id, tag, or registration_num. Top-level fields apply to all unless overridden per item.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "animal_id": {"type": "string"},
                                **animal_properties(),
                            },
                        },
                    },
                },
            },
        ),
        Tool(
            name="record_weight",
            description=(
                "Record weight measurements. For a single animal, provide animal_id/tag/registration_num + weight_lbs + category. "
                "For a batch of 2–60 animals, provide top-level defaults (weight_date, category) and a 'records' array where each "
                "item has tag or registration_num and weight_lbs (overrides defaults when repeated). One tool call handles the whole batch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "animal_id":        {"type": "string", "description": "Single-record mode: UUID"},
                    "tag":              {"type": "string", "description": "Single-record mode: short tag e.g. '28N'"},
                    "registration_num": {"type": "string"},
                    "weight_date":      {"type": "string", "description": "ISO date — defaults to today. Used as default for batch records."},
                    "weight_lbs":       {"type": "number", "description": "Single-record mode"},
                    "category":         {"type": "string", "enum": ["weaning", "yearly", "routine"], "description": "Default for all batch records"},
                    "notes":            {"type": "string"},
                    "records": {
                        "type": "array",
                        "description": "Batch mode: list of weight entries. Top-level weight_date/category/notes apply to all unless overridden per item.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tag":              {"type": "string"},
                                "registration_num": {"type": "string"},
                                "animal_id":        {"type": "string"},
                                "weight_lbs":       {"type": "number"},
                                "weight_date":      {"type": "string"},
                                "category":         {"type": "string", "enum": ["weaning", "yearly", "routine"]},
                                "notes":            {"type": "string"},
                            },
                            "required": ["weight_lbs"],
                        },
                    },
                },
            },
        ),
        Tool(
            name="record_vaccination",
            description=(
                "Record vaccinations administered to animals. Use this for ALL vaccination records — routine scheduled vaccines, "
                "booster shots, and any other vaccine administration. For a single animal, provide animal_id/tag/registration_num + "
                "vaccine_name + administered_date. For a batch (e.g. whole herd processed same day), set top-level "
                "vaccine_name/administered_date/next_due_date as defaults and pass a 'records' array — each item just needs tag or "
                "registration_num. One tool call handles the whole batch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "animal_id":         {"type": "string", "description": "Single-record mode: UUID"},
                    "tag":               {"type": "string", "description": "Single-record mode: short tag"},
                    "registration_num":  {"type": "string"},
                    "vaccine_name":      {"type": "string", "description": "Default for all batch records"},
                    "administered_date": {"type": "string", "description": "ISO date — default for all batch records"},
                    "administered_by":   {"type": "string"},
                    "next_due_date":     {"type": "string", "description": "ISO date — default for all batch records"},
                    "lot_number":        {"type": "string"},
                    "notes":             {"type": "string"},
                    "records": {
                        "type": "array",
                        "description": "Batch mode: list of animals. Top-level vaccine_name/administered_date/next_due_date apply to all unless overridden.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tag":               {"type": "string"},
                                "registration_num":  {"type": "string"},
                                "animal_id":         {"type": "string"},
                                "vaccine_name":      {"type": "string"},
                                "administered_date": {"type": "string"},
                                "administered_by":   {"type": "string"},
                                "next_due_date":     {"type": "string"},
                                "lot_number":        {"type": "string"},
                                "notes":             {"type": "string"},
                            },
                        },
                    },
                },
            },
        ),
        Tool(
            name="log_health_event",
            description=(
                "Log unexpected health problems: illnesses, injuries, vet visits for issues, and medical treatments for non-routine conditions. "
                "Do NOT use this for routine scheduled vaccinations — use record_vaccination instead. "
                "For a single animal, provide animal_id/tag/registration_num + event_type + description. "
                "For a batch (e.g. same illness or treatment affecting multiple animals), set top-level event_type/description/medication "
                "as defaults and pass a 'records' array with one entry per animal. One tool call handles the whole batch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "animal_id":        {"type": "string", "description": "Single-record mode: UUID"},
                    "tag":              {"type": "string", "description": "Single-record mode: short tag"},
                    "registration_num": {"type": "string"},
                    "event_date":       {"type": "string", "description": "ISO date — defaults to today. Default for batch records."},
                    "event_type":       {"type": "string", "enum": ["illness", "treatment", "vet_visit", "injury", "other"], "description": "Default for batch records"},
                    "description":      {"type": "string", "description": "Default for batch records"},
                    "treatment":        {"type": "string"},
                    "medication":       {"type": "string"},
                    "veterinarian":     {"type": "string"},
                    "resolved_date":    {"type": "string", "description": "ISO date — leave blank if still active"},
                    "notes":            {"type": "string"},
                    "records": {
                        "type": "array",
                        "description": "Batch mode: list of animals receiving the same event. Top-level event_type/description/medication apply to all unless overridden.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tag":              {"type": "string"},
                                "registration_num": {"type": "string"},
                                "animal_id":        {"type": "string"},
                                "event_date":       {"type": "string"},
                                "event_type":       {"type": "string", "enum": ["illness", "treatment", "vet_visit", "injury", "other"]},
                                "description":      {"type": "string"},
                                "treatment":        {"type": "string"},
                                "medication":       {"type": "string"},
                                "veterinarian":     {"type": "string"},
                                "resolved_date":    {"type": "string"},
                                "notes":            {"type": "string"},
                            },
                        },
                    },
                },
            },
        ),
        Tool(
            name="record_breeding",
            description=(
                "Log breeding events or update calving outcomes, one or many at a time. For a single record, provide "
                "dam_id + sire_id (or breeding_record_id to update an existing record). For a batch, set top-level "
                "defaults (e.g. breeding_date, outcome) and pass a 'records' array — each item needs dam_id + sire_id "
                "(new record) or breeding_record_id (update). One tool call handles the whole batch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dam_id":                {"type": "string", "description": "UUID of the dam (cow)"},
                    "sire_id":               {"type": "string", "description": "UUID of the sire (bull)"},
                    "breeding_date":         {"type": "string", "description": "ISO date"},
                    "expected_calving_date": {"type": "string", "description": "ISO date"},
                    "actual_calving_date":   {"type": "string", "description": "ISO date"},
                    "calf_id":               {"type": "string", "description": "UUID of resulting calf"},
                    "outcome":               {"type": "string", "enum": ["live_birth", "stillbirth", "abort", "pending"]},
                    "notes":                 {"type": "string"},
                    "breeding_record_id":    {"type": "string", "description": "UUID — provide to update an existing record"},
                    "records": {
                        "type": "array",
                        "description": "Batch mode: list of breeding events/updates. Top-level fields apply to all unless overridden per item.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "dam_id":                {"type": "string"},
                                "sire_id":               {"type": "string"},
                                "breeding_date":         {"type": "string"},
                                "expected_calving_date": {"type": "string"},
                                "actual_calving_date":   {"type": "string"},
                                "calf_id":               {"type": "string"},
                                "outcome":               {"type": "string", "enum": ["live_birth", "stillbirth", "abort", "pending"]},
                                "notes":                 {"type": "string"},
                                "breeding_record_id":    {"type": "string"},
                            },
                        },
                    },
                },
            },
        ),
        # ── Delete ────────────────────────────────────────────────────────────
        Tool(
            name="delete_record",
            description=(
                "Permanently delete one or more records from the same table. Cannot be undone. "
                "Deleting an animal also cascades to its weights, vaccinations, and health events. "
                "Use get_animal_detail or the relevant retrieval tool first to confirm record IDs. "
                "For a single record, provide record_id. For a batch, provide record_ids (all from the same table)."
            ),
            inputSchema={
                "type": "object",
                "required": ["table"],
                "properties": {
                    "table":      {"type": "string", "enum": ["animals", "weight_records", "vaccinations", "health_events", "breeding_records"]},
                    "record_id":  {"type": "string", "description": "Single-record mode: UUID of the record to delete"},
                    "record_ids": {
                        "type": "array",
                        "description": "Batch mode: UUIDs of records to delete, all from the same table",
                        "items": {"type": "string"},
                    },
                },
            },
        ),
        # ── Intelligence ───────────────────────────────────────────────────────
        Tool(
            name="get_herd_summary",
            description="Herd-wide counts by status, type, and sex; recent weight activity; upcoming vaccinations; active health issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "upcoming_days": {"type": "integer", "description": "Days ahead to check for upcoming vaccinations (default 30)"},
                },
            },
        ),
        Tool(
            name="get_upcoming_vaccinations",
            description="Animals with a vaccination due within N days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days ahead to look (default 30)"},
                },
            },
        ),
        Tool(
            name="get_active_health_issues",
            description="All unresolved health events across the herd.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "enum": ["illness", "treatment", "vet_visit", "injury", "other"]},
                },
            },
        ),
    ]


# ── Tool dispatch ─────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    db = get_client()

    dispatch = {
        "search_animals":            lambda: search_animals(db, arguments),
        "get_animal_detail":         lambda: get_animal_detail(db, arguments),
        "get_weight_history":        lambda: get_weight_history(db, arguments),
        "get_vaccination_records":   lambda: get_vaccination_records(db, arguments),
        "get_health_events":         lambda: get_health_events(db, arguments),
        "get_breeding_records":      lambda: get_breeding_records(db, arguments),
        "add_animal":                lambda: add_animal(db, arguments),
        "update_animal":             lambda: update_animal(db, arguments),
        "record_weight":             lambda: record_weight(db, arguments),
        "record_vaccination":        lambda: record_vaccination(db, arguments),
        "log_health_event":          lambda: log_health_event(db, arguments),
        "record_breeding":           lambda: record_breeding(db, arguments),
        "delete_record":             lambda: delete_record(db, arguments),
        "get_herd_summary":          lambda: get_herd_summary(db, arguments),
        "get_upcoming_vaccinations": lambda: get_upcoming_vaccinations(db, arguments),
        "get_active_health_issues":  lambda: get_active_health_issues(db, arguments),
    }

    handler = dispatch.get(name)
    result = handler() if handler else {"error": f"Unknown tool: {name}"}
    return [TextContent(type="text", text=json.dumps(result, default=str))]


# ── Bearer auth middleware ─────────────────────────────────────────────────────

class BearerAuthMiddleware:
    """Validates OAuth Bearer tokens on /mcp requests and sets current_user_id."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()

        if not auth.startswith("Bearer "):
            resource_metadata_url = f"{BASE_URL}/.well-known/oauth-protected-resource/mcp"
            response = Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": (
                        f'Bearer realm="{BASE_URL}",'
                        f' resource_metadata_url="{resource_metadata_url}"'
                    )
                },
            )
            await response(scope, receive, send)
            return

        token = auth[7:]
        access_token = await oauth_provider.load_access_token(token)
        if access_token is None:
            response = Response(
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer realm="{BASE_URL}"'},
            )
            await response(scope, receive, send)
            return

        current_user_id.set(access_token.user_id)
        await self.app(scope, receive, send)


# ── HTTP app ──────────────────────────────────────────────────────────────────

session_manager = StreamableHTTPSessionManager(app=server, stateless=True)


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette) -> AsyncIterator[None]:
    _app.state.allowed_emails = ALLOWED_EMAILS
    async with session_manager.run():
        yield


async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
    await session_manager.handle_request(scope, receive, send)


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "cattle-tracker"})


async def supabase_callback_landing(request: Request):
    """
    Supabase returns auth params in the URL fragment (#) which never reaches
    the server. This page runs in the browser, extracts the fragment, and
    redirects to /supabase/callback as query params so the server can read them.
    """
    from starlette.responses import HTMLResponse as HR
    return HR("""<!DOCTYPE html>
<html><body><script>
  const hash = window.location.hash.substring(1);
  const params = new URLSearchParams(hash);
  // Merge any existing query params (mcp_state is passed as a query param)
  const query = new URLSearchParams(window.location.search);
  for (const [k, v] of params) { query.set(k, v); }
  window.location.replace('/supabase/callback?' + query.toString());
</script></body></html>""")


issuer  = AnyHttpUrl(BASE_URL)
mcp_url = AnyHttpUrl(f"{BASE_URL}/mcp")

auth_routes = create_auth_routes(
    provider=oauth_provider,
    issuer_url=issuer,
    client_registration_options=ClientRegistrationOptions(enabled=True),
    revocation_options=RevocationOptions(enabled=True),
)

protected_resource_routes = create_protected_resource_routes(
    resource_url=mcp_url,
    authorization_servers=[issuer],
)

app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/", endpoint=health),
        Route("/supabase/callback/landing", endpoint=supabase_callback_landing),
        Route("/supabase/callback", endpoint=handle_supabase_callback),
        *auth_routes,
        *protected_resource_routes,
        Mount("/mcp", app=handle_mcp),
    ],
)

app = BearerAuthMiddleware(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
