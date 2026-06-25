import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import anyio
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from supabase import Client


# ── Timestamp helpers ─────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_in(**delta) -> str:
    return (utcnow() + timedelta(**delta)).isoformat()


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_expired(value) -> bool:
    return bool(value) and parse_ts(value) < utcnow()


# ── Custom token types ────────────────────────────────────────────────────────

class CattleAccessToken(AccessToken):
    user_id: str


class CattleAuthorizationCode(AuthorizationCode):
    user_id: str


# ── Provider ──────────────────────────────────────────────────────────────────

class CattleOAuthProvider:
    """
    MCP OAuth provider that delegates Google login to Supabase Auth.
    Access is restricted to email addresses listed in the ALLOWED_EMAILS
    environment variable (comma-separated).

    Flow:
      /authorize → Supabase Google OAuth → /supabase/callback → MCP token
    """

    def __init__(self, db: Client, base_url: str, supabase_url: str, allowed_emails: set[str]):
        self.db = db
        self.base_url = base_url.rstrip("/")
        self.supabase_url = supabase_url.rstrip("/")
        self.allowed_emails = {e.strip().lower() for e in allowed_emails}

    async def _db(self, fn):
        return await anyio.to_thread.run_sync(fn)

    # ── Client registration ───────────────────────────────────────────────────

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        def _query():
            return self.db.table("mcp_oauth_clients").select("*").eq("client_id", client_id).limit(1).execute()

        result = await self._db(_query)
        if not result.data:
            return None
        row = result.data[0]
        auth_method = "client_secret_post" if row.get("client_secret") else "none"
        return OAuthClientInformationFull(
            client_id=row["client_id"],
            client_secret=row.get("client_secret"),
            redirect_uris=[AnyUrl(uri) for uri in row["redirect_uris"]],
            client_name=row.get("client_name"),
            scope=row.get("scope"),
            token_endpoint_auth_method=auth_method,
        )

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        row = {
            "client_id":     client_info.client_id,
            "client_secret": client_info.client_secret,
            "redirect_uris": [str(uri) for uri in (client_info.redirect_uris or [])],
            "client_name":   client_info.client_name,
            "scope":         client_info.scope,
        }

        def _upsert():
            return self.db.table("mcp_oauth_clients").upsert(row).execute()

        await self._db(_upsert)

    # ── Authorization ─────────────────────────────────────────────────────────

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        supabase_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(supabase_verifier.encode()).digest()
        supabase_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

        state_id = secrets.token_urlsafe(32)

        row = {
            "state":                          state_id,
            "client_id":                      client.client_id,
            "code_challenge":                 params.code_challenge,
            "redirect_uri":                   str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "scopes":                         params.scopes or [],
            "mcp_state":                      params.state,
            "supabase_code_verifier":         supabase_verifier,
            "expires_at":                     iso_in(minutes=10),
        }

        def _insert():
            return self.db.table("mcp_pending_auths").insert(row).execute()

        await self._db(_insert)

        callback = f"{self.base_url}/supabase/callback/landing?mcp_state={state_id}"
        return (
            f"{self.supabase_url}/auth/v1/authorize"
            f"?provider=google"
            f"&redirect_to={quote(callback, safe='')}"
            f"&code_challenge={supabase_challenge}"
            f"&code_challenge_method=S256"
        )

    # ── Authorization code ────────────────────────────────────────────────────

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> CattleAuthorizationCode | None:
        def _query():
            return (
                self.db.table("mcp_auth_codes")
                .select("*")
                .eq("code", authorization_code)
                .eq("client_id", client.client_id)
                .limit(1)
                .execute()
            )

        result = await self._db(_query)
        if not result.data:
            return None
        row = result.data[0]
        if is_expired(row["expires_at"]):
            return None

        return CattleAuthorizationCode(
            code=row["code"],
            client_id=row["client_id"],
            user_id=row["user_id"],
            scopes=row["scopes"] or [],
            expires_at=parse_ts(row["expires_at"]).timestamp(),
            code_challenge=row["code_challenge"],
            redirect_uri=AnyUrl(row["redirect_uri"]),
            redirect_uri_provided_explicitly=row["redirect_uri_provided_explicitly"],
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: CattleAuthorizationCode
    ) -> OAuthToken:
        def _delete():
            return self.db.table("mcp_auth_codes").delete().eq("code", authorization_code.code).execute()

        await self._db(_delete)

        access_token = secrets.token_urlsafe(32)
        refresh_token_val = secrets.token_urlsafe(32)
        expires_at = iso_in(hours=1)

        def _store():
            self.db.table("mcp_access_tokens").insert({
                "token":      access_token,
                "client_id":  client.client_id,
                "user_id":    authorization_code.user_id,
                "scopes":     authorization_code.scopes,
                "expires_at": expires_at,
            }).execute()
            self.db.table("mcp_refresh_tokens").insert({
                "token":      refresh_token_val,
                "client_id":  client.client_id,
                "user_id":    authorization_code.user_id,
                "scopes":     authorization_code.scopes,
                "expires_at": None,
            }).execute()

        await self._db(_store)

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=refresh_token_val,
            scope=" ".join(authorization_code.scopes) if authorization_code.scopes else None,
        )

    # ── Refresh token ─────────────────────────────────────────────────────────

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        def _query():
            return (
                self.db.table("mcp_refresh_tokens")
                .select("*")
                .eq("token", refresh_token)
                .eq("client_id", client.client_id)
                .limit(1)
                .execute()
            )

        result = await self._db(_query)
        if not result.data:
            return None
        row = result.data[0]
        return RefreshToken(
            token=row["token"],
            client_id=row["client_id"],
            scopes=row["scopes"] or [],
            expires_at=None,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        def _query():
            return (
                self.db.table("mcp_refresh_tokens")
                .select("user_id")
                .eq("token", refresh_token.token)
                .limit(1)
                .execute()
            )

        result = await self._db(_query)
        if not result.data:
            raise TokenError(error="invalid_grant", error_description="Refresh token not found")

        user_id = result.data[0]["user_id"]
        new_scopes = scopes or refresh_token.scopes
        new_access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)
        expires_at = iso_in(hours=1)

        def _rotate():
            self.db.table("mcp_refresh_tokens").delete().eq("token", refresh_token.token).execute()
            self.db.table("mcp_access_tokens").insert({
                "token":      new_access,
                "client_id":  client.client_id,
                "user_id":    user_id,
                "scopes":     new_scopes,
                "expires_at": expires_at,
            }).execute()
            self.db.table("mcp_refresh_tokens").insert({
                "token":      new_refresh,
                "client_id":  client.client_id,
                "user_id":    user_id,
                "scopes":     new_scopes,
                "expires_at": None,
            }).execute()

        await self._db(_rotate)

        return OAuthToken(
            access_token=new_access,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=new_refresh,
            scope=" ".join(new_scopes) if new_scopes else None,
        )

    # ── Access token ──────────────────────────────────────────────────────────

    async def load_access_token(self, token: str) -> CattleAccessToken | None:
        def _query():
            return (
                self.db.table("mcp_access_tokens")
                .select("*")
                .eq("token", token)
                .limit(1)
                .execute()
            )

        result = await self._db(_query)
        if not result.data:
            return None
        row = result.data[0]
        if is_expired(row.get("expires_at")):
            return None

        return CattleAccessToken(
            token=row["token"],
            client_id=row["client_id"],
            user_id=str(row["user_id"]),
            scopes=row["scopes"] or [],
            expires_at=None,
        )

    # ── Revocation ────────────────────────────────────────────────────────────

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        def _revoke():
            self.db.table("mcp_access_tokens").delete().eq("token", token.token).execute()
            self.db.table("mcp_refresh_tokens").delete().eq("token", token.token).execute()

        await self._db(_revoke)
