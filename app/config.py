import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://bbm-server-hfq1.onrender.com",
]