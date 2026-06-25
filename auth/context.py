from contextvars import ContextVar

# Set by BearerAuthMiddleware before each /mcp request
current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)
