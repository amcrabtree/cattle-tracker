import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    """Singleton service-role client for normal DB operations."""
    global _client
    if _client is None:
        _client = new_client()
    return _client


def new_client() -> Client:
    """Fresh (non-singleton) client — used by OAuth callback to avoid
    swapping the shared client's auth state during code exchange."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)
