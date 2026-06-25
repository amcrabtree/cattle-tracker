-- MCP OAuth tables (mirrors benchbuddy-mcp pattern).
-- Run this in the Supabase SQL editor after 001_initial_schema.sql.

-- OAuth clients: Claude registers itself dynamically on first connect
create table if not exists mcp_oauth_clients (
  client_id     text        primary key,
  client_secret text,
  redirect_uris text[]      not null,
  client_name   text,
  scope         text,
  created_at    timestamptz default now()
);

-- Pending auth flows: created at /authorize, consumed at /supabase/callback
create table if not exists mcp_pending_auths (
  state                           text        primary key,
  client_id                       text        not null,
  code_challenge                  text        not null,
  redirect_uri                    text        not null,
  redirect_uri_provided_explicitly boolean    not null default false,
  scopes                          text[],
  mcp_state                       text,
  supabase_code_verifier          text        not null,
  expires_at                      timestamptz not null
);

-- Short-lived auth codes issued to Claude after successful Google login
create table if not exists mcp_auth_codes (
  code                            text        primary key,
  client_id                       text        not null,
  user_id                         uuid        not null,
  scopes                          text[],
  code_challenge                  text        not null,
  redirect_uri                    text        not null,
  redirect_uri_provided_explicitly boolean    not null default false,
  expires_at                      timestamptz not null,
  created_at                      timestamptz default now()
);

-- Access tokens → user_id mapping (1-hour TTL)
create table if not exists mcp_access_tokens (
  token      text        primary key,
  client_id  text        not null,
  user_id    uuid        not null,
  scopes     text[],
  expires_at timestamptz,
  created_at timestamptz default now()
);

-- Refresh tokens (rotated on each use, no expiry)
create table if not exists mcp_refresh_tokens (
  token      text        primary key,
  client_id  text        not null,
  user_id    uuid        not null,
  scopes     text[],
  expires_at timestamptz,
  created_at timestamptz default now()
);

-- Indexes for expiry-based cleanup queries
create index if not exists mcp_pending_auths_expires_idx  on mcp_pending_auths(expires_at);
create index if not exists mcp_auth_codes_expires_idx     on mcp_auth_codes(expires_at);
create index if not exists mcp_access_tokens_expires_idx  on mcp_access_tokens(expires_at);

-- RLS: service-role key bypasses; anon/authenticated get nothing
alter table mcp_oauth_clients   enable row level security;
alter table mcp_pending_auths   enable row level security;
alter table mcp_auth_codes      enable row level security;
alter table mcp_access_tokens   enable row level security;
alter table mcp_refresh_tokens  enable row level security;
