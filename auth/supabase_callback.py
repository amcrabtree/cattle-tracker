"""
Handles the redirect from Supabase after Google login.

Flow:
  /supabase/callback?code=<supabase_code>&mcp_state=<state_id>
    → exchange Supabase code for session (gets user_id + email)
    → verify email is in ALLOWED_EMAILS
    → mint MCP authorization code
    → redirect to Claude's redirect_uri?code=<mcp_code>&state=<mcp_state>
"""

import secrets

import anyio
from mcp.server.auth.provider import construct_redirect_uri
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from auth.oauth_provider import is_expired, iso_in
from db.client import get_client, new_client


async def handle_supabase_callback(request: Request) -> HTMLResponse | RedirectResponse:
    db = get_client()
    mcp_state_id = request.query_params.get("mcp_state")
    supabase_code = request.query_params.get("code")

    def _error(msg: str) -> HTMLResponse:
        return HTMLResponse(
            f"<h2>Cattle Tracker — login error</h2><p>{msg}</p>",
            status_code=400,
        )

    if not mcp_state_id or not supabase_code:
        return _error("Missing code or state parameter.")

    # Load pending auth params
    def _load_pending():
        return (
            db.table("mcp_pending_auths")
            .select("*")
            .eq("state", mcp_state_id)
            .limit(1)
            .execute()
        )

    result = await anyio.to_thread.run_sync(_load_pending)
    if not result.data:
        return _error("Login session not found or already used. Please try again.")

    pending = result.data[0]
    if is_expired(pending["expires_at"]):
        return _error("Login session expired. Please try again.")

    # Exchange Supabase code for user session (use a fresh client to avoid
    # swapping the shared service-role client's auth state)
    code_verifier = pending["supabase_code_verifier"]

    def _exchange():
        return new_client().auth.exchange_code_for_session({
            "auth_code": supabase_code,
            "code_verifier": code_verifier,
        })

    try:
        session = await anyio.to_thread.run_sync(_exchange)
    except Exception as exc:
        return _error(f"Failed to verify Google login: {exc}")

    user_id = str(session.user.id)
    user_email = (session.user.email or "").strip().lower()

    # Check against allowed emails (loaded by server.py into the provider)
    from auth.oauth_provider import CattleOAuthProvider  # avoid circular at module level
    # Access the provider's allowed_emails via the app state set in server.py
    allowed_emails: set[str] = request.app.state.allowed_emails

    if user_email not in allowed_emails:
        return _error(
            f"The Google account <strong>{user_email}</strong> is not authorized "
            f"to access Cattle Tracker. Contact Angela to be added."
        )

    # Consume the pending record
    def _delete_pending():
        return db.table("mcp_pending_auths").delete().eq("state", mcp_state_id).execute()

    await anyio.to_thread.run_sync(_delete_pending)

    # Mint an MCP authorization code (5-minute window for Claude to exchange it)
    mcp_code = secrets.token_urlsafe(32)

    def _store_code():
        return db.table("mcp_auth_codes").insert({
            "code":                           mcp_code,
            "client_id":                      pending["client_id"],
            "user_id":                        user_id,
            "scopes":                         pending["scopes"] or [],
            "code_challenge":                 pending["code_challenge"],
            "redirect_uri":                   pending["redirect_uri"],
            "redirect_uri_provided_explicitly": pending["redirect_uri_provided_explicitly"],
            "expires_at":                     iso_in(minutes=5),
        }).execute()

    await anyio.to_thread.run_sync(_store_code)

    redirect_url = construct_redirect_uri(
        pending["redirect_uri"],
        code=mcp_code,
        state=pending.get("mcp_state"),
    )
    return RedirectResponse(
        url=redirect_url,
        status_code=302,
        headers={"Cache-Control": "no-store"},
    )
