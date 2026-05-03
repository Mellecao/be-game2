import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY precisam estar no .env"
        )
    return create_client(url, key)
